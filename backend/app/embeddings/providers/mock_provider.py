"""Deterministic mock embedding provider for fast, reliable unit and integration tests."""

import hashlib
import math
from typing import Optional

from app.embeddings.base import (
    BatchEmbeddingResult,
    EmbeddingProvider,
    EmbeddingProviderConfig,
    EmbeddingResult,
)


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic mock provider generating reproducible unit-normalized vectors."""

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return "mock-embedding-v1"

    @property
    def supported_models(self) -> list[str]:
        return ["mock-embedding-v1", "mock-embedding-small", "mock-embedding-large"]

    def get_dimensions(self, model_name: Optional[str] = None) -> int:
        if model_name == "mock-embedding-small":
            return 384
        if model_name == "mock-embedding-large":
            return 3072
        return 1536

    def _generate_vector(self, text: str, dimensions: int) -> list[float]:
        """Produce a deterministic, L2-normalized float vector from text hash."""
        vec: list[float] = []
        for i in range(dimensions):
            h = hashlib.sha256(f"{text}::{i}".encode("utf-8")).digest()
            val = (int.from_bytes(h[:4], "big") / (2**32)) * 2.0 - 1.0
            vec.append(val)

        # L2-normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    async def embed_text(self, text: str, config: EmbeddingProviderConfig) -> EmbeddingResult:
        dims = config.dimensions or self.get_dimensions(config.model_name)
        vec = self._generate_vector(text, dims)
        token_estimate = max(1, len(text.split()))
        return EmbeddingResult(
            vector=vec,
            dimensions=dims,
            tokens_used=token_estimate,
            model=config.model_name or self.default_model,
        )

    async def embed_batch(
        self, texts: list[str], config: EmbeddingProviderConfig
    ) -> BatchEmbeddingResult:
        dims = config.dimensions or self.get_dimensions(config.model_name)
        vectors: list[list[float]] = []
        total_tokens = 0
        for t in texts:
            vec = self._generate_vector(t, dims)
            vectors.append(vec)
            total_tokens += max(1, len(t.split()))

        return BatchEmbeddingResult(
            embeddings=vectors,
            total_tokens=total_tokens,
            model=config.model_name or self.default_model,
            dimensions=dims,
        )

    async def validate_configuration(self, config: EmbeddingProviderConfig) -> bool:
        return True

    async def check_health(self) -> bool:
        return True
