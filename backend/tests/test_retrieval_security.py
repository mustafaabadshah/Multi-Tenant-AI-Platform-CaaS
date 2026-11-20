"""Critical Security Tests: Multi-Tenant Isolation, Department Access Control, and Adversarial Scenarios."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.models.knowledge import Document, DocumentChunk, KnowledgeBase
from app.retrieval.service import RetrievalService
from app.vectorstores.base import VectorPoint, VectorStoreFilter
from app.vectorstores.pgvector_store import PgVectorStore


@pytest.mark.asyncio
async def test_cross_tenant_vector_isolation(db_session: AsyncSession, seed_data: dict):
    """Security Requirement 1: Tenant A cannot retrieve Tenant B's vectors."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]

    # 1. Create KB and document in Tenant B
    kb_b = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_b.id, name="Tenant B Secrets", status="ACTIVE")
    db_session.add(kb_b)
    await db_session.flush()

    doc_b = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        knowledge_base_id=kb_b.id,
        filename="b_confidential.txt",
        safe_filename="b_confidential.txt",
        file_path="/tenants/b/doc",
        mime_type="text/plain",
        status="COMPLETED",
    )
    db_session.add(doc_b)
    await db_session.flush()

    chunk_b = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        knowledge_base_id=kb_b.id,
        document_id=doc_b.id,
        chunk_index=0,
        content="Tenant B confidential strategy and trade secrets.",
    )
    db_session.add(chunk_b)
    await db_session.commit()

    # Index into vector store
    pg_store = PgVectorStore(db_session)
    await pg_store.upsert(
        [
            VectorPoint(
                id=str(chunk_b.id),
                vector=[0.8, 0.2, 0.0, 0.0],
                payload={"document_id": str(doc_b.id), "embedding_version": 1},
            )
        ],
        tenant_b.id,
        kb_b.id,
    )

    # 2. Tenant A attempts to search with Tenant A's tenant_id pointing to KB B
    filter_a = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[kb_b.id],
        embedding_version=1,
    )
    results = await pg_store.search([0.8, 0.2, 0.0, 0.0], filter_a, top_k=5)
    # MUST return 0 results
    assert len(results) == 0


@pytest.mark.asyncio
async def test_cross_tenant_fts_isolation(db_session: AsyncSession, seed_data: dict, client: AsyncClient):
    """Security Requirement 2: Tenant A cannot retrieve Tenant B's FTS results via API."""
    tenant_b = seed_data["tenant_b"]
    token_a = seed_data["token_a_owner"]

    # Create KB and document in Tenant B
    kb_b = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_b.id, name="KB B", status="ACTIVE")
    db_session.add(kb_b)
    await db_session.flush()

    doc_b = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        knowledge_base_id=kb_b.id,
        filename="financials.txt",
        safe_filename="financials.txt",
        file_path="/tenants/b/fin",
        mime_type="text/plain",
        status="COMPLETED",
    )
    db_session.add(doc_b)
    await db_session.flush()

    chunk_b = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        knowledge_base_id=kb_b.id,
        document_id=doc_b.id,
        chunk_index=0,
        content="Q4 net earnings and audit financials for Company B.",
    )
    db_session.add(chunk_b)
    await db_session.commit()

    # Tenant A attempts to search KB B using API with Tenant A's context
    response = await client.post(
        "/api/v1/retrieval/search",
        headers={
            "Authorization": f"Bearer {token_a}",
            "X-Tenant-ID": str(seed_data["tenant_a"].id),
        },
        json={
            "query": "financials",
            "knowledge_base_ids": [str(kb_b.id)],
            "mode": "lexical",
        },
    )
    # Must be 403 Forbidden because Tenant A does not own KB B
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_department_isolation_blocks_unauthorized_employee(db_session: AsyncSession, seed_data: dict):
    """Security Requirement 3: Employee cannot retrieve an unauthorized department's documents."""
    tenant_a = seed_data["tenant_a"]

    # 1. Create two departments in Tenant A: HR and Engineering
    hr_dept = Department(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Human Resources")
    eng_dept = Department(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Engineering")
    db_session.add_all([hr_dept, eng_dept])
    await db_session.flush()

    # 2. Create KB in Tenant A
    kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Company Portal", status="ACTIVE")
    db_session.add(kb)
    await db_session.flush()

    # 3. Create HR Document (restricted to HR department)
    hr_doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        department_id=hr_dept.id,
        access_level="department",
        filename="executive_salaries.txt",
        safe_filename="executive_salaries.txt",
        file_path="/tenants/hr",
        mime_type="text/plain",
        status="COMPLETED",
    )
    db_session.add(hr_doc)
    await db_session.flush()

    hr_chunk = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=hr_doc.id,
        chunk_index=0,
        content="Executive compensation and bonus structure for senior management.",
    )
    db_session.add(hr_chunk)
    await db_session.commit()

    # 4. Engineering employee searches
    eng_service = RetrievalService(
        session=db_session,
        tenant_id=tenant_a.id,
        user_id=seed_data["user_a_employee"].id,
        is_admin=False,
        user_department_id=eng_dept.id,  # In Engineering, NOT HR!
    )

    resp = await eng_service.search(
        query="compensation bonus",
        knowledge_base_ids=[kb.id],
        mode="lexical",
    )
    # Engineering employee MUST NOT see HR document!
    assert len(resp.results) == 0


@pytest.mark.asyncio
async def test_deleted_documents_excluded_from_retrieval(db_session: AsyncSession, seed_data: dict):
    """Security Requirement 5: User cannot retrieve chunks from deleted documents."""
    tenant_a = seed_data["tenant_a"]

    kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="General KB", status="ACTIVE")
    db_session.add(kb)
    await db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="deprecated_spec.txt",
        safe_filename="deprecated_spec.txt",
        file_path="/tenants/dep",
        mime_type="text/plain",
        status="DELETED",  # Mark document as DELETED!
    )
    db_session.add(doc)
    await db_session.flush()

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        content="Old deprecated protocol instructions from 2020.",
    )
    db_session.add(chunk)
    await db_session.commit()

    service = RetrievalService(
        session=db_session,
        tenant_id=tenant_a.id,
        is_admin=True,
    )
    resp = await service.search(
        query="deprecated protocol instructions",
        knowledge_base_ids=[kb.id],
        mode="lexical",
    )
    # Deleted document chunks MUST be excluded
    assert len(resp.results) == 0


@pytest.mark.asyncio
async def test_hybrid_retrieval_does_not_reintroduce_unauthorized_candidates(db_session: AsyncSession, seed_data: dict):
    """Security Requirement 10: Hybrid RRF fusion cannot reintroduce unauthorized candidates."""
    tenant_a = seed_data["tenant_a"]
    hr_dept = Department(id=uuid.uuid4(), tenant_id=tenant_a.id, name="HR Dept")
    eng_dept = Department(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Engineering Dept")
    db_session.add_all([hr_dept, eng_dept])
    await db_session.flush()

    kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Dual Search KB", status="ACTIVE")
    db_session.add(kb)
    await db_session.flush()

    from app.repositories.retrieval_repository import RetrievalRepository
    ret_repo = RetrievalRepository(db_session, tenant_a.id)
    await ret_repo.update_config(
        kb.id,
        embedding_provider="mock",
        embedding_model="mock-embedding-v1",
        embedding_dimensions=4,
    )
    await db_session.commit()

    # Create HR document
    doc_hr = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        department_id=hr_dept.id,
        access_level="department",
        filename="hr_secret.txt",
        safe_filename="hr_secret.txt",
        file_path="/tenants/hr_secret",
        mime_type="text/plain",
        status="COMPLETED",
    )
    db_session.add(doc_hr)
    await db_session.flush()

    chunk_hr = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc_hr.id,
        chunk_index=0,
        content="Hybrid secret HR review notes.",
    )
    db_session.add(chunk_hr)
    await db_session.commit()

    # Index into pgvector store
    pg_store = PgVectorStore(db_session)
    await pg_store.upsert(
        [
            VectorPoint(
                id=str(chunk_hr.id),
                vector=[0.5, 0.5, 0.0, 0.0],
                payload={
                    "document_id": str(doc_hr.id),
                    "department_id": str(hr_dept.id),
                    "embedding_version": 1,
                },
            )
        ],
        tenant_a.id,
        kb.id,
    )

    # Search in hybrid mode as Engineering employee
    service = RetrievalService(
        session=db_session,
        tenant_id=tenant_a.id,
        user_id=seed_data["user_a_employee"].id,
        is_admin=False,
        user_department_id=eng_dept.id,
    )
    resp = await service.search(
        query="Hybrid secret HR review notes",
        knowledge_base_ids=[kb.id],
        mode="hybrid",
    )
    # Candidate MUST NOT leak through hybrid fusion!
    assert len(resp.results) == 0
