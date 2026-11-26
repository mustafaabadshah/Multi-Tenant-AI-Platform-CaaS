"""Registry for managing and resolving LLM providers with capability metadata."""

import logging
from functools import lru_cache
from typing import Any, Optional

from app.llm.base import LLMProvider
from app.llm.capabilities import get_model_capability_registry
from app.llm.providers.anthropic_provider import AnthropicLLMProvider
from app.llm.providers.gemini_provider import GeminiLLMProvider
from app.llm.providers.groq_provider import GroqLLMProvider
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.providers.openai_provider import OpenAICompatibleLLMProvider

logger = logging.getLogger("mmaip.llm.registry")


class LLMProviderRegistry:
    """Registry maintaining active LLM providers and capability metadata."""

    def __init__(self):
        self._providers: dict[str, LLMProvider] = {}
        self._register_defaults()

    def _register_defaults(self):
        # 1. Groq (High-Throughput LPU)
        self.register_provider(GroqLLMProvider())

        # 2. Anthropic (Claude 3.5 Sonnet / Haiku / Opus)
        self.register_provider(AnthropicLLMProvider())

        # 3. Google Gemini (1.5 Pro / Flash & 2.0 Flash)
        self.register_provider(GeminiLLMProvider())

        # 4. OpenAI (Direct BYOK)
        self.register_provider(
            OpenAICompatibleLLMProvider(
                name="openai",
                default_base_url="https://api.openai.com/v1",
                default_api_key_env="OPENAI_API_KEY",
            )
        )

        # 5. OmniRoute Gateway (Local AI Gateway)
        self.register_provider(
            OpenAICompatibleLLMProvider(
                name="omniroute",
                default_base_url="http://localhost:20128/v1",
                default_api_key_env="OMNIROUTE_API_KEY",
            )
        )

        # 6. Mock Provider for offline tests
        self.register_provider(MockLLMProvider(name="mock"))

    def register_provider(self, provider: LLMProvider):
        name = provider.provider_name.lower()
        self._providers[name] = provider
        logger.debug(f"Registered LLM provider: {name}")

    def get_all_providers(self) -> list[LLMProvider]:
        return list(self._providers.values())

    def get_provider(self, name: Optional[str], strict: bool = False) -> LLMProvider:
        key = (name or "omniroute").lower()
        if key not in self._providers:
            if not strict and "mock" in self._providers:
                return self._providers["mock"]
            raise KeyError(f"LLM provider '{key}' is not registered. Available: {list(self._providers.keys())}")
        return self._providers[key]

    def list_providers(self) -> list[dict[str, Any]]:
        cap_reg = get_model_capability_registry()
        meta = {
            "groq": {
                "display_name": "Groq LPU Engine",
                "description": "Ultra-low-latency open-weights inference (Llama 3.3, Mixtral)",
                "requires_api_key": True,
                "default_base_url": "https://api.groq.com/openai/v1",
            },
            "anthropic": {
                "display_name": "Anthropic Claude",
                "description": "Claude 3.5 Sonnet, Haiku, and Opus models with advanced reasoning",
                "requires_api_key": True,
                "default_base_url": "https://api.anthropic.com/v1",
            },
            "gemini": {
                "display_name": "Google Gemini",
                "description": "Gemini 1.5 Pro, Flash, and 2.0 Flash with up to 2M token context",
                "requires_api_key": True,
                "default_base_url": "https://generativelanguage.googleapis.com/v1beta",
            },
            "openai": {
                "display_name": "OpenAI Direct",
                "description": "GPT-4o, GPT-4o-mini, and o3-mini models via direct BYOK key",
                "requires_api_key": True,
                "default_base_url": "https://api.openai.com/v1",
            },
            "omniroute": {
                "display_name": "OmniRoute Local Gateway",
                "description": "Local dynamic router automatically dispatching requests to configured models",
                "requires_api_key": False,
                "default_base_url": "http://localhost:20128/v1",
            },
            "mock": {
                "display_name": "Deterministic Mock",
                "description": "Zero-network offline provider for local development and test validation",
                "requires_api_key": False,
                "default_base_url": None,
            },
        }

        output = []
        for name in ["groq", "anthropic", "gemini", "openai", "omniroute", "mock"]:
            if name in self._providers:
                info = meta.get(name, {"display_name": name.capitalize(), "description": ""})
                models = cap_reg.get_by_provider(name)
                output.append({
                    "name": name,
                    "display_name": info["display_name"],
                    "description": info["description"],
                    "requires_api_key": info.get("requires_api_key", True),
                    "default_base_url": info.get("default_base_url"),
                    "models": [
                        {
                            "model_id": m.model_id,
                            "display_name": m.display_name,
                            "context_window": m.context_window,
                            "max_output_tokens": m.max_output_tokens,
                            "supports_streaming": m.supports_streaming,
                            "supports_tools": m.supports_tools,
                            "supports_vision": m.supports_vision,
                            "supports_audio": m.supports_audio,
                            "description": m.description,
                        }
                        for m in models
                    ],
                })
        return output


@lru_cache
def get_llm_registry() -> LLMProviderRegistry:
    """Return singleton instance of LLMProviderRegistry."""
    return LLMProviderRegistry()
