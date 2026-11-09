"""Groq High-Throughput LPU Provider Adapter."""

import logging
from typing import Optional

from app.llm.base import LLMConfig
from app.llm.providers.openai_provider import OpenAICompatibleLLMProvider

logger = logging.getLogger("mmaip.llm.groq")

GROQ_DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"


class GroqLLMProvider(OpenAICompatibleLLMProvider):
    """Groq LPU Provider implementing ultra-low-latency Llama and Mixtral inference."""

    def __init__(self, default_base_url: str = GROQ_DEFAULT_BASE_URL):
        super().__init__(
            name="groq",
            default_base_url=default_base_url,
            default_api_key_env="GROQ_API_KEY",
        )

    @property
    def provider_name(self) -> str:
        return "groq"

    async def validate_key(self, config: LLMConfig) -> bool:
        """Validate Groq API key against /models endpoint."""
        api_key = config.api_key or self._resolve_api_key(config)
        if not api_key:
            return False
        base_url = config.base_url or self._default_base_url
        url = f"{base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers)
                return res.status_code == 200
        except Exception as exc:
            logger.warning(f"Groq key validation network failure: {exc}")
            return False
