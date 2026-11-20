"""Reranking interface and implementations for post-retrieval candidate refinement."""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.vectorstores.base import VectorSearchResult

logger = logging.getLogger("mmaip.retrieval.reranking")


class Reranker(ABC):
    """Abstract interface for optional second-stage candidate rerankers."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[VectorSearchResult],
        top_k: int = 8,
    ) -> list[VectorSearchResult]:
        """Rerank candidates based on deep cross-encoder or API scoring."""
        pass


class NoOpReranker(Reranker):
    """Default pass-through reranker preserving first-stage ranking order."""

    @property
    def name(self) -> str:
        return "none"

    async def rerank(
        self,
        query: str,
        candidates: list[VectorSearchResult],
        top_k: int = 8,
    ) -> list[VectorSearchResult]:
        return candidates[:top_k]


def get_reranker(provider_name: Optional[str] = None) -> Reranker:
    """Resolve configured reranker, defaulting to NoOp."""
    return NoOpReranker()
