"""Lightweight CPU-first Semantic Embedding Provider for all-MiniLM-L6-v2."""

import logging
import os
from typing import Any, Optional

from app.embeddings.base import (
    BatchEmbeddingResult,
    EmbeddingProvider,
    EmbeddingProviderConfig,
    EmbeddingResult,
)

logger = logging.getLogger("mmaip.embeddings.sentence_transformer")


class SentenceTransformerProvider(EmbeddingProvider):
    """Genuine semantic embedding provider optimized for CPU inference on constrained hardware.

    Supports 'sentence-transformers/all-MiniLM-L6-v2' (384 dimensions) using fastembed (ONNX runtime)
    or sentence-transformers. Operates with bounded memory and lazy model loading.
    """

    SUPPORTED_MODELS = {
        "sentence-transformers/all-MiniLM-L6-v2": 384,
        "all-MiniLM-L6-v2": 384,
        "BAAI/bge-small-en-v1.5": 384,
    }

    def __init__(self, cache_dir: Optional[str] = None):
        self._cache_dir = cache_dir or os.environ.get("MMAIP_MODEL_CACHE_DIR")
        self._models: dict[str, Any] = {}

    @property
    def provider_name(self) -> str:
        return "sentence-transformers"

    @property
    def default_model(self) -> str:
        return "sentence-transformers/all-MiniLM-L6-v2"

    @property
    def supported_models(self) -> list[str]:
        return list(self.SUPPORTED_MODELS.keys())

    def get_dimensions(self, model_name: Optional[str] = None) -> int:
        model = model_name or self.default_model
        return self.SUPPORTED_MODELS.get(model, 384)

    def _get_model(self, model_name: str) -> Any:
        """Lazily load the model on first inference request."""
        if model_name in self._models:
            return self._models[model_name]

        # 1. Try fastembed (ONNX runtime CPU-optimized engine)
        try:
            from fastembed import TextEmbedding
            # Normalize model name for fastembed
            fe_name = model_name
            if fe_name == "all-MiniLM-L6-v2":
                fe_name = "sentence-transformers/all-MiniLM-L6-v2"

            logger.info(f"Loading fastembed CPU model '{fe_name}' (cache: {self._cache_dir})")
            model = TextEmbedding(model_name=fe_name, cache_dir=self._cache_dir)
            self._models[model_name] = ("fastembed", model)
            return self._models[model_name]
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Could not load via fastembed: {e}. Trying sentence-transformers...")

        # 2. Try sentence_transformers fallback
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading sentence_transformers model '{model_name}' on CPU")
            model = SentenceTransformer(model_name, device="cpu", cache_folder=self._cache_dir)
            self._models[model_name] = ("sentence_transformers", model)
            return self._models[model_name]
        except ImportError:
            pass

        raise RuntimeError(
            "Neither 'fastembed' nor 'sentence-transformers' is available to run "
            f"semantic model '{model_name}'. Please ensure fastembed is installed."
        )

    async def embed_text(self, text: str, config: EmbeddingProviderConfig) -> EmbeddingResult:
        model_name = config.model_name or self.default_model
        backend_type, model = self._get_model(model_name)
        dims = self.get_dimensions(model_name)

        if not text.strip():
            return EmbeddingResult(
                vector=[0.0] * dims,
                dimensions=dims,
                tokens_used=0,
                model=model_name,
            )

        if backend_type == "fastembed":
            # fastembed embed returns a generator of numpy arrays
            embeddings = list(model.embed([text]))
            vec = [float(x) for x in embeddings[0]]
        else:
            emb = model.encode(text, convert_to_numpy=True)
            vec = [float(x) for x in emb]

        # Enforce exact dimension and finite values
        if len(vec) != dims:
            raise ValueError(f"Expected {dims} dimensions from {model_name}, got {len(vec)}")

        return EmbeddingResult(
            vector=vec,
            dimensions=dims,
            tokens_used=len(text.split()),
            model=model_name,
        )

    async def embed_batch(
        self, texts: list[str], config: EmbeddingProviderConfig
    ) -> BatchEmbeddingResult:
        model_name = config.model_name or self.default_model
        backend_type, model = self._get_model(model_name)
        dims = self.get_dimensions(model_name)

        if not texts:
            return BatchEmbeddingResult(
                embeddings=[],
                total_tokens=0,
                model=model_name,
                dimensions=dims,
            )

        # Batch execution with configurable batch size
        batch_size = config.batch_size or 32
        all_vectors: list[list[float]] = []

        if backend_type == "fastembed":
            # fastembed has built-in batching
            for emb_batch in model.embed(texts, batch_size=batch_size):
                all_vectors.append([float(x) for x in emb_batch])
        else:
            for i in range(0, len(texts), batch_size):
                chunk = texts[i : i + batch_size]
                batch_res = model.encode(chunk, batch_size=batch_size, convert_to_numpy=True)
                for vec in batch_res:
                    all_vectors.append([float(x) for x in vec])

        total_tokens = sum(len(t.split()) for t in texts)
        return BatchEmbeddingResult(
            embeddings=all_vectors,
            total_tokens=total_tokens,
            model=model_name,
            dimensions=dims,
        )

    async def validate_configuration(self, config: EmbeddingProviderConfig) -> bool:
        model_name = config.model_name or self.default_model
        if model_name not in self.SUPPORTED_MODELS:
            return False
        try:
            self._get_model(model_name)
            return True
        except Exception:
            return False

    async def check_health(self) -> bool:
        try:
            self._get_model(self.default_model)
            return True
        except Exception:
            return False
