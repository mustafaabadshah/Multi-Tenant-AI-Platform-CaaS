"""Registry for managing and resolving embedding providers."""

import logging
from functools import lru_cache
from typing import Any, Optional

from app.embeddings.base import EmbeddingProvider
from app.embeddings.providers.local_provider import LocalEmbeddingProvider
from app.embeddings.providers.mock_provider import MockEmbeddingProvider
from app.embeddings.providers.openai_provider import OpenAICompatibleProvider
from app.embeddings.providers.sentence_transformer_provider import SentenceTransformerProvider

logger = logging.getLogger("mmaip.embeddings.registry")


class EmbeddingProviderRegistry:
    """Registry maintaining active embedding providers."""

    def __init__(self):
        self._providers: dict[str, EmbeddingProvider] = {}
        self._register_defaults()

    def _register_defaults(self):
        # Register default OmniRoute gateway provider
        omniroute_provider = OpenAICompatibleProvider(name="omniroute")
        self.register_provider(omniroute_provider)

        # Register OpenAI provider
        openai_provider = OpenAICompatibleProvider(name="openai")
        self.register_provider(openai_provider)

        # Register SentenceTransformers CPU semantic provider
        st_provider = SentenceTransformerProvider()
        self.register_provider(st_provider)

        # Register Local CPU feature projection provider (baseline / tests)
        local_provider = LocalEmbeddingProvider()
        self.register_provider(local_provider)

        # Register Mock provider for testing
        mock_provider = MockEmbeddingProvider()
        self.register_provider(mock_provider)


    def register_provider(self, provider: EmbeddingProvider):
        name = provider.provider_name.lower()
        self._providers[name] = provider
        logger.debug(f"Registered embedding provider: {name}")

    def get_provider(self, name: Optional[str]) -> EmbeddingProvider:
        key = (name or "omniroute").lower()
        if key not in self._providers:
            # Fall back to omniroute or mock
            if "mock" in self._providers:
                return self._providers["mock"]
            raise KeyError(f"Embedding provider '{key}' is not registered. Available: {list(self._providers.keys())}")
        return self._providers[key]

    def list_providers(self) -> list[dict[str, Any]]:
        """Return provider descriptors without secrets."""
        results = []
        for name, p in self._providers.items():
            results.append({
                "name": p.provider_name,
                "default_model": p.default_model,
                "supported_models": p.supported_models,
                "default_dimensions": p.get_dimensions(p.default_model),
            })
        return results


@lru_cache
def get_embedding_registry() -> EmbeddingProviderRegistry:
    """Return singleton instance of EmbeddingProviderRegistry."""
    return EmbeddingProviderRegistry()
