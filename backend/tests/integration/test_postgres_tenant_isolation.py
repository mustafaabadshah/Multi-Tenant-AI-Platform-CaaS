"""Integration tests verifying strict multi-tenant isolation and department ACLs on real PostgreSQL."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, DocumentChunk, KnowledgeBase
from app.retrieval.authorization import RetrievalAuthorizer
from app.vectorstores.base import VectorStoreFilter
from app.vectorstores.fts_store import PostgresFTSStore


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_cross_tenant_isolation_on_real_postgresql(pg_session: AsyncSession, pg_seed_tenants: dict):
    """Verify that Tenant B cannot access Tenant A documents on real PostgreSQL even with matching queries."""
    tenant_a = pg_seed_tenants["tenant_a"]
    tenant_b = pg_seed_tenants["tenant_b"]
    fts_store = PostgresFTSStore(pg_session)

    # Tenant A KB & Document
    kb_a = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Tenant A Secret Docs",
        status="ACTIVE",
    )
    pg_session.add(kb_a)
    await pg_session.flush()

    doc_a = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_a.id,
        filename="classified_financials.txt",
        safe_filename="classified_financials.txt",
        file_path="/tenants/a/doc",
        mime_type="text/plain",
        status="COMPLETED",
    )
    pg_session.add(doc_a)
    await pg_session.flush()

    chunk_a = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb_a.id,
        document_id=doc_a.id,
        chunk_index=0,
        content="Confidential financial projection: Q4 net revenue of $50,000,000.",
        page_number=1,
    )
    pg_session.add(chunk_a)
    await pg_session.commit()

    # 1. Tenant B searches with exact keywords "net revenue"
    filt_b = VectorStoreFilter(
        tenant_id=tenant_b.id,
        knowledge_base_ids=[kb_a.id],  # Even if Tenant B tries to pass Tenant A's KB ID
    )
    results_b = await fts_store.search_lexical("net revenue", filt_b, top_k=5)
    assert len(results_b) == 0, "Cross-tenant leakage: Tenant B retrieved Tenant A's document chunk!"

    # 2. RetrievalAuthorizer on Tenant B must reject Tenant A's KB ID
    authorizer_b = RetrievalAuthorizer(pg_session, tenant_b.id)
    with pytest.raises(PermissionError, match="Unauthorized or non-existent knowledge bases"):
        await authorizer_b.validate_knowledge_bases([kb_a.id], user_department_id=None, is_admin=False)


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_department_isolation_on_real_postgresql(pg_session: AsyncSession, pg_seed_tenants: dict):
    """Verify that a user in Marketing cannot access an Engineering-restricted document in the same tenant."""
    tenant_a = pg_seed_tenants["tenant_a"]
    dept_eng = pg_seed_tenants["dept_a"]
    fts_store = PostgresFTSStore(pg_session)

    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Company Portal",
        status="ACTIVE",
    )
    pg_session.add(kb)
    await pg_session.flush()

    # Engineering-restricted document
    doc_eng = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        department_id=dept_eng.id,
        filename="kernel_source.txt",
        safe_filename="kernel_source.txt",
        file_path="/tenants/eng/kernel",
        mime_type="text/plain",
        status="COMPLETED",
    )
    pg_session.add(doc_eng)
    await pg_session.flush()

    chunk_eng = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc_eng.id,
        chunk_index=0,
        content="Linux kernel patch for memory management and TLB flush optimization.",
        page_number=1,
    )
    pg_session.add(chunk_eng)
    await pg_session.commit()

    # User in a different department (or None) searches
    other_dept_id = uuid.uuid4()
    filt_restricted = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[kb.id],
        user_department_id=other_dept_id,
        is_admin=False,
    )

    results = await fts_store.search_lexical("kernel patch memory", filt_restricted, top_k=5)
    assert len(results) == 0, "Department isolation failure: non-engineering user retrieved engineering chunk!"
