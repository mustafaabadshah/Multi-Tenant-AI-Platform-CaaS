"""Registry for managing and resolving LLM providers."""

import logging
from functools import lru_cache
from typing import Any, Optional

from app.llm.base import LLMProvider
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.providers.openai_provider import OpenAICompatibleLLMProvider

logger = logging.getLogger("mmaip.llm.registry")


class LLMProviderRegistry:
    """Registry maintaining active LLM providers."""

    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}
        self._register_defaults()

    def _register_defaults(self):
        # 1. OmniRoute Gateway
        omniroute_provider = OpenAICompatibleLLMProvider(
            name="omniroute",
            default_base_url="http://localhost:20128/v1",
        )
        self.register_provider(omniroute_provider)

        # 2. OpenAI BYOK
        openai_provider = OpenAICompatibleLLMProvider(
            name="openai",
            default_base_url="https://api.openai.com/v1",
        )
        self.register_provider(openai_provider)

        # 3. Mock Provider for offline tests
        mock_provider = MockLLMProvider(name="mock")
        self.register_provider(mock_provider)

    def register_provider(self, provider: LLMProvider):
        name = provider.provider_name.lower()
        self._providers[name] = provider
        logger.debug(f"Registered LLM provider: {name}")

    def get_provider(self, name: Optional[str]) -> LLMProvider:
        key = (name or "omniroute").lower()
        if key not in self._providers:
            if "mock" in self._providers:
                return self._providers["mock"]
            raise KeyError(f"LLM provider '{key}' is not registered. Available: {list(self._providers.keys())}")
        return self._providers[key]

    def list_providers(self) -> list[dict[str, Any]]:
        return [
            {"name": "omniroute", "description": "OmniRoute AI Gateway (Auto Model Routing)"},
            {"name": "openai", "description": "OpenAI BYOK (Direct API Key)"},
            {"name": "mock", "description": "Deterministic Offline Testing Provider"},
        ]


@lru_cache
def get_llm_registry() -> LLMProviderRegistry:
    """Return singleton instance of LLMProviderRegistry."""
    return LLMProviderRegistry()
