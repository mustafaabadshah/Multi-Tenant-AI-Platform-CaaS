"""Groq High-Throughput LPU Provider Adapter."""

import logging
import os
from collections.abc import AsyncGenerator

from app.llm.base import LLMConfig, LLMMessage, LLMResponse, LLMStreamChunk
from app.llm.providers.openai_provider import OpenAICompatibleLLMProvider

logger = logging.getLogger("mmaip.llm.groq")

GROQ_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = os.environ.get("GROQ_DEFAULT_MODEL", "openai/gpt-oss-120b")


class GroqLLMProvider(OpenAICompatibleLLMProvider):
    """Groq LPU Provider implementing ultra-low-latency open-weights inference."""

    def __init__(self, default_base_url: str = GROQ_DEFAULT_BASE_URL):
        super().__init__(
            name="groq",
            default_base_url=default_base_url,
            default_api_key_env="GROQ_API_KEY",
        )

    @property
    def provider_name(self) -> str:
        return "groq"

    def _normalize_config(self, config: LLMConfig) -> LLMConfig:
        raw_model = (config.model or "").strip()
        if not raw_model or raw_model.lower() == "auto":
            model = GROQ_DEFAULT_MODEL
            logger.debug(f"Resolved Groq auto model to production default: {model}")
        else:
            model = raw_model

        extra_h = getattr(config, "extra_headers", {}) or {}
        return LLMConfig(
            provider=config.provider,
            model=model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            api_key=config.api_key,
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            extra_headers=extra_h,
        )

    async def generate(self, messages: list[LLMMessage], config: LLMConfig) -> LLMResponse:
        return await super().generate(messages, self._normalize_config(config))

    async def generate_stream(
        self, messages: list[LLMMessage], config: LLMConfig
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        async for chunk in super().generate_stream(messages, self._normalize_config(config)):
            yield chunk

    async def validate_key(self, config: LLMConfig) -> bool:
        """Validate Groq API key against /models endpoint."""
        api_key = config.api_key or self._resolve_api_key(config)
        if not api_key:
            return False
        base_url = self._resolve_base_url(config)
        url = f"{base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                res = await client.get(url, headers=headers)
                return res.status_code == 200
        except Exception as exc:
            logger.warning(f"Groq key validation network failure: {exc}")
            return False
