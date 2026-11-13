"""Stage 3 remediation tests â€” STOR-1: production storage safety (fail-closed)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.storage import get_storage_provider, validate_storage_configuration
from app.storage.base import StorageError, sanitize_filename
from app.storage.local import LocalStorageProvider
from app.storage.s3 import S3StorageProvider


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


# ---------------------------------------------------------------------------
# Configuration validation matrix
# ---------------------------------------------------------------------------
def test_local_development_configuration_valid():
    validate_storage_configuration(_settings(ENVIRONMENT="development", STORAGE_BACKEND="local"))


def test_valid_production_s3_configuration_valid():
    validate_storage_configuration(
        _settings(
            ENVIRONMENT="production",
            STORAGE_BACKEND="s3",
            S3_BUCKET_NAME="prod-bucket",
            S3_ENDPOINT_URL="https://s3.example.com",
            S3_ACCESS_KEY_ID="key",
            S3_SECRET_ACCESS_KEY="secret",
        )
    )


def test_production_local_storage_rejected():
    with pytest.raises(RuntimeError, match="STORAGE_BACKEND=local is not allowed in production"):
        validate_storage_configuration(_settings(ENVIRONMENT="production", STORAGE_BACKEND="local"))


def test_production_s3_missing_bucket_rejected():
    with pytest.raises(RuntimeError, match="S3_BUCKET_NAME is not configured"):
        validate_storage_configuration(_settings(ENVIRONMENT="production", STORAGE_BACKEND="s3"))


def test_production_s3_endpoint_without_credentials_rejected():
    with pytest.raises(RuntimeError, match="S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY are missing"):
        validate_storage_configuration(
            _settings(
                ENVIRONMENT="production",
                STORAGE_BACKEND="s3",
                S3_BUCKET_NAME="prod-bucket",
                S3_ENDPOINT_URL="https://s3.example.com",
            )
        )


def test_unsupported_storage_backend_rejected():
    with pytest.raises(ValueError, match="Unsupported storage backend"):
        validate_storage_configuration(_settings(ENVIRONMENT="development", STORAGE_BACKEND="ftp"))


def test_development_factory_returns_local_provider():
    provider = get_storage_provider()
    assert isinstance(provider, LocalStorageProvider)


# ---------------------------------------------------------------------------
# Tenant isolation and key safety
# ---------------------------------------------------------------------------
def test_tenant_separated_object_keys():
    provider = S3StorageProvider(bucket_name="bucket")
    key_a = provider._get_full_key("tenant-A", "docs/file.pdf")
    key_b = provider._get_full_key("tenant-B", "docs/file.pdf")
    assert key_a == "tenant-A/docs/file.pdf"
    assert key_b == "tenant-B/docs/file.pdf"
    assert key_a != key_b


def test_leading_slash_cannot_escape_tenant_prefix():
    provider = S3StorageProvider(bucket_name="bucket")
    key = provider._get_full_key("tenant-A", "/../../etc/passwd")
    assert key.startswith("tenant-A/")
    assert ".." not in key.split("tenant-A/")[1]


def test_sanitize_filename_blocks_path_traversal():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\config") == "config"
    assert sanitize_filename("plain-report.pdf") == "plain-report.pdf"


def test_build_storage_key_partitions_by_tenant():
    provider = S3StorageProvider(bucket_name="bucket")
    key_a = provider.build_storage_key("t1", "kb", "doc", 1, "a.pdf")
    key_b = provider.build_storage_key("t2", "kb", "doc", 1, "a.pdf")
    assert key_a.startswith("tenants/t1/")
    assert key_b.startswith("tenants/t2/")
    assert key_a != key_b


# ---------------------------------------------------------------------------
# S3 error safety (no secret leakage) with mocked client
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_s3_operation_error_does_not_leak_secrets():
    secret = "super-secret-key-123"
    provider = S3StorageProvider(
        bucket_name="bucket",
        endpoint_url="https://s3.example.com",
        access_key_id="access-id",
        secret_access_key=secret,
    )

    mock_client = AsyncMock()
    mock_client.put_object = AsyncMock(side_effect=RuntimeError("network down"))
    mock_session_inst = MagicMock()
    mock_client_context = AsyncMock()
    mock_client_context.__aenter__.return_value = mock_client
    mock_session_inst.client.return_value = mock_client_context
    mock_aioboto3 = MagicMock()
    mock_aioboto3.Session.return_value = mock_session_inst

    with patch.dict("sys.modules", {"aioboto3": mock_aioboto3}):
        # M13.2: S3 provider operations now wrap unexpected provider failures
        # in the typed StorageError hierarchy instead of leaking raw exceptions.
        with pytest.raises(StorageError) as exc_info:
            await provider.save("tenant-A", "doc.txt", b"data")

    assert secret not in str(exc_info.value)
    assert "access-id" not in str(exc_info.value)
