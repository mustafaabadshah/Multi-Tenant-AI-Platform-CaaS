"""M13.2 STO-1/STO-2: typed storage errors and reconciliation safety.

No real S3, cloud, network, or external storage is contacted. S3 behavior is
exercised through a fake ``aioboto3`` client; reconciliation uses an in-memory
storage provider and the test database.
"""

import sys
import uuid
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.commands import reconcile_storage as reconcile_command
from app.models.knowledge import Document, KnowledgeBase
from app.services.storage_reconciliation import reconcile_storage
from app.storage.base import (
    StorageError,
    StorageNotFoundError,
    StorageProvider,
    StorageUnavailableError,
)
from app.storage.s3 import S3StorageProvider


def _client_error(code: str, status: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": f"simulated {code}"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "HeadObject",
    )


@contextmanager
def _fake_aioboto3(client):
    session = MagicMock()
    client_context = AsyncMock()
    client_context.__aenter__.return_value = client
    client_context.__aexit__.return_value = False
    session.client.return_value = client_context

    module = MagicMock()
    module.Session.return_value = session
    with patch.dict(sys.modules, {"aioboto3": module}):
        yield


def _provider() -> S3StorageProvider:
    return S3StorageProvider(
        bucket_name="test-bucket",
        endpoint_url="http://storage.invalid",
        access_key_id="test-key",
        secret_access_key="test-secret",
    )


def _head_client(return_value=None, side_effect=None) -> AsyncMock:
    client = AsyncMock()
    client.head_object = AsyncMock(return_value=return_value, side_effect=side_effect)
    return client


# ---------------------------------------------------------------------------
# S3 exists(): only genuine not-found is False
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_exists_returns_true_for_existing_object():
    client = _head_client(return_value={"ContentLength": 12})
    with _fake_aioboto3(client):
        assert await _provider().exists("tenant-1", "docs/a.txt") is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        _client_error("NoSuchKey", 404),
        _client_error("NotFound", 404),
        _client_error("404", 404),
        ClientError({"ResponseMetadata": {"HTTPStatusCode": 404}}, "HeadObject"),
    ],
)
async def test_exists_returns_false_only_for_genuine_not_found(error):
    client = _head_client(side_effect=error)
    with _fake_aioboto3(client):
        assert await _provider().exists("tenant-1", "docs/a.txt") is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        _client_error("AccessDenied", 403),
        _client_error("403", 403),
        _client_error("Forbidden", 403),
    ],
)
async def test_exists_raises_unavailable_on_access_denied(error):
    client = _head_client(side_effect=error)
    with _fake_aioboto3(client):
        with pytest.raises(StorageUnavailableError):
            await _provider().exists("tenant-1", "docs/a.txt")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        _client_error("InvalidAccessKeyId", 403),
        _client_error("SignatureDoesNotMatch", 403),
    ],
)
async def test_exists_raises_unavailable_on_invalid_credentials(error):
    client = _head_client(side_effect=error)
    with _fake_aioboto3(client):
        with pytest.raises(StorageUnavailableError):
            await _provider().exists("tenant-1", "docs/a.txt")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        EndpointConnectionError(endpoint_url="http://storage.invalid"),
        ConnectTimeoutError(endpoint_url="http://storage.invalid"),
        ReadTimeoutError(endpoint_url="http://storage.invalid"),
        TimeoutError("simulated timeout"),
    ],
)
async def test_exists_raises_unavailable_on_network_or_timeout(error):
    client = _head_client(side_effect=error)
    with _fake_aioboto3(client):
        with pytest.raises(StorageUnavailableError):
            await _provider().exists("tenant-1", "docs/a.txt")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        _client_error("SlowDown", 503),
        _client_error("Throttling", 400),
        _client_error("503", 503),
        _client_error("InternalError", 500),
    ],
)
async def test_exists_raises_unavailable_on_throttling_or_5xx(error):
    client = _head_client(side_effect=error)
    with _fake_aioboto3(client):
        with pytest.raises(StorageUnavailableError):
            await _provider().exists("tenant-1", "docs/a.txt")


@pytest.mark.asyncio
async def test_exists_raises_base_storage_error_for_unexpected_failure():
    client = _head_client(side_effect=RuntimeError("unexpected provider crash"))
    with _fake_aioboto3(client):
        with pytest.raises(StorageError) as exc_info:
            await _provider().exists("tenant-1", "docs/a.txt")
    assert type(exc_info.value) is StorageError


@pytest.mark.asyncio
async def test_exists_raises_unavailable_for_missing_bucket():
    client = _head_client(side_effect=_client_error("NoSuchBucket", 404))
    with _fake_aioboto3(client):
        with pytest.raises(StorageUnavailableError):
            await _provider().exists("tenant-1", "docs/a.txt")


# ---------------------------------------------------------------------------
# Other S3 operations use the same classification
# ---------------------------------------------------------------------------
def _body_client(data: bytes = b"content") -> AsyncMock:
    client = AsyncMock()
    body = AsyncMock()
    body.__aenter__.return_value = body
    body.read = AsyncMock(return_value=data)
    client.get_object = AsyncMock(return_value={"Body": body})
    return client


@pytest.mark.asyncio
async def test_get_raises_not_found_and_unavailable():
    client = _body_client()
    client.get_object.side_effect = _client_error("NoSuchKey", 404)
    with _fake_aioboto3(client):
        with pytest.raises(StorageNotFoundError):
            await _provider().get("tenant-1", "docs/a.txt")

    client = _body_client()
    client.get_object.side_effect = _client_error("AccessDenied", 403)
    with _fake_aioboto3(client):
        with pytest.raises(StorageUnavailableError):
            await _provider().get("tenant-1", "docs/a.txt")


@pytest.mark.asyncio
async def test_get_size_raises_not_found_and_unavailable():
    client = _head_client(side_effect=_client_error("NoSuchKey", 404))
    with _fake_aioboto3(client):
        with pytest.raises(StorageNotFoundError):
            await _provider().get_size("tenant-1", "docs/a.txt")

    client = _head_client(side_effect=EndpointConnectionError(endpoint_url="http://storage.invalid"))
    with _fake_aioboto3(client):
        with pytest.raises(StorageUnavailableError):
            await _provider().get_size("tenant-1", "docs/a.txt")


@pytest.mark.asyncio
async def test_delete_distinguishes_success_absent_and_failure():
    client = AsyncMock()
    client.delete_object = AsyncMock(return_value={})
    with _fake_aioboto3(client):
        assert await _provider().delete("tenant-1", "docs/a.txt") is True

    client = AsyncMock()
    client.delete_object = AsyncMock(side_effect=_client_error("NoSuchKey", 404))
    with _fake_aioboto3(client):
        assert await _provider().delete("tenant-1", "docs/a.txt") is False

    client = AsyncMock()
    client.delete_object = AsyncMock(side_effect=_client_error("AccessDenied", 403))
    with _fake_aioboto3(client):
        with pytest.raises(StorageUnavailableError):
            await _provider().delete("tenant-1", "docs/a.txt")


@pytest.mark.asyncio
async def test_list_keys_raises_instead_of_returning_empty():
    client = AsyncMock()
    client.get_paginator = MagicMock(side_effect=_client_error("AccessDenied", 403))
    with _fake_aioboto3(client):
        with pytest.raises(StorageUnavailableError):
            await _provider().list_keys("tenant-1")


# ---------------------------------------------------------------------------
# Reconciliation fakes
# ---------------------------------------------------------------------------
class _FakeStorage(StorageProvider):
    def __init__(self) -> None:
        self.keys: set[str] = set()
        self.exists_errors: dict[str, BaseException] = {}
        self.default_exists_error: BaseException | None = None
        self.list_error: BaseException | None = None
        self.delete_error: BaseException | None = None
        self.deleted: list[str] = []
        self.list_calls = 0

    async def save(self, tenant_id: str, relative_key: str, data: bytes) -> str:
        self.keys.add(relative_key)
        return relative_key

    async def get(self, tenant_id: str, relative_key: str) -> bytes:
        if relative_key not in self.keys:
            raise StorageNotFoundError(relative_key)
        return b"content"

    async def delete(self, tenant_id: str, relative_key: str) -> bool:
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append(relative_key)
        if relative_key in self.keys:
            self.keys.remove(relative_key)
            return True
        return False

    async def exists(self, tenant_id: str, relative_key: str) -> bool:
        if relative_key in self.exists_errors:
            raise self.exists_errors[relative_key]
        if self.default_exists_error is not None:
            raise self.default_exists_error
        return relative_key in self.keys

    async def get_size(self, tenant_id: str, relative_key: str) -> int:
        return 1

    async def list_keys(self, tenant_id: str, prefix: str = "") -> list[str]:
        self.list_calls += 1
        if self.list_error is not None:
            raise self.list_error
        tenant_prefix = f"tenants/{tenant_id}/"
        return sorted(
            key
            for key in self.keys
            if key.startswith(tenant_prefix)
            and (not prefix or key.startswith(prefix))
        )


async def _create_kb(session: AsyncSession, tenant_id: uuid.UUID) -> KnowledgeBase:
    kb = KnowledgeBase(
        tenant_id=tenant_id,
        name=f"M13.2 KB {uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    session.add(kb)
    await session.commit()
    await session.refresh(kb)
    return kb


async def _add_document(
    session: AsyncSession,
    storage: StorageProvider,
    tenant_id: uuid.UUID,
    kb_id: uuid.UUID,
    filename: str,
) -> tuple[Document, str]:
    document_id = uuid.uuid4()
    key = storage.build_storage_key(
        tenant_id=str(tenant_id),
        knowledge_base_id=str(kb_id),
        document_id=str(document_id),
        version_number=1,
        filename=filename,
    )
    document = Document(
        id=document_id,
        tenant_id=tenant_id,
        knowledge_base_id=kb_id,
        filename=filename,
        safe_filename=filename,
        file_path=key,
        file_size=8,
        mime_type="text/plain",
        file_hash=uuid.uuid4().hex,
        status="QUEUED",
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document, key


@pytest.fixture
async def reconciliation_state(db_session: AsyncSession, seed_data: dict):
    tenant = seed_data["tenant_a"]
    kb = await _create_kb(db_session, tenant.id)
    storage = _FakeStorage()
    missing_document, missing_key = await _add_document(
        db_session, storage, tenant.id, kb.id, "missing.txt"
    )
    present_document, present_key = await _add_document(
        db_session, storage, tenant.id, kb.id, "present.txt"
    )
    storage.keys.add(present_key)
    orphan_key = storage.build_storage_key(
        tenant_id=str(tenant.id),
        knowledge_base_id=str(kb.id),
        document_id=str(uuid.uuid4()),
        version_number=1,
        filename="orphan.txt",
    )
    storage.keys.add(orphan_key)
    return {
        "tenant": tenant,
        "kb": kb,
        "storage": storage,
        "missing_document": missing_document,
        "missing_key": missing_key,
        "present_document": present_document,
        "present_key": present_key,
        "orphan_key": orphan_key,
    }


@pytest.mark.asyncio
async def test_dry_run_with_unavailable_storage_reports_incomplete_without_mutations(
    db_session: AsyncSession, reconciliation_state: dict
):
    state = reconciliation_state
    storage = state["storage"]
    storage.default_exists_error = StorageUnavailableError("head failed")

    report = await reconcile_storage(
        db_session, storage, tenant_id=state["tenant"].id
    )

    assert report["dry_run"] is True
    assert report["inventory_complete"] is False
    assert report["inventory_status"] == "incomplete"
    assert report["fix_refused"] is False
    assert report["missing_objects_count"] == 0
    assert report["fixed"]["documents_marked_failed"] == 0
    assert report["fixed"]["orphan_objects_deleted"] == 0
    assert report["orphan_inventory_verified"] is False
    assert report["errors"]
    assert storage.deleted == []

    await db_session.refresh(state["missing_document"])
    await db_session.refresh(state["present_document"])
    assert state["missing_document"].status == "QUEUED"
    assert state["present_document"].status == "QUEUED"
    assert state["orphan_key"] in storage.keys


@pytest.mark.asyncio
async def test_listing_failure_aborts_before_any_mutation(
    db_session: AsyncSession, reconciliation_state: dict
):
    state = reconciliation_state
    storage = state["storage"]
    storage.list_error = StorageUnavailableError("inventory auth failure")

    with pytest.raises(StorageUnavailableError):
        await reconcile_storage(db_session, storage, tenant_id=state["tenant"].id)

    await db_session.refresh(state["missing_document"])
    assert state["missing_document"].status == "QUEUED"
    assert state["orphan_key"] in storage.keys
    assert storage.deleted == []


@pytest.mark.asyncio
async def test_listing_unexpected_failure_aborts_as_storage_error(
    db_session: AsyncSession, reconciliation_state: dict
):
    state = reconciliation_state
    storage = state["storage"]
    storage.list_error = RuntimeError("unexpected inventory crash")

    with pytest.raises(StorageError):
        await reconcile_storage(db_session, storage, tenant_id=state["tenant"].id)

    await db_session.refresh(state["missing_document"])
    assert state["missing_document"].status == "QUEUED"
    assert storage.deleted == []


@pytest.mark.asyncio
async def test_fix_refuses_incomplete_inventory_and_keeps_db_rows(
    db_session: AsyncSession, reconciliation_state: dict
):
    state = reconciliation_state
    storage = state["storage"]
    storage.exists_errors[state["missing_key"]] = StorageUnavailableError("head denied")

    report = await reconcile_storage(
        db_session,
        storage,
        tenant_id=state["tenant"].id,
        fix=True,
        delete_orphans=True,
    )

    assert report["fix_refused"] is True
    assert report["refusal_reason"] == "inventory_incomplete"
    assert report["inventory_complete"] is False
    assert report["fixed"]["documents_marked_failed"] == 0
    assert report["fixed"]["orphan_objects_deleted"] == 0
    assert report["orphan_cleanup"] == {
        "requested": True,
        "performed": False,
        "skipped_reason": "inventory_incomplete",
    }
    assert storage.deleted == []

    await db_session.refresh(state["missing_document"])
    await db_session.refresh(state["present_document"])
    assert state["missing_document"].status == "QUEUED"
    assert state["present_document"].status == "QUEUED"
    assert "storage_reconciliation" not in (state["missing_document"].metadata_json or {})


@pytest.mark.asyncio
async def test_fix_with_confirmed_incomplete_inventory_marks_only_definitive_misses(
    db_session: AsyncSession, reconciliation_state: dict
):
    state = reconciliation_state
    storage = state["storage"]
    storage.exists_errors[state["present_key"]] = StorageUnavailableError("head denied")

    report = await reconcile_storage(
        db_session,
        storage,
        tenant_id=state["tenant"].id,
        fix=True,
        delete_orphans=True,
        allow_incomplete_inventory=True,
    )

    assert report["fix_refused"] is False
    assert report["inventory_complete"] is False
    assert report["fixed"]["documents_marked_failed"] == 1
    assert report["fixed"]["orphan_objects_deleted"] == 0
    assert report["orphan_cleanup"]["performed"] is False
    assert report["orphan_cleanup"]["skipped_reason"] == "inventory_incomplete"
    assert storage.deleted == []

    await db_session.refresh(state["missing_document"])
    await db_session.refresh(state["present_document"])
    assert state["missing_document"].status == "FAILED"
    assert state["present_document"].status == "QUEUED"


@pytest.mark.asyncio
async def test_orphan_cleanup_requires_verified_complete_inventory(
    db_session: AsyncSession, reconciliation_state: dict
):
    state = reconciliation_state
    storage = state["storage"]
    storage.exists_errors[state["present_key"]] = StorageUnavailableError("head denied")

    report = await reconcile_storage(
        db_session,
        storage,
        tenant_id=state["tenant"].id,
        fix=True,
        delete_orphans=True,
        allow_incomplete_inventory=True,
    )
    assert report["orphan_inventory_verified"] is False
    assert state["orphan_key"] in storage.keys

    storage.exists_errors.clear()
    clean_report = await reconcile_storage(
        db_session,
        storage,
        tenant_id=state["tenant"].id,
        fix=True,
        delete_orphans=True,
    )
    assert clean_report["inventory_complete"] is True
    assert clean_report["orphan_inventory_verified"] is True
    assert clean_report["orphan_cleanup"]["performed"] is True
    assert clean_report["fixed"]["orphan_objects_deleted"] == 1
    assert state["orphan_key"] not in storage.keys


@pytest.mark.asyncio
async def test_unsupported_listing_is_incomplete_and_never_deletes_orphans(
    db_session: AsyncSession, reconciliation_state: dict
):
    state = reconciliation_state
    storage = state["storage"]
    storage.list_error = NotImplementedError("listing unsupported")

    report = await reconcile_storage(
        db_session,
        storage,
        tenant_id=state["tenant"].id,
        fix=True,
        delete_orphans=True,
        allow_incomplete_inventory=True,
    )

    assert report["inventory_complete"] is False
    assert report["tenant_results"][0]["object_listing"] == "unsupported"
    assert report["orphan_cleanup"]["performed"] is False
    assert storage.deleted == []
    assert len(storage.keys) == 2


@pytest.mark.asyncio
async def test_cli_fix_refuses_incomplete_inventory_with_nonzero_exit(
    db_session: AsyncSession,
    reconciliation_state: dict,
    monkeypatch,
    capsys,
):
    state = reconciliation_state
    storage = state["storage"]
    storage.exists_errors[state["missing_key"]] = StorageUnavailableError("head denied")

    class _SessionContext:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(reconcile_command, "async_session_factory", lambda: _SessionContext())
    monkeypatch.setattr(reconcile_command, "get_storage_provider", lambda: storage)

    args = reconcile_command._parse_args(["--fix", "--tenant", str(state["tenant"].id)])
    exit_code = await reconcile_command._run(args)

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Reconciliation refused" in captured.err
    assert '"fix_refused": true' in captured.out
    await db_session.refresh(state["missing_document"])
    assert state["missing_document"].status == "QUEUED"
