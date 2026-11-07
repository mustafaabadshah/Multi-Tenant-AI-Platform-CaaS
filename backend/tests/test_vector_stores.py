"""Unit and adapter tests for Vector Stores (FTS, pgvector, and Qdrant)."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, DocumentChunk, KnowledgeBase
from app.vectorstores.base import VectorPoint, VectorStoreFilter
from app.vectorstores.fts_store import PostgresFTSStore
from app.vectorstores.pgvector_store import PgVectorStore
from app.vectorstores.registry import VectorStoreRegistry


@pytest.mark.asyncio
async def test_vector_store_registry_listing():
    stores = VectorStoreRegistry.list_available_stores()
    store_types = {s["type"] for s in stores}
    assert "pgvector" in store_types
    assert "qdrant" in store_types
    assert "fts" in store_types


@pytest.mark.asyncio
async def test_fts_store_lexical_search_and_ranking(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    fts = PostgresFTSStore(db_session)

    # 1. Create Knowledge Base and Document with Chunks
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Engineering Docs",
        status="ACTIVE",
    )
    db_session.add(kb)
    await db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="leave_policy.txt",
        safe_filename="leave_policy.txt",
        file_path="/tenants/doc1",
        mime_type="text/plain",
        status="COMPLETED",
    )
    db_session.add(doc)
    await db_session.flush()

    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        content="Employees are entitled to 20 days of paid annual vacation leave per calendar year.",
        page_number=1,
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=1,
        content="Remote work setup guidelines for engineering teams including VPN and SSH keys.",
        page_number=2,
    )
    db_session.add_all([chunk1, chunk2])
    await db_session.commit()

    # 2. Search for "vacation leave"
    filter_criteria = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[kb.id],
    )
    results = await fts.search_lexical("vacation leave", filter_criteria, top_k=5)
    assert len(results) >= 1
    assert results[0].chunk_id == chunk1.id
    assert results[0].retrieval_source == "lexical"
    assert "annual vacation leave" in results[0].content


@pytest.mark.asyncio
async def test_pgvector_store_upsert_and_similarity_ranking(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    pg_store = PgVectorStore(db_session)

    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Product Specs",
        status="ACTIVE",
    )
    db_session.add(kb)
    await db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="specs.md",
        safe_filename="specs.md",
        file_path="/tenants/specs",
        mime_type="text/markdown",
        status="COMPLETED",
    )
    db_session.add(doc)
    await db_session.flush()

    chunk1_id = uuid.uuid4()
    chunk2_id = uuid.uuid4()
    chunk1 = DocumentChunk(
        id=chunk1_id,
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        content="Antigravity multi-tenant vector architecture specifications.",
    )
    chunk2 = DocumentChunk(
        id=chunk2_id,
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=1,
        content="Database backup procedures and disaster recovery checklists.",
    )
    db_session.add_all([chunk1, chunk2])
    await db_session.commit()

    # Upsert vector points
    # Query vector will be closer to chunk1 ([1.0, 0.0, 0.0, 0.0]) than chunk2 ([0.0, 1.0, 0.0, 0.0])
    points = [
        VectorPoint(
            id=str(chunk1_id),
            vector=[0.9, 0.1, 0.0, 0.0],
            payload={"document_id": str(doc.id), "embedding_version": 1},
        ),
        VectorPoint(
            id=str(chunk2_id),
            vector=[0.1, 0.9, 0.0, 0.0],
            payload={"document_id": str(doc.id), "embedding_version": 1},
        ),
    ]
    upserted = await pg_store.upsert(points, tenant_a.id, kb.id)
    assert upserted == 2

    # Query with vector [1.0, 0.0, 0.0, 0.0]
    filter_criteria = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[kb.id],
        embedding_version=1,
    )
    results = await pg_store.search([1.0, 0.0, 0.0, 0.0], filter_criteria, top_k=2)
    assert len(results) == 2
    # First candidate should be chunk1
    assert results[0].chunk_id == chunk1_id
    assert results[0].score > results[1].score


@pytest.mark.asyncio
async def test_pgvector_store_rejects_dimension_mismatch_on_upsert(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    pg_store = PgVectorStore(db_session)
    kb_id = uuid.uuid4()

    # Points with mismatched declared dimensions or differing lengths
    points = [
        VectorPoint(
            id=str(uuid.uuid4()),
            vector=[0.1, 0.2, 0.3],  # length 3
            dimensions=4,  # mismatch declared dimension
            payload={"embedding_version": 1},
        )
    ]
    with pytest.raises(ValueError, match="Vector dimension mismatch"):
        await pg_store.upsert(points, tenant_a.id, kb_id)


@pytest.mark.asyncio
async def test_pgvector_store_filters_by_dimension_on_search(db_session: AsyncSession, seed_data: dict):
    tenant_a = seed_data["tenant_a"]
    pg_store = PgVectorStore(db_session)

    kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Dim Isolation KB", status="ACTIVE")
    db_session.add(kb)
    await db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="dim_test.txt",
        safe_filename="dim_test.txt",
        file_path="/tenants/dim_test",
        mime_type="text/plain",
        status="COMPLETED",
    )
    db_session.add(doc)
    await db_session.flush()

    chunk_id = uuid.uuid4()
    chunk = DocumentChunk(
        id=chunk_id,
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=doc.id,
        chunk_index=0,
        content="Dimension isolation verification content.",
    )
    db_session.add(chunk)
    await db_session.commit()

    # Upsert a 4-dimensional vector with explicit dimensions=4
    points = [
        VectorPoint(
            id=str(chunk_id),
            vector=[0.5, 0.5, 0.5, 0.5],
            dimensions=4,
            payload={"document_id": str(doc.id), "embedding_version": 1},
        )
    ]
    await pg_store.upsert(points, tenant_a.id, kb.id)

    # 1. Search with matching 4-dim query and expected_dimensions=4 -> should find it
    filter_match = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[kb.id],
        embedding_version=1,
        expected_dimensions=4,
    )
    results = await pg_store.search([0.5, 0.5, 0.5, 0.5], filter_match, top_k=5)
    assert len(results) == 1
    assert results[0].chunk_id == chunk_id

    # 2. Search with expected_dimensions=384 -> should return empty (isolated)
    filter_mismatch = VectorStoreFilter(
        tenant_id=tenant_a.id,
        knowledge_base_ids=[kb.id],
        embedding_version=1,
        expected_dimensions=384,
    )
    # query_vector length must match expected_dimensions or search raises/returns empty
    mismatch_results = await pg_store.search([0.1] * 384, filter_mismatch, top_k=5)
    assert len(mismatch_results) == 0


def test_qdrant_store_isolates_collections_by_dimension():
    from app.vectorstores.qdrant_store import QdrantVectorStore

    store = QdrantVectorStore(collection_name="test_col")
    assert store._collection_for_dim(384) == "test_col_384"
    assert store._collection_for_dim(1536) == "test_col_1536"
    assert store._collection_for_dim(384) != store._collection_for_dim(1536)

