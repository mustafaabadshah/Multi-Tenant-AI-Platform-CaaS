"""Abstract base classes and dataclasses for the LLM provider system."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMMessage:
    """Chat completion message."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMStreamChunk:
    """Streamed response delta chunk."""
    content_delta: str
    finish_reason: Optional[str] = None


@dataclass
class LLMResponse:
    """Full chat completion response."""
    content: str
    model: str
    tokens_used: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    raw_response: dict[str, Any] = field(default_factory=dict)


class LLMException(Exception):
    """Base exception for all LLM provider errors."""
    pass


class LLMConnectionError(LLMException):
    """Raised when connection to LLM provider endpoint fails."""
    pass


class LLMTimeoutError(LLMException):
    """Raised when provider connection or streaming read times out."""
    pass


class LLMAuthenticationError(LLMException):
    """Raised when provider authentication or API key verification fails (HTTP 401/403)."""
    pass


class LLMRateLimitError(LLMException):
    """Raised when provider rate limit is exceeded (HTTP 429)."""
    pass


class LLMProviderError(LLMException):
    """Raised when provider returns an upstream server error (HTTP 5xx or unhandled status)."""
    pass


class LLMConfigurationError(LLMException):
    """Raised when provider configuration, model, or endpoint is invalid."""
    pass


@dataclass
class LLMConfig:
    """Configuration for an LLM generation call."""
    provider: str
    model: str = "auto"
    temperature: float = 0.7
    max_tokens: int = 1024
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout_seconds: int = 45
    extra_headers: dict[str, str] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract interface that every LLM provider must implement."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier (e.g. 'omniroute', 'openai', 'mock')."""
        pass

    @abstractmethod
    async def generate(self, messages: list[LLMMessage], config: LLMConfig) -> LLMResponse:
        """Generate a complete non-streaming chat response."""
        pass

    @abstractmethod
    async def generate_stream(
        self, messages: list[LLMMessage], config: LLMConfig
    ) -> AsyncIterator[LLMStreamChunk]:
        """Generate a streaming response yielding token chunks."""
        pass

    @abstractmethod
    async def validate_key(self, config: LLMConfig) -> bool:
        """Validate API key credentials with the external endpoint."""
        pass
