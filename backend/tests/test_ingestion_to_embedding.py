"""Integration tests for the ingestion-to-embedding pipeline and FTS-only mode."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeBase
from app.repositories.retrieval_repository import RetrievalRepository
from app.services.ingestion.service import IngestionService


@pytest.mark.asyncio
async def test_ingestion_pipeline_end_to_end_with_embeddings(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]

    # 1. Create Knowledge Base configured with mock embedding provider
    kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="AI Knowledge Base", status="ACTIVE")
    db_session.add(kb)
    await db_session.flush()

    ret_repo = RetrievalRepository(db_session, tenant_a.id)
    await ret_repo.update_config(
        kb.id,
        vector_store="pgvector",
        embedding_provider="mock",
        embedding_model="mock-embedding-v1",
        embedding_dimensions=1536,
    )
    await db_session.commit()

    # 2. Upload document via IngestionService
    ingestion_service = IngestionService(db_session, tenant_a.id)
    doc_content = (
        b"# Antigravity Platform\n\n"
        b"Antigravity is an enterprise AI knowledge platform providing vector search and hybrid retrieval.\n\n"
        b"## Multi-Tenant Security\n\n"
        b"Strict row-level isolation guarantees data privacy across organizations."
    )
    doc, job, is_dup = await ingestion_service.upload_document(
        knowledge_base_id=kb.id,
        filename="antigravity_overview.md",
        content=doc_content,
        mime_type="text/markdown",
    )
    assert not is_dup
    assert doc.status == "QUEUED"

    # 3. Execute the full ingestion & embedding pipeline
    completed_job = await ingestion_service.execute_job(job.id)
    assert completed_job.status == "COMPLETED"
    assert doc.status == "COMPLETED"
    assert doc.total_chunks > 0

    # 4. Verify index status shows indexed chunks
    status_info = await ret_repo.get_index_status(kb.id)
    assert status_info["total_chunks"] == doc.total_chunks
    assert status_info["indexed_chunks"] == doc.total_chunks
    assert status_info["pending_chunks"] == 0


@pytest.mark.asyncio
async def test_fts_only_mode_skips_embedding_generation(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]

    kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="FTS Only Manuals", status="ACTIVE")
    db_session.add(kb)
    await db_session.flush()

    ret_repo = RetrievalRepository(db_session, tenant_a.id)
    await ret_repo.update_config(
        kb.id,
        retrieval_mode="lexical",
        vector_store="fts",
    )
    await db_session.commit()

    ingestion_service = IngestionService(db_session, tenant_a.id)
    content = b"Simple operating system user instructions for local setup without any AI vectors."
    doc, job, _ = await ingestion_service.upload_document(
        knowledge_base_id=kb.id,
        filename="manual.txt",
        content=content,
        mime_type="text/plain",
    )

    completed_job = await ingestion_service.execute_job(job.id)
    assert completed_job.status == "COMPLETED"
    assert doc.status == "COMPLETED"

    # In FTS-only mode, indexed_chunks for vectors is 0 because no embeddings were generated
    status_info = await ret_repo.get_index_status(kb.id)
    assert status_info["vector_store"] == "fts"
    assert status_info["indexed_chunks"] == 0
