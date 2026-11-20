"""Abstract base classes and dataclasses for the embedding provider system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class EmbeddingResult:
    """Result of embedding a single text string."""
    vector: list[float]
    dimensions: int
    tokens_used: int = 0
    model: str = ""


@dataclass
class BatchEmbeddingResult:
    """Result of embedding a batch of text strings."""
    embeddings: list[list[float]]
    total_tokens: int = 0
    model: str = ""
    dimensions: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingProviderConfig:
    """Configuration passed to embedding provider execution."""
    provider_name: str
    model_name: str
    dimensions: int = 1536
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    batch_size: int = 32
    timeout_seconds: int = 30
    max_retries: int = 3


class EmbeddingProvider(ABC):
    """Abstract interface that every embedding provider must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'omniroute', 'openai', 'local', 'mock')."""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model name for this provider."""
        pass

    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        """List of recognized models for this provider."""
        pass

    @abstractmethod
    def get_dimensions(self, model_name: Optional[str] = None) -> int:
        """Return the vector dimensionality for the given model."""
        pass

    @abstractmethod
    async def embed_text(self, text: str, config: EmbeddingProviderConfig) -> EmbeddingResult:
        """Generate an embedding for a single text chunk."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: list[str], config: EmbeddingProviderConfig) -> BatchEmbeddingResult:
        """Generate embeddings for a list of text chunks in bounded batches."""
        pass

    @abstractmethod
    async def validate_configuration(self, config: EmbeddingProviderConfig) -> bool:
        """Verify API keys, endpoints, and dimensions with the external provider."""
        pass

    @abstractmethod
    async def check_health(self) -> bool:
        """Perform a quick capability/liveness check."""
        pass
