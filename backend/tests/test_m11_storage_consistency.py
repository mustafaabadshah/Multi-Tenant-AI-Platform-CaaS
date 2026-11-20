"""M11 storage consistency: upload compensation, delete ordering, failed
ingestion cleanup, and storage reconciliation.

All storage is a temporary local filesystem provider. No real S3, cloud,
LLM, or embedding provider is contacted.
"""

import shutil
import tempfile
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import (
    ChunkEmbedding,
    Document,
    DocumentChunk,
    KnowledgeBase,
)
from app.repositories.document_repository import DocumentRepository
from app.services.ingestion.service import IngestionService
from app.services.storage_reconciliation import reconcile_storage
from app.storage.local import LocalStorageProvider


@pytest.fixture
def storage():
    # Keep the base path short: Windows MAX_PATH is exceeded by pytest's deep
    # tmp_path prefix combined with the tenant/KB/document storage key.
    base_dir = Path(tempfile.mkdtemp(prefix="m11s-"))
    provider = LocalStorageProvider(base_dir=str(base_dir))
    try:
        yield provider
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


@pytest.fixture
async def kb_a(db_session: AsyncSession, seed_data: dict) -> KnowledgeBase:
    kb = KnowledgeBase(
        tenant_id=seed_data["tenant_a"].id,
        name=f"M11 Storage KB {uuid.uuid4().hex[:8]}",
        description="M11 storage consistency tests",
        status="ACTIVE",
    )
    db_session.add(kb)
    await db_session.commit()
    await db_session.refresh(kb)
    return kb


def _patch_ingestion_storage(monkeypatch, storage: LocalStorageProvider) -> None:
    monkeypatch.setattr(
        "app.services.ingestion.service.get_storage_provider", lambda: storage
    )


def _patch_documents_storage(monkeypatch, storage: LocalStorageProvider) -> None:
    monkeypatch.setattr(
        "app.api.v1.documents.get_storage_provider", lambda: storage
    )


async def _create_kb(
    session: AsyncSession, tenant_id: uuid.UUID, label: str = "M11 Storage KB"
) -> KnowledgeBase:
    kb = KnowledgeBase(
        tenant_id=tenant_id,
        name=f"{label} {uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    session.add(kb)
    await session.commit()
    await session.refresh(kb)
    return kb


async def _add_document(
    session: AsyncSession,
    storage: LocalStorageProvider,
    tenant_id: uuid.UUID,
    kb_id: uuid.UUID,
    filename: str,
    status: str = "QUEUED",
) -> tuple[Document, str]:
    doc_id = uuid.uuid4()
    key = storage.build_storage_key(
        tenant_id=str(tenant_id),
        knowledge_base_id=str(kb_id),
        document_id=str(doc_id),
        version_number=1,
        filename=filename,
    )
    document = Document(
        id=doc_id,
        tenant_id=tenant_id,
        knowledge_base_id=kb_id,
        filename=filename,
        safe_filename=filename,
        file_path=key,
        file_size=8,
        mime_type="text/plain",
        file_hash=uuid.uuid4().hex,
        status=status,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document, key


async def _upload_document(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    kb_id: uuid.UUID,
    filename: str,
    content: bytes,
):
    service = IngestionService(session, tenant_id)
    document, job, is_duplicate = await service.upload_document(
        knowledge_base_id=kb_id,
        filename=filename,
        content=content,
        mime_type="text/plain",
    )
    return service, document, job, is_duplicate


# ---------------------------------------------------------------------------
# 1. Upload compensation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upload_compensation_removes_object_when_db_write_fails(
    db_session: AsyncSession,
    seed_data: dict,
    kb_a: KnowledgeBase,
    storage: LocalStorageProvider,
    monkeypatch,
):
    tenant_id = seed_data["tenant_a"].id
    _patch_ingestion_storage(monkeypatch, storage)
    service = IngestionService(db_session, tenant_id)

    async def _fail_create_version(*args, **kwargs):
        raise RuntimeError("simulated database write failure")

    monkeypatch.setattr(DocumentRepository, "create_version", _fail_create_version)

    with pytest.raises(RuntimeError, match="upload persistence failed"):
        await service.upload_document(
            knowledge_base_id=kb_a.id,
            filename="compensate.txt",
            content=b"Unique content for compensation test.",
            mime_type="text/plain",
        )

    assert await storage.list_keys(str(tenant_id)) == []

    documents = (
        await db_session.execute(select(Document).where(Document.tenant_id == tenant_id))
    ).scalars().all()
    assert documents == []


# ---------------------------------------------------------------------------
# 2. Delete ordering and error surfacing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_delete_storage_failure_keeps_db_row_and_raises(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
    kb_a: KnowledgeBase,
    storage: LocalStorageProvider,
    monkeypatch,
):
    tenant = seed_data["tenant_a"]
    _patch_ingestion_storage(monkeypatch, storage)
    _doc, document, _job, _dup = await _upload_document(
        db_session,
        tenant.id,
        kb_a.id,
        "delete-failure.txt",
        b"Delete failure coverage.",
    )
    document_id = document.id
    file_path = document.file_path
    assert await storage.exists(str(tenant.id), file_path)

    async def _fail_delete(*args, **kwargs):
        raise RuntimeError("object store unavailable")

    monkeypatch.setattr(storage, "delete", _fail_delete)
    _patch_documents_storage(monkeypatch, storage)

    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant.id),
    }
    response = await client.delete(f"/api/v1/documents/{document_id}", headers=headers)
    assert response.status_code == 502

    stored = (
        await db_session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.tenant_id == tenant.id,
            )
        )
    ).scalars().first()
    assert stored is not None
    assert await storage.exists(str(tenant.id), file_path)


@pytest.mark.asyncio
async def test_delete_success_removes_db_row_and_object(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
    kb_a: KnowledgeBase,
    storage: LocalStorageProvider,
    monkeypatch,
):
    tenant = seed_data["tenant_a"]
    _patch_ingestion_storage(monkeypatch, storage)
    _doc, document, _job, _dup = await _upload_document(
        db_session,
        tenant.id,
        kb_a.id,
        "delete-success.txt",
        b"Delete success coverage.",
    )
    document_id = document.id
    file_path = document.file_path

    _patch_documents_storage(monkeypatch, storage)
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant.id),
    }
    response = await client.delete(f"/api/v1/documents/{document_id}", headers=headers)
    assert response.status_code == 204

    stored = (
        await db_session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.tenant_id == tenant.id,
            )
        )
    ).scalars().first()
    assert stored is None
    assert not await storage.exists(str(tenant.id), file_path)


# ---------------------------------------------------------------------------
# 3. Terminal ingestion failure cleanup
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_terminal_ingestion_failure_removes_partial_chunks_and_embeddings(
    db_session: AsyncSession,
    seed_data: dict,
    kb_a: KnowledgeBase,
    storage: LocalStorageProvider,
    monkeypatch,
):
    tenant_id = seed_data["tenant_a"].id
    _patch_ingestion_storage(monkeypatch, storage)
    service, document, job, _dup = await _upload_document(
        db_session,
        tenant_id,
        kb_a.id,
        "will-fail.txt",
        b"# Failure\n\nThis document will fail parsing.",
    )
    document_id = document.id
    job_id = job.id
    document_version_id = job.document_version_id

    job.max_retries = 0
    await db_session.commit()

    chunk = DocumentChunk(
        tenant_id=tenant_id,
        knowledge_base_id=kb_a.id,
        document_id=document_id,
        document_version_id=document_version_id,
        chunk_index=0,
        content="Partial chunk from an interrupted attempt.",
        character_count=45,
        token_count=9,
        chunk_hash=uuid.uuid4().hex,
        chunking_strategy="recursive",
        metadata_json={},
    )
    db_session.add(chunk)
    await db_session.flush()
    embedding = ChunkEmbedding(
        tenant_id=tenant_id,
        knowledge_base_id=kb_a.id,
        document_id=document_id,
        document_version_id=document_version_id,
        chunk_id=chunk.id,
        embedding_version=1,
        provider="mock",
        model="mock-embed",
        dimensions=4,
        content_hash=uuid.uuid4().hex,
        vector=None,
    )
    db_session.add(embedding)
    await db_session.commit()

    def _raise_parser(*args, **kwargs):
        raise RuntimeError("simulated parser failure")

    monkeypatch.setattr(service.parser_registry, "resolve_parser", _raise_parser)

    executed = await service.execute_job(job_id)
    assert executed.status == "FAILED"
    assert executed.stage == "FAILED"

    fresh_document = (
        await db_session.execute(
            select(Document).where(
                Document.id == document_id,
                Document.tenant_id == tenant_id,
            )
        )
    ).scalars().one()
    assert fresh_document.status == "FAILED"

    remaining_chunks = (
        await db_session.execute(
            select(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.tenant_id == tenant_id,
            )
        )
    ).scalars().all()
    remaining_embeddings = (
        await db_session.execute(
            select(ChunkEmbedding).where(
                ChunkEmbedding.document_id == document_id,
                ChunkEmbedding.tenant_id == tenant_id,
            )
        )
    ).scalars().all()
    assert remaining_chunks == []
    assert remaining_embeddings == []
    assert fresh_document.total_chunks == 0


# ---------------------------------------------------------------------------
# 4. Reconciliation
# ---------------------------------------------------------------------------
async def _seed_reconciliation_state(
    session: AsyncSession,
    storage: LocalStorageProvider,
    tenant_id: uuid.UUID,
    kb_id: uuid.UUID,
):
    missing_document, missing_key = await _add_document(
        session, storage, tenant_id, kb_id, "missing.txt"
    )
    present_document, present_key = await _add_document(
        session, storage, tenant_id, kb_id, "present.txt"
    )
    await storage.save(str(tenant_id), present_key, b"present object")

    orphan_key = storage.build_storage_key(
        tenant_id=str(tenant_id),
        knowledge_base_id=str(kb_id),
        document_id=str(uuid.uuid4()),
        version_number=1,
        filename="orphan.txt",
    )
    await storage.save(str(tenant_id), orphan_key, b"orphan object")
    return missing_document, missing_key, present_document, present_key, orphan_key


@pytest.mark.asyncio
async def test_reconciliation_dry_run_reports_missing_and_orphan_without_changes(
    db_session: AsyncSession,
    seed_data: dict,
    kb_a: KnowledgeBase,
    storage: LocalStorageProvider,
):
    tenant = seed_data["tenant_a"]
    (
        missing_document,
        _missing_key,
        present_document,
        _present_key,
        orphan_key,
    ) = await _seed_reconciliation_state(db_session, storage, tenant.id, kb_a.id)

    report = await reconcile_storage(db_session, storage, tenant_id=tenant.id)

    assert report["dry_run"] is True
    assert report["fix"] is False
    missing_ids = {item["document_id"] for item in report["missing_objects"]}
    assert str(missing_document.id) in missing_ids
    orphan_keys = {item["key"] for item in report["orphan_objects"]}
    assert orphan_key in orphan_keys
    assert report["fixed"]["documents_marked_failed"] == 0
    assert report["fixed"]["orphan_objects_deleted"] == 0

    await db_session.refresh(missing_document)
    await db_session.refresh(present_document)
    assert missing_document.status == "QUEUED"
    assert present_document.status == "QUEUED"
    assert await storage.exists(str(tenant.id), orphan_key)


@pytest.mark.asyncio
async def test_reconciliation_fix_marks_missing_documents_failed_only(
    db_session: AsyncSession,
    seed_data: dict,
    kb_a: KnowledgeBase,
    storage: LocalStorageProvider,
):
    tenant = seed_data["tenant_a"]
    (
        missing_document,
        _missing_key,
        present_document,
        _present_key,
        orphan_key,
    ) = await _seed_reconciliation_state(db_session, storage, tenant.id, kb_a.id)

    report = await reconcile_storage(db_session, storage, tenant_id=tenant.id, fix=True)

    await db_session.refresh(missing_document)
    await db_session.refresh(present_document)
    assert missing_document.status == "FAILED"
    assert (
        missing_document.metadata_json["storage_reconciliation"]["state"]
        == "OBJECT_MISSING"
    )
    assert present_document.status == "QUEUED"
    assert report["fixed"]["documents_marked_failed"] == 1
    assert report["fixed"]["orphan_objects_deleted"] == 0

    stored = (
        await db_session.execute(
            select(Document.id).where(Document.id == missing_document.id)
        )
    ).scalar_one_or_none()
    assert stored is not None
    assert await storage.exists(str(tenant.id), orphan_key)


@pytest.mark.asyncio
async def test_reconciliation_orphan_delete_requires_explicit_flag(
    db_session: AsyncSession,
    seed_data: dict,
    kb_a: KnowledgeBase,
    storage: LocalStorageProvider,
):
    tenant = seed_data["tenant_a"]
    (
        _missing_document,
        _missing_key,
        _present_document,
        present_key,
        orphan_key,
    ) = await _seed_reconciliation_state(db_session, storage, tenant.id, kb_a.id)

    first_report = await reconcile_storage(
        db_session, storage, tenant_id=tenant.id, fix=True, delete_orphans=False
    )
    assert first_report["fixed"]["orphan_objects_deleted"] == 0
    assert await storage.exists(str(tenant.id), orphan_key)

    second_report = await reconcile_storage(
        db_session, storage, tenant_id=tenant.id, fix=True, delete_orphans=True
    )
    assert second_report["fixed"]["orphan_objects_deleted"] == 1
    assert not await storage.exists(str(tenant.id), orphan_key)
    assert await storage.exists(str(tenant.id), present_key)


@pytest.mark.asyncio
async def test_reconciliation_is_tenant_scoped(
    db_session: AsyncSession,
    seed_data: dict,
    kb_a: KnowledgeBase,
    storage: LocalStorageProvider,
):
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    kb_b = await _create_kb(db_session, tenant_b.id, label="Tenant B Storage KB")

    (
        missing_a,
        _missing_a_key,
        _present_a,
        _present_a_key,
        orphan_a,
    ) = await _seed_reconciliation_state(db_session, storage, tenant_a.id, kb_a.id)
    (
        missing_b,
        _missing_b_key,
        _present_b,
        present_b_key,
        orphan_b,
    ) = await _seed_reconciliation_state(db_session, storage, tenant_b.id, kb_b.id)

    report = await reconcile_storage(
        db_session,
        storage,
        tenant_id=tenant_a.id,
        fix=True,
        delete_orphans=True,
    )

    assert report["tenant_scope"] == str(tenant_a.id)
    assert {row["tenant_id"] for row in report["tenant_results"]} == {str(tenant_a.id)}
    assert not await storage.exists(str(tenant_a.id), orphan_a)
    assert await storage.exists(str(tenant_b.id), orphan_b)
    assert await storage.exists(str(tenant_b.id), present_b_key)

    await db_session.refresh(missing_a)
    await db_session.refresh(missing_b)
    assert missing_a.status == "FAILED"
    assert missing_b.status == "QUEUED"

    # A later tenant-B run must not touch tenant A and must clean only tenant B.
    tenant_b_report = await reconcile_storage(
        db_session,
        storage,
        tenant_id=tenant_b.id,
        fix=True,
        delete_orphans=True,
    )
    assert {row["tenant_id"] for row in tenant_b_report["tenant_results"]} == {
        str(tenant_b.id)
    }
    assert not await storage.exists(str(tenant_b.id), orphan_b)
    await db_session.refresh(missing_b)
    assert missing_b.status == "FAILED"
    await db_session.refresh(missing_a)
    assert missing_a.status == "FAILED"
