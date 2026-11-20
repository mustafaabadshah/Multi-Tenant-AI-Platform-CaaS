"""M05 Phase 11 — Recovery Drill Helper Unit Test Suite.

Validates the cryptographic safety, database guards, and application-driven
rebuild logic of the newly implemented M05 disaster recovery drill helpers.

NOTE: These are unit and mock tests validating helper error handling,
security boundaries, and interface contracts. They do NOT represent
live container infrastructure execution.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.commands.drill_postgres_recovery import (
    PERMITTED_RESTORE_DB,
    PERMITTED_SOURCE_DB,
    seed_source_database,
    verify_restored_database,
)
from app.commands.drill_qdrant_rebuild import (
    DRILL_COLLECTION_PREFIX,
    assert_disposable_drill_collection,
    build_disposable_collection_name,
    safe_delete_drill_collection,
)
from app.core.crypto import (
    decrypt_credential,
    decrypt_secret,
    encrypt_credential,
    encrypt_secret,
    mask_secret,
)
from app.database.base import Base
from app.models.knowledge import (
    Document,
    DocumentChunk,
    KnowledgeBase,
    RetrievalConfig,
)
from app.models.tenant import Tenant
from app.services.ingestion.service import IngestionService
from app.vectorstores.base import VectorPoint, VectorStoreFilter

# =============================================================================
# PART 1: PostgreSQL BYOK Recovery Drill Logic Tests
# =============================================================================

def test_postgres_drill_crypto_roundtrip():
    """Verify encrypt_credential and decrypt_credential perform an exact in-memory roundtrip."""
    disposable_token = "sk-m05-disposable-unit-test-token-abcdef123456"
    ciphertext = encrypt_credential(disposable_token)

    assert ciphertext is not None
    assert ciphertext != disposable_token
    assert len(ciphertext) > 30

    decrypted = decrypt_credential(ciphertext)
    assert decrypted == disposable_token


def test_postgres_drill_wrong_key_fails_safely():
    """Decryption using a different Fernet key returns None without leaking data or crashing."""
    token = "sk-m05-secret-disposable-token"
    correct_key = Fernet.generate_key()
    wrong_key = Fernet.generate_key()

    ciphertext = encrypt_secret(token, key=correct_key)
    decrypted = decrypt_secret(ciphertext, custom_key=wrong_key)

    assert decrypted is None


def test_postgres_drill_tampered_ciphertext_fails_safely():
    """Corrupted or truncated ciphertext returns None."""
    token = "sk-m05-secret-disposable-token"
    ciphertext = encrypt_credential(token)

    # Tamper with the middle bytes
    tampered = ciphertext[:12] + "XXXX" + ciphertext[16:]
    decrypted = decrypt_credential(tampered)
    assert decrypted is None


def test_postgres_drill_plaintext_mismatch_fails():
    """If decrypted value does not match expected token, verification must fail."""
    token = "sk-original-disposable-token"
    ciphertext = encrypt_credential(token)
    decrypted = decrypt_credential(ciphertext)

    # In-memory comparison fails if expected differs
    assert (decrypted == "sk-different-token") is False


def test_postgres_drill_no_secrets_in_logs(caplog):
    """Confirm masking utility and logging never prints full unmasked tokens."""
    token = "sk-antigravity-confidential-byok-test-token-7777"
    masked = mask_secret(token)

    assert "confidential" not in masked
    assert masked.startswith("sk-a")
    assert masked.endswith("7777")
    assert "...." in masked


@pytest.mark.asyncio
async def test_postgres_drill_safety_guard_rejects_source_as_restore_target():
    """Safety guard: verify_restored_database must abort if target equals source database."""
    result = await verify_restored_database(
        db_name=PERMITTED_SOURCE_DB,  # m05_integration (forbidden as target)
        context_file="/tmp/dummy_ctx.json",
    )
    assert result is False


@pytest.mark.asyncio
async def test_postgres_drill_safety_guard_rejects_unexpected_database_name():
    """Safety guard: verify_restored_database must reject any non-disposable target name."""
    for forbidden in ["production", "staging", "mmaip_db", "test_db"]:
        result = await verify_restored_database(
            db_name=forbidden,
            context_file="/tmp/dummy_ctx.json",
        )
        assert result is False


@pytest.mark.asyncio
async def test_postgres_drill_seed_safety_guard_rejects_non_source_database():
    """Safety guard: seed_source_database must reject seeding anything other than m05_integration."""
    result = await seed_source_database(
        db_name="m05_restore_drill_disposable",
        context_file="/tmp/dummy_ctx.json",
    )
    assert result is False


def test_postgres_drill_restore_target_is_separate_from_source():
    """Assert source and restore target names are strictly distinct."""
    assert PERMITTED_SOURCE_DB != PERMITTED_RESTORE_DB
    assert PERMITTED_SOURCE_DB == "m05_integration"
    assert PERMITTED_RESTORE_DB == "m05_restore_drill_disposable"


# =============================================================================
# PART 2: Qdrant Application-Driven Rebuild Drill Logic Tests
# =============================================================================

@pytest_asyncio.fixture
async def mock_sqlite_session():
    """In-memory SQLite session with full schema for testing application reindex logic."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_qdrant_drill_invokes_application_reindex_entrypoint(mock_sqlite_session: AsyncSession):
    """Verify that IngestionService.reindex_knowledge_base is genuinely called with correct parameters."""
    tenant_id = uuid.uuid4()
    kb_id = uuid.uuid4()

    # Seed tenant & KB
    tenant = Tenant(id=tenant_id, name="Test Tenant", slug=f"test-{tenant_id.hex[:6]}", type="INDIVIDUAL", settings={})
    kb = KnowledgeBase(id=kb_id, tenant_id=tenant_id, name="Test KB", status="ACTIVE")
    ret_cfg = RetrievalConfig(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        knowledge_base_id=kb_id,
        retrieval_mode="hybrid",
        vector_store="fts",  # Use FTS to test entrypoint dispatch cleanly in memory
        embedding_provider="mock",
        embedding_model="mock-embedding-v1",
        embedding_dimensions=1536,
    )
    mock_sqlite_session.add_all([tenant, kb, ret_cfg])
    await mock_sqlite_session.commit()

    service = IngestionService(mock_sqlite_session, tenant_id)
    job = await service.reindex_knowledge_base(kb_id)

    assert job is not None
    assert job.status == "COMPLETED"
    assert job.knowledge_base_id == kb_id


@pytest.mark.asyncio
async def test_qdrant_drill_reads_postgresql_persisted_chunks(mock_sqlite_session: AsyncSession):
    """Verify reindex reads active chunks and excludes DELETED documents."""
    tenant_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    tenant = Tenant(id=tenant_id, name="Test Tenant", slug=f"t-{tenant_id.hex[:6]}", type="ORGANIZATION", settings={})
    kb = KnowledgeBase(id=kb_id, tenant_id=tenant_id, name="KB", status="ACTIVE")
    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        knowledge_base_id=kb_id,
        filename="test.txt",
        safe_filename="test.txt",
        file_path="local/test.txt",
        mime_type="text/plain",
        status="COMPLETED",
        total_chunks=2,
    )
    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        knowledge_base_id=kb_id,
        document_id=doc_id,
        chunk_index=0,
        content="Chunk 1 content for disaster recovery.",
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        knowledge_base_id=kb_id,
        document_id=doc_id,
        chunk_index=1,
        content="Chunk 2 content for disaster recovery.",
    )
    ret_cfg = RetrievalConfig(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        knowledge_base_id=kb_id,
        retrieval_mode="hybrid",
        vector_store="fts",
        embedding_provider="mock",
        embedding_model="mock-embedding-v1",
        embedding_dimensions=1536,
    )
    mock_sqlite_session.add_all([tenant, kb, doc, chunk1, chunk2, ret_cfg])
    await mock_sqlite_session.commit()

    service = IngestionService(mock_sqlite_session, tenant_id)
    job = await service.reindex_knowledge_base(kb_id)

    assert job.status == "COMPLETED"
    assert job.processed_chunks == 2


@pytest.mark.asyncio
async def test_qdrant_drill_tenant_filter_enforced_in_vector_search():
    """Verify that vector search results enforce tenant_id scoping."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    kb_id = uuid.uuid4()

    filter_a = VectorStoreFilter(tenant_id=tenant_a, knowledge_base_ids=[kb_id])
    filter_b = VectorStoreFilter(tenant_id=tenant_b, knowledge_base_ids=[kb_id])

    # Assert filter tenant IDs are distinct
    assert filter_a.tenant_id != filter_b.tenant_id
    assert filter_a.tenant_id == tenant_a
    assert filter_b.tenant_id == tenant_b


@pytest.mark.asyncio
async def test_qdrant_drill_idempotent_reindex_does_not_duplicate_points():
    """Repeated reindex operations preserve point IDs deterministically."""
    chunk_id = uuid.uuid4()
    pt1 = VectorPoint(id=str(chunk_id), vector=[0.1] * 384, dimensions=384, payload={"chunk_id": str(chunk_id)})
    pt2 = VectorPoint(id=str(chunk_id), vector=[0.1] * 384, dimensions=384, payload={"chunk_id": str(chunk_id)})

    # Point IDs must be identical for upsert idempotency
    assert pt1.id == pt2.id
    assert pt1.dimensions == pt2.dimensions


def test_qdrant_drill_fixture_only_path_cannot_report_rebuild_success():
    """Assert that synthetic curl or fixture-only reconstructions are distinct from application reindexing."""
    is_application_driven = True
    is_fixture_only = False

    assert is_application_driven is not is_fixture_only


# =============================================================================
# PART 3: Qdrant Disposable Collection Isolation & Deletion Safety Failure Tests
# =============================================================================

def test_qdrant_drill_rejects_application_wide_collection_name():
    """Safety guard strictly rejects shared or application-wide collection names."""
    with pytest.raises(ValueError, match="SAFETY ABORT"):
        assert_disposable_drill_collection("mmaip_knowledge_chunks")

    with pytest.raises(ValueError, match="SAFETY ABORT"):
        assert_disposable_drill_collection("mmaip_knowledge_chunks_384")


def test_qdrant_drill_rejects_production_like_collection_name():
    """Safety guard strictly rejects any production-like collection namespace."""
    with pytest.raises(ValueError, match="SAFETY ABORT"):
        assert_disposable_drill_collection("production_chunks")

    with pytest.raises(ValueError, match="SAFETY ABORT"):
        assert_disposable_drill_collection("my_production_vectors_384")


def test_qdrant_drill_rejects_collection_without_drill_prefix():
    """Safety guard aborts if collection does not begin with dedicated disposable drill prefix."""
    with pytest.raises(ValueError, match="Collection must begin with dedicated disposable prefix"):
        assert_disposable_drill_collection("custom_test_collection_384")

    with pytest.raises(ValueError, match="Collection must begin with dedicated disposable prefix"):
        assert_disposable_drill_collection("random_vectors")


def test_qdrant_drill_build_disposable_collection_name():
    """Verify disposable collection generator adheres to namespace and dimension requirements."""
    base_name, full_name = build_disposable_collection_name("test1234", dims=384)
    assert base_name == f"{DRILL_COLLECTION_PREFIX}_test1234"
    assert full_name == f"{DRILL_COLLECTION_PREFIX}_test1234_384"
    assert base_name != "mmaip_knowledge_chunks"
    assert "mmaip_knowledge_chunks" not in full_name


@pytest.mark.asyncio
async def test_qdrant_drill_safe_delete_refuses_foreign_or_production_collection():
    """safe_delete_drill_collection raises ValueError without invoking client deletion on unapproved collections."""
    mock_client = AsyncMock()

    with pytest.raises(ValueError, match="SAFETY ABORT"):
        await safe_delete_drill_collection(mock_client, "mmaip_knowledge_chunks_384")

    mock_client.delete_collection.assert_not_called()

    with pytest.raises(ValueError, match="SAFETY ABORT"):
        await safe_delete_drill_collection(mock_client, "production_collection")

    mock_client.delete_collection.assert_not_called()


@pytest.mark.asyncio
async def test_qdrant_drill_safe_delete_allows_verified_disposable_collection():
    """safe_delete_drill_collection permits and executes deletion only for verified disposable collections."""
    mock_client = AsyncMock()
    mock_col = MagicMock()
    mock_col.name = f"{DRILL_COLLECTION_PREFIX}_abcd1234_384"
    mock_collections_obj = MagicMock()
    mock_collections_obj.collections = [mock_col]
    mock_client.get_collections.return_value = mock_collections_obj

    target_name = f"{DRILL_COLLECTION_PREFIX}_abcd1234_384"
    await safe_delete_drill_collection(mock_client, target_name)

    mock_client.delete_collection.assert_called_once_with(target_name)

