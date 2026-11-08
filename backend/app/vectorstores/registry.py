"""Registry for resolving vector store adapters."""

import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.vectorstores.base import VectorStore
from app.vectorstores.fts_store import PostgresFTSStore
from app.vectorstores.pgvector_store import PgVectorStore
from app.vectorstores.qdrant_store import QdrantVectorStore

logger = logging.getLogger("mmaip.vectorstores.registry")


class VectorStoreRegistry:
    """Registry providing factory methods for vector store instances."""

    @staticmethod
    def get_store(
        store_type: Optional[str],
        session: Optional[AsyncSession] = None,
        custom_endpoint: Optional[str] = None,
        custom_api_key: Optional[str] = None,
        custom_collection_name: Optional[str] = None,
    ) -> VectorStore:
        """Instantiate the requested vector store adapter."""
        st = (store_type or settings.DEFAULT_VECTOR_STORE).lower()

        if st in ("pgvector", "postgresql_pgvector", "postgres"):
            if session is None:
                raise ValueError("AsyncSession is required for PgVectorStore")
            return PgVectorStore(session)

        if st in ("qdrant",):
            return QdrantVectorStore(
                url=custom_endpoint or settings.QDRANT_URL,
                api_key=custom_api_key or settings.QDRANT_API_KEY,
                collection_name=custom_collection_name or getattr(settings, "QDRANT_COLLECTION_NAME", "mmaip_knowledge_chunks"),
            )

        if st in ("fts", "full_text_search", "lexical"):
            if session is None:
                raise ValueError("AsyncSession is required for PostgresFTSStore")
            return PostgresFTSStore(session)

        # Default fallback to pgvector if session available, else FTS
        if session:
            return PgVectorStore(session)
        return QdrantVectorStore(
            collection_name=custom_collection_name or getattr(settings, "QDRANT_COLLECTION_NAME", "mmaip_knowledge_chunks")
        )

    @staticmethod
    def list_available_stores() -> list[dict[str, Any]]:
        """List registered vector stores with capabilities."""
        return [
            {
                "type": "pgvector",
                "name": "PostgreSQL pgvector",
                "description": "Native vector similarity search integrated into PostgreSQL database.",
                "requires_embeddings": True,
                "supports_hybrid": True,
                "default_metric": "cosine",
            },
            {
                "type": "qdrant",
                "name": "Qdrant Vector Database",
                "description": "High-performance independent vector database with payload indexing.",
                "requires_embeddings": True,
                "supports_hybrid": True,
                "default_metric": "cosine",
            },
            {
                "type": "fts",
                "name": "PostgreSQL Full-Text Search (FTS)",
                "description": "Fast keyword/lexical search without vector database or embeddings.",
                "requires_embeddings": False,
                "supports_hybrid": False,
                "default_metric": "ts_rank",
            },
        ]


def get_vector_store(
    store_type: Optional[str] = None,
    session: Optional[AsyncSession] = None,
    custom_endpoint: Optional[str] = None,
    custom_api_key: Optional[str] = None,
    custom_collection_name: Optional[str] = None,
) -> VectorStore:
    """Convenience factory function."""
    return VectorStoreRegistry.get_store(
        store_type,
        session=session,
        custom_endpoint=custom_endpoint,
        custom_api_key=custom_api_key,
        custom_collection_name=custom_collection_name,
    )
