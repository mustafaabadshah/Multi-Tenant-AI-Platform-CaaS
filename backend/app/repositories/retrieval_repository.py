"""Repository for RetrievalConfig, ChunkEmbedding, and Indexing lifecycle."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import encrypt_secret
from app.models.knowledge import (
    ChunkEmbedding,
    Document,
    DocumentChunk,
    EmbeddingJob,
    RetrievalConfig,
)
from app.repositories.base import TenantScopedRepository
from app.vectorstores.registry import get_vector_store


class RetrievalRepository(TenantScopedRepository[RetrievalConfig]):
    """Tenant-scoped repository for knowledge base retrieval and vector configurations."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(RetrievalConfig, session, tenant_id)

    async def get_by_kb_id(self, knowledge_base_id: uuid.UUID) -> Optional[RetrievalConfig]:
        """Fetch RetrievalConfig for a specific knowledge base."""
        stmt = select(RetrievalConfig).where(
            RetrievalConfig.tenant_id == self.tenant_id,
            RetrievalConfig.knowledge_base_id == knowledge_base_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_or_create_config(self, knowledge_base_id: uuid.UUID) -> RetrievalConfig:
        """Fetch or initialize default RetrievalConfig for a knowledge base."""
        existing = await self.get_by_kb_id(knowledge_base_id)
        if existing:
            return existing

        new_config = RetrievalConfig(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            knowledge_base_id=knowledge_base_id,
            retrieval_mode=settings.DEFAULT_RETRIEVAL_MODE,
            vector_store=settings.DEFAULT_VECTOR_STORE,
            embedding_provider=settings.DEFAULT_EMBEDDING_PROVIDER,
            embedding_model=settings.DEFAULT_EMBEDDING_MODEL,
            embedding_dimensions=settings.DEFAULT_EMBEDDING_DIMENSIONS,
            similarity_metric="cosine",
            top_k=8,
            rrf_k=settings.RRF_K_CONSTANT,
            rerank_enabled=settings.RERANKING_ENABLED_DEFAULT,
            embedding_version=1,
            settings_json={},
        )
        self.session.add(new_config)
        await self.session.flush()
        return new_config

    async def update_config(
        self,
        knowledge_base_id: uuid.UUID,
        **kwargs: Any,
    ) -> RetrievalConfig:
        """Update knowledge base retrieval settings. Encrypts API key if provided."""
        config = await self.get_or_create_config(knowledge_base_id)

        # Handle API key encryption if provided
        if "api_key" in kwargs:
            raw_key = kwargs.pop("api_key")
            if raw_key:
                config.encrypted_api_key = encrypt_secret(raw_key)

        for key, value in kwargs.items():
            if hasattr(config, key) and value is not None:
                setattr(config, key, value)

        await self.session.flush()
        return config

    async def get_index_status(self, knowledge_base_id: uuid.UUID) -> dict[str, Any]:
        """Fetch comprehensive indexing metrics and vector store health for a KB."""
        config = await self.get_or_create_config(knowledge_base_id)
        version = config.embedding_version

        # Total active documents
        doc_count_stmt = select(func.count(Document.id)).where(
            Document.tenant_id == self.tenant_id,
            Document.knowledge_base_id == knowledge_base_id,
            Document.status != "DELETED",
        )
        total_documents = (await self.session.execute(doc_count_stmt)).scalar() or 0

        # Total chunks in KB
        chunk_count_stmt = select(func.count(DocumentChunk.id)).where(
            DocumentChunk.tenant_id == self.tenant_id,
            DocumentChunk.knowledge_base_id == knowledge_base_id,
        )
        total_chunks = (await self.session.execute(chunk_count_stmt)).scalar() or 0

        # Indexed embeddings for active version
        indexed_stmt = select(func.count(ChunkEmbedding.id)).where(
            ChunkEmbedding.tenant_id == self.tenant_id,
            ChunkEmbedding.knowledge_base_id == knowledge_base_id,
            ChunkEmbedding.embedding_version == version,
        )
        indexed_chunks = (await self.session.execute(indexed_stmt)).scalar() or 0

        # Latest activity
        latest_stmt = (
            select(ChunkEmbedding.created_at)
            .where(
                ChunkEmbedding.tenant_id == self.tenant_id,
                ChunkEmbedding.knowledge_base_id == knowledge_base_id,
            )
            .order_by(desc(ChunkEmbedding.created_at))
            .limit(1)
        )
        last_indexed_at = (await self.session.execute(latest_stmt)).scalar()

        # Vector store health check
        vstore = get_vector_store(config.vector_store, session=self.session)
        health = await vstore.check_health()

        return {
            "knowledge_base_id": str(knowledge_base_id),
            "retrieval_mode": config.retrieval_mode,
            "vector_store": config.vector_store,
            "embedding_provider": config.embedding_provider,
            "embedding_model": config.embedding_model,
            "embedding_dimensions": config.embedding_dimensions,
            "active_embedding_version": version,
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "indexed_chunks": indexed_chunks,
            "pending_chunks": max(0, total_chunks - indexed_chunks),
            "has_custom_api_key": bool(config.encrypted_api_key),
            "last_indexed_at": last_indexed_at.isoformat() if last_indexed_at else None,
            "vector_store_health": health,
        }

    async def create_embedding_job(
        self,
        knowledge_base_id: uuid.UUID,
        embedding_version: int,
        total_chunks: int,
        document_id: Optional[uuid.UUID] = None,
    ) -> EmbeddingJob:
        """Create a new tracked embedding or reindexing job."""
        job = EmbeddingJob(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            embedding_version=embedding_version,
            status="QUEUED",
            stage="QUEUED",
            total_chunks=total_chunks,
            processed_chunks=0,
            failed_chunks=0,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def list_embedding_jobs(
        self,
        knowledge_base_id: uuid.UUID,
        limit: int = 20,
    ) -> list[EmbeddingJob]:
        """List recent embedding/reindexing jobs for a knowledge base."""
        stmt = (
            select(EmbeddingJob)
            .where(
                EmbeddingJob.tenant_id == self.tenant_id,
                EmbeddingJob.knowledge_base_id == knowledge_base_id,
            )
            .order_by(desc(EmbeddingJob.created_at))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
