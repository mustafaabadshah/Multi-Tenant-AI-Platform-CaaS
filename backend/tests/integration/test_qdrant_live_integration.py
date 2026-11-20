"""Integration tests for live Qdrant vector database, payload filtering, and dimension separation."""

import os
import uuid

import pytest
import pytest_asyncio

from app.vectorstores.base import VectorPoint, VectorStoreFilter
from app.vectorstores.qdrant_store import HAVE_QDRANT, QdrantVectorStore

QDRANT_TEST_URL = os.environ.get("M05_QDRANT_TEST_URL", "http://127.0.0.1:6333")


async def is_qdrant_online() -> bool:
    """Check whether Qdrant test instance is online and reachable."""
    if not HAVE_QDRANT:
        return False
    try:
        from qdrant_client import AsyncQdrantClient

        client = AsyncQdrantClient(url=QDRANT_TEST_URL, timeout=3)
        await client.get_collections()
        await client.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def qdrant_available():
    import asyncio

    online = asyncio.run(is_qdrant_online())
    if not online:
        pytest.skip(
            f"Live Qdrant vector database is NOT reachable at {QDRANT_TEST_URL}. "
            "To execute: start the isolated M05 Qdrant container with `docker compose -f docker-compose.m05-qdrant.yml up -d`."
        )
    return True


@pytest_asyncio.fixture
async def qdrant_store(qdrant_available):
    store = QdrantVectorStore(
        url=QDRANT_TEST_URL,
        collection_name=f"test_m05_{uuid.uuid4().hex[:8]}",
    )
    yield store
    # Cleanup created collections
    try:
        client = store._get_client()
        cols = await client.get_collections()
        for c in cols.collections:
            if c.name.startswith(store.collection_name):
                await client.delete_collection(c.name)
        await client.close()
    except Exception:
        pass


@pytest.mark.qdrant_integration
@pytest.mark.asyncio
async def test_qdrant_service_connectivity_and_health(qdrant_store: QdrantVectorStore):
    """Verify live Qdrant service health check."""
    health = await qdrant_store.check_health()
    assert health["status"] == "healthy"
    assert health["store"] == "qdrant"
    assert "collection_count" in health


@pytest.mark.qdrant_integration
@pytest.mark.asyncio
async def test_qdrant_collection_creation_and_dimension_isolation(qdrant_store: QdrantVectorStore):
    """Verify that vector spaces are strictly isolated by dimensionality ({collection}_{dims})."""
    tenant_id = uuid.uuid4()
    kb_id = uuid.uuid4()

    # Space 1: 384 dimensions
    p_384 = VectorPoint(
        id=str(uuid.uuid4()),
        vector=[0.1] * 384,
        payload={"document_id": str(uuid.uuid4()), "embedding_version": 1},
        dimensions=384,
    )
    await qdrant_store.upsert([p_384], tenant_id, kb_id)

    # Space 2: 4 dimensions
    p_4 = VectorPoint(
        id=str(uuid.uuid4()),
        vector=[1.0, 0.0, 0.0, 0.0],
        payload={"document_id": str(uuid.uuid4()), "embedding_version": 1},
        dimensions=4,
    )
    await qdrant_store.upsert([p_4], tenant_id, kb_id)

    client = qdrant_store._get_client()
    cols = await client.get_collections()
    col_names = {c.name for c in cols.collections}

    assert f"{qdrant_store.collection_name}_384" in col_names
    assert f"{qdrant_store.collection_name}_4" in col_names


@pytest.mark.qdrant_integration
@pytest.mark.asyncio
async def test_qdrant_upsert_and_filtered_search(qdrant_store: QdrantVectorStore):
    """Verify 384-dimensional vector upsert and nearest neighbor search in Qdrant."""
    tenant_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    cid1 = uuid.uuid4()
    cid2 = uuid.uuid4()

    v1 = [1.0] + [0.0] * 383
    v2 = [0.0, 1.0] + [0.0] * 382

    p1 = VectorPoint(
        id=str(cid1),
        vector=v1,
        payload={"document_id": str(doc_id), "content": "Retrieval Augmented Generation with LLMs", "embedding_version": 1},
        dimensions=384,
    )
    p2 = VectorPoint(
        id=str(cid2),
        vector=v2,
        payload={"document_id": str(doc_id), "content": "Database sharding and replication architectures", "embedding_version": 1},
        dimensions=384,
    )

    upserted = await qdrant_store.upsert([p1, p2], tenant_id, kb_id)
    assert upserted == 2

    # Query with vector close to v1
    query_v = [0.98] + [0.0] * 383
    filt = VectorStoreFilter(
        tenant_id=tenant_id,
        knowledge_base_ids=[kb_id],
        embedding_version=1,
        expected_dimensions=384,
    )

    results = await qdrant_store.search(query_v, filt, top_k=2)
    assert len(results) == 2
    assert results[0].chunk_id == cid1
    assert "Retrieval Augmented Generation" in results[0].content


@pytest.mark.qdrant_integration
@pytest.mark.asyncio
async def test_qdrant_cross_tenant_payload_isolation(qdrant_store: QdrantVectorStore):
    """Verify that Tenant B cannot retrieve Tenant A vectors even with identical query vectors."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    kb_a = uuid.uuid4()

    v = [0.5] * 384
    p = VectorPoint(
        id=str(uuid.uuid4()),
        vector=v,
        payload={"document_id": str(uuid.uuid4()), "content": "Confidential Tenant A Strategy", "embedding_version": 1},
        dimensions=384,
    )
    await qdrant_store.upsert([p], tenant_a, kb_a)

    # Tenant B queries with exact same vector
    filt_b = VectorStoreFilter(
        tenant_id=tenant_b,
        knowledge_base_ids=[kb_a],
        embedding_version=1,
        expected_dimensions=384,
    )

    results_b = await qdrant_store.search(v, filt_b, top_k=5)
    assert len(results_b) == 0, "Cross-tenant leakage: Tenant B retrieved Tenant A's Qdrant vector!"


@pytest.mark.qdrant_integration
@pytest.mark.asyncio
async def test_qdrant_scoped_deletion(qdrant_store: QdrantVectorStore):
    """Verify that deleting points in Qdrant is strictly scoped by tenant_id."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    kb_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    p = VectorPoint(
        id=str(chunk_id),
        vector=[0.1] * 384,
        payload={"document_id": str(uuid.uuid4()), "embedding_version": 1},
        dimensions=384,
    )
    await qdrant_store.upsert([p], tenant_a, kb_id)

    # Tenant B attempts to delete Tenant A's chunk
    await qdrant_store.delete([chunk_id], tenant_id=tenant_b)

    # Tenant A must still be able to search and find its chunk
    filt_a = VectorStoreFilter(
        tenant_id=tenant_a,
        knowledge_base_ids=[kb_id],
        embedding_version=1,
        expected_dimensions=384,
    )
    results = await qdrant_store.search([0.1] * 384, filt_a, top_k=1)
    assert len(results) == 1, "Tenant B was improperly allowed to delete Tenant A's chunk!"

    # Now Tenant A deletes its own chunk
    await qdrant_store.delete([chunk_id], tenant_id=tenant_a)
    results_after = await qdrant_store.search([0.1] * 384, filt_a, top_k=1)
    assert len(results_after) == 0
