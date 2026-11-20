"""Integration tests verifying native PostgreSQL Full-Text Search (to_tsvector, plainto_tsquery, ts_rank_cd)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, DocumentChunk, KnowledgeBase
from app.vectorstores.base import VectorStoreFilter
from app.vectorstores.fts_store import PostgresFTSStore


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_native_postgresql_fts_query_and_ranking(pg_session: AsyncSession, pg_seed_tenants: dict):
    """Verify native PostgreSQL FTS ranking using ts_rank_cd against real document chunks."""
    tenant_a = pg_seed_tenants["tenant_a"]
    fts_store = PostgresFTSStore(pg_session)

    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Postgres FTS KB",
        status="ACTIVE",
    )
    pg_session.add(kb)
    await pg_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="cloud_infrastructure.txt",
        safe_filename="cloud_infrastructure.txt",
        file_path="/storage/cloud_infra.txt",
        mime_type="text/plain",
        status="COMPLETED",
    )
    pg_session.add(doc)
    await pg_session.flush()

    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        content="Kubernetes cluster orchestration on AWS with Terraform automation and auto-scaling pods.",
        page_number=1,
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=1,
        content="PostgreSQL high availability replication using Patroni, Raft consensus, and pgBouncer pooling.",
        page_number=2,
    )
    pg_session.add_all([chunk1, chunk2])
    await pg_session.commit()

    # Search for "PostgreSQL replication"
    filt = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[kb.id],
    )
    results = await fts_store.search_lexical("PostgreSQL replication", filt, top_k=5)

    assert len(results) >= 1
    assert results[0].chunk_id == chunk2.id
    assert results[0].retrieval_source == "lexical"
    assert results[0].score > 0.0, "PostgreSQL ts_rank_cd must return positive relevance score"


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_native_postgresql_fts_sql_injection_safety(pg_session: AsyncSession, pg_seed_tenants: dict):
    """Verify that malicious user input with SQL injection payloads does not break PostgreSQL FTS."""
    tenant_a = pg_seed_tenants["tenant_a"]
    fts_store = PostgresFTSStore(pg_session)

    kb_id = uuid.uuid4()
    filt = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[kb_id],
    )

    injection_queries = [
        "'; DROP TABLE documents; --",
        "vacation' OR 1=1 --",
        "' UNION SELECT * FROM users --",
        "kubernetes & | ! : * ( )",
    ]

    for malicious_q in injection_queries:
        # Must execute cleanly via parameter binding without exception or syntax error
        res = await fts_store.search_lexical(malicious_q, filt, top_k=5)
        assert isinstance(res, list)
