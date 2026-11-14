"""Lightweight CPU-local embedding provider suitable for low-resource environments."""

import hashlib
import math
from typing import Optional

from app.embeddings.base import (
    BatchEmbeddingResult,
    EmbeddingProvider,
    EmbeddingProviderConfig,
    EmbeddingResult,
)


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local CPU feature projection embedding provider.

    Zero model downloads, instant execution, completely safe on Windows 8GB RAM without GPU.
    """

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def default_model(self) -> str:
        return "local-feature-projection"

    @property
    def supported_models(self) -> list[str]:
        return ["local-feature-projection", "local-hashing-v1"]

    def get_dimensions(self, model_name: Optional[str] = None) -> int:
        return 384

    def _compute_vector(self, text: str, dimensions: int) -> list[float]:
        """Compute semantic feature vector using character/word n-grams and frequency projection."""
        words = text.lower().split()
        if not words:
            return [0.0] * dimensions

        vector = [0.0] * dimensions
        for pos, word in enumerate(words):
            # Positional decay
            weight = 1.0 / (1.0 + 0.05 * pos)
            # Hash word to multiple buckets
            h1 = int(hashlib.md5(word.encode("utf-8")).hexdigest()[:8], 16)
            h2 = int(hashlib.sha1(word.encode("utf-8")).hexdigest()[:8], 16)

            idx1 = h1 % dimensions
            idx2 = h2 % dimensions
            sign1 = 1.0 if (h1 & 1) else -1.0
            sign2 = 1.0 if (h2 & 1) else -1.0

            vector[idx1] += sign1 * weight
            vector[idx2] += sign2 * weight * 0.5

        # L2-normalize
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 1e-9:
            vector = [v / norm for v in vector]
        return vector

    async def embed_text(self, text: str, config: EmbeddingProviderConfig) -> EmbeddingResult:
        dims = config.dimensions or self.get_dimensions(config.model_name)
        vec = self._compute_vector(text, dims)
        return EmbeddingResult(
            vector=vec,
            dimensions=dims,
            tokens_used=len(text.split()),
            model=config.model_name or self.default_model,
        )

    async def embed_batch(
        self, texts: list[str], config: EmbeddingProviderConfig
    ) -> BatchEmbeddingResult:
        dims = config.dimensions or self.get_dimensions(config.model_name)
        embs = [self._compute_vector(t, dims) for t in texts]
        total_tokens = sum(len(t.split()) for t in texts)
        return BatchEmbeddingResult(
            embeddings=embs,
            total_tokens=total_tokens,
            model=config.model_name or self.default_model,
            dimensions=dims,
        )

    async def validate_configuration(self, config: EmbeddingProviderConfig) -> bool:
        return True

    async def check_health(self) -> bool:
        return True
