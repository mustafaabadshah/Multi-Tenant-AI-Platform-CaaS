"""OpenAI-compatible embedding provider supporting OmniRoute and OpenAI wire format."""

import asyncio
import logging
import random
from typing import Optional

import httpx

from app.core.config import settings
from app.embeddings.base import (
    BatchEmbeddingResult,
    EmbeddingProvider,
    EmbeddingProviderConfig,
    EmbeddingResult,
)

logger = logging.getLogger("mmaip.embeddings.openai")


class OpenAICompatibleProvider(EmbeddingProvider):
    """Embedding provider connecting to OpenAI or OmniRoute gateway via standard REST wire format."""

    def __init__(self, name: str = "omniroute"):
        self._name = name

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def default_model(self) -> str:
        return "text-embedding-3-small"

    @property
    def supported_models(self) -> list[str]:
        return [
            "text-embedding-3-small",
            "text-embedding-3-large",
            "text-embedding-ada-002",
            "bge-small-en-v1.5",
            "bge-base-en-v1.5",
            "auto",
        ]

    def get_dimensions(self, model_name: Optional[str] = None) -> int:
        name = (model_name or self.default_model).lower()
        if "3-large" in name:
            return 3072
        if "bge-small" in name:
            return 384
        if "bge-base" in name:
            return 768
        return 1536

    def _resolve_url_and_key(self, config: EmbeddingProviderConfig) -> tuple[str, str]:
        """Resolve target base URL and API key using config with system fallbacks."""
        base_url = config.base_url or settings.LLM_BASE_URL
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/") + "/v1" if not base_url.endswith("/v1") else base_url

        api_key = config.api_key or settings.OMNIROUTE_API_KEY or settings.OPENAI_API_KEY or "omniroute-local"
        endpoint = f"{base_url.rstrip('/')}/embeddings"
        return endpoint, api_key

    async def _request_embeddings(
        self, texts: list[str], config: EmbeddingProviderConfig
    ) -> tuple[list[list[float]], int]:
        """Execute HTTP POST with exponential backoff and jitter."""
        endpoint, api_key = self._resolve_url_and_key(config)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": texts,
            "model": config.model_name or self.default_model,
        }
        if config.dimensions and "3-" in (config.model_name or ""):
            payload["dimensions"] = config.dimensions

        max_retries = config.max_retries
        timeout = float(config.timeout_seconds)

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(endpoint, json=payload, headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    raw_data = data.get("data", [])
                    # Sort by index to preserve input order
                    sorted_items = sorted(raw_data, key=lambda x: x.get("index", 0))
                    embeddings = [item["embedding"] for item in sorted_items]
                    usage = data.get("usage", {})
                    tokens = usage.get("total_tokens", sum(max(1, len(t.split())) for t in texts))
                    return embeddings, tokens

                if resp.status_code == 429:
                    logger.warning(f"Rate limited by {self._name} on attempt {attempt + 1}")
                elif resp.status_code in (401, 403):
                    raise PermissionError(f"Authentication failed with {self._name} at {endpoint}: {resp.text}")
                elif resp.status_code >= 500:
                    logger.warning(f"Server error {resp.status_code} from {self._name}: {resp.text}")
                else:
                    raise RuntimeError(f"Embedding request failed [{resp.status_code}]: {resp.text}")

            except (httpx.TimeoutException, httpx.NetworkError) as err:
                logger.warning(f"Network error on attempt {attempt + 1}: {err}")
                if "127.0.0.1" in endpoint or "localhost" in endpoint:
                    break

            if attempt < max_retries:
                # Exponential backoff with jitter
                delay = (2**attempt) * 0.5 + random.uniform(0.1, 0.5)
                await asyncio.sleep(delay)

        raise TimeoutError(f"Failed to fetch embeddings from {endpoint} after {max_retries + 1} attempts.")

    async def embed_text(self, text: str, config: EmbeddingProviderConfig) -> EmbeddingResult:
        embeddings, tokens = await self._request_embeddings([text], config)
        if not embeddings:
            raise ValueError("No embedding returned by provider.")
        vec = embeddings[0]
        return EmbeddingResult(
            vector=vec,
            dimensions=len(vec),
            tokens_used=tokens,
            model=config.model_name or self.default_model,
        )

    async def embed_batch(
        self, texts: list[str], config: EmbeddingProviderConfig
    ) -> BatchEmbeddingResult:
        if not texts:
            return BatchEmbeddingResult(embeddings=[], total_tokens=0, model=config.model_name, dimensions=0)

        batch_size = max(1, config.batch_size or settings.EMBEDDING_BATCH_SIZE)
        all_embeddings: list[list[float]] = []
        total_tokens = 0
        dims = 0

        for i in range(0, len(texts), batch_size):
            chunk_texts = texts[i : i + batch_size]
            embs, tokens = await self._request_embeddings(chunk_texts, config)
            all_embeddings.extend(embs)
            total_tokens += tokens
            if embs and dims == 0:
                dims = len(embs[0])

        return BatchEmbeddingResult(
            embeddings=all_embeddings,
            total_tokens=total_tokens,
            model=config.model_name or self.default_model,
            dimensions=dims,
        )

    async def validate_configuration(self, config: EmbeddingProviderConfig) -> bool:
        """Validate connectivity and authentication."""
        try:
            res = await self.embed_text("test connection", config)
            return len(res.vector) > 0
        except Exception as e:
            logger.info(f"Validation failed for {self._name}: {e}")
            return False

    async def check_health(self) -> bool:
        """Check if target gateway is accessible."""
        cfg = EmbeddingProviderConfig(
            provider_name=self._name,
            model_name=self.default_model,
            timeout_seconds=2,
            max_retries=0,
        )
        return await self.validate_configuration(cfg)
