"""Abstract interfaces and data structures for vector database adapters and FTS stores."""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class VectorPoint:
    """A point to be indexed in a vector store."""
    id: str  # Typically chunk UUID string
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)
    dimensions: Optional[int] = None


@dataclass
class VectorStoreFilter:
    """Mandatory tenant-scoped search filter."""
    tenant_id: uuid.UUID
    knowledge_base_ids: list[uuid.UUID]
    document_ids: Optional[list[uuid.UUID]] = None
    embedding_version: int = 1
    department_id: Optional[uuid.UUID] = None
    user_department_id: Optional[uuid.UUID] = None
    is_admin: bool = False
    expected_dimensions: Optional[int] = None


@dataclass
class VectorSearchResult:
    """Standardized search candidate returned by any vector store or FTS adapter."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    score: float
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    rank: int = 0
    document_title: Optional[str] = None
    page_number: Optional[int] = None
    heading_path: Optional[str] = None
    chunk_index: int = 0
    retrieval_source: str = "semantic"  # "semantic", "lexical", "hybrid"


class VectorStore(ABC):
    """Abstract vector database adapter interface."""

    @property
    @abstractmethod
    def store_name(self) -> str:
        """Identifier of the vector store ('pgvector', 'qdrant', 'fts')."""
        pass

    @abstractmethod
    async def upsert(
        self,
        points: list[VectorPoint],
        tenant_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
    ) -> int:
        """Upsert points into vector store with tenant scope."""
        pass

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        filter_criteria: VectorStoreFilter,
        top_k: int = 8,
    ) -> list[VectorSearchResult]:
        """Execute filtered vector similarity search."""
        pass

    @abstractmethod
    async def delete(
        self,
        chunk_ids: list[uuid.UUID],
        tenant_id: uuid.UUID,
    ) -> int:
        """Remove vectors for specific chunks."""
        pass

    @abstractmethod
    async def delete_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> int:
        """Remove all vectors associated with a document."""
        pass

    @abstractmethod
    async def check_health(self) -> dict[str, Any]:
        """Perform health/liveness check and return diagnostic information."""
        pass
