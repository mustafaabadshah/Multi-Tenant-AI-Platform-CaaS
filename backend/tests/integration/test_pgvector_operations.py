"""Integration tests verifying real pgvector operations, cosine distance (<=>), and dimensional safety."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, DocumentChunk, KnowledgeBase
from app.vectorstores.base import VectorPoint, VectorStoreFilter
from app.vectorstores.pgvector_store import PgVectorStore


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_real_pgvector_insert_and_cosine_distance_ranking(pg_session: AsyncSession, pg_seed_tenants: dict):
    """Verify that real numeric vectors (384 dimensions) are stored and ranked via pgvector <=> operator."""
    tenant_a = pg_seed_tenants["tenant_a"]
    pg_store = PgVectorStore(pg_session)

    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Vector Specs",
        status="ACTIVE",
    )
    pg_session.add(kb)
    await pg_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="system_architecture.pdf",
        safe_filename="system_architecture.pdf",
        file_path="/tenants/doc_vec",
        mime_type="application/pdf",
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
        content="Microservices communication over gRPC and protobuf protocols.",
        page_number=1,
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=1,
        content="Frontend rendering utilizing Next.js Server Components and streaming SSR.",
        page_number=2,
    )
    pg_session.add_all([chunk1, chunk2])
    await pg_session.commit()

    # Create 384-dimensional test vectors
    # Point 1: near [1.0, 0.0, ...]
    v1 = [1.0] + [0.0] * 383
    # Point 2: near [0.0, 1.0, ...]
    v2 = [0.0, 1.0] + [0.0] * 382

    p1 = VectorPoint(
        id=str(chunk1.id),
        vector=v1,
        payload={"document_id": str(doc.id), "embedding_version": 1},
        dimensions=384,
    )
    p2 = VectorPoint(
        id=str(chunk2.id),
        vector=v2,
        payload={"document_id": str(doc.id), "embedding_version": 1},
        dimensions=384,
    )

    upserted = await pg_store.upsert([p1, p2], tenant_a.id, kb.id)
    assert upserted == 2
    await pg_session.commit()

    # Search with query vector very close to v2 [0.0, 0.99, ...]
    query_v = [0.0, 0.99] + [0.0] * 382
    filter_criteria = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[kb.id],
        embedding_version=1,
        expected_dimensions=384,
    )

    results = await pg_store.search(query_v, filter_criteria, top_k=2)
    assert len(results) == 2
    # chunk2 must be top result due to minimal cosine distance
    assert results[0].chunk_id == chunk2.id
    assert results[0].retrieval_source == "semantic"
    assert results[1].chunk_id == chunk1.id


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_pgvector_rejects_dimension_mismatch(pg_session: AsyncSession, pg_seed_tenants: dict):
    """Verify that attempting to query or insert incompatible vector dimensions raises ValueError."""
    tenant_a = pg_seed_tenants["tenant_a"]
    pg_store = PgVectorStore(pg_session)
    kb_id = uuid.uuid4()

    # Attempting to upsert vector with length != declared dimensions
    p_invalid = VectorPoint(
        id=str(uuid.uuid4()),
        vector=[0.1, 0.2, 0.3],  # 3 dims
        payload={"document_id": str(uuid.uuid4())},
        dimensions=384,  # expects 384
    )

    with pytest.raises(ValueError, match="Vector dimension mismatch"):
        await pg_store.upsert([p_invalid], tenant_a.id, kb_id)

    # Attempting to search with wrong dimensions
    filter_criteria = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[kb_id],
        expected_dimensions=384,
    )
    with pytest.raises(ValueError, match="Query vector dimension mismatch"):
        await pg_store.search([0.1, 0.2], filter_criteria)
