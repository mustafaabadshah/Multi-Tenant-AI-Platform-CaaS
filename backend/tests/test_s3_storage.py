"""Unit tests for S3 storage provider and factory."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.storage import get_storage_provider
from app.storage.local import LocalStorageProvider
from app.storage.s3 import S3StorageProvider


def test_s3_unconfigured_raises_error():
    """S3 provider without bucket_name raises clear configuration error."""
    provider = S3StorageProvider(bucket_name=None)
    with pytest.raises(ValueError, match="S3_BUCKET_NAME is not configured"):
        provider._check_configured()


def test_s3_key_prefix_tenant_isolation():
    """Verify all S3 keys are prefixed with tenant_id."""
    provider = S3StorageProvider(bucket_name="my-bucket")
    full_key = provider._get_full_key(
        tenant_id="tenant-123",
        relative_key="documents/kb-456/doc-789/file.pdf",
    )
    assert full_key == "tenant-123/documents/kb-456/doc-789/file.pdf"


def test_storage_factory_default_is_local():
    """Default factory returns LocalStorageProvider."""
    provider = get_storage_provider()
    assert isinstance(provider, LocalStorageProvider)


@pytest.mark.asyncio
async def test_s3_operations_mocked():
    """Verify S3 save/get/delete/exists operations via mocked aioboto3."""
    provider = S3StorageProvider(
        bucket_name="prod-bucket",
        endpoint_url="https://s3.us-east-1.amazonaws.com",
        access_key_id="test-key",
        secret_access_key="test-secret",
    )

    mock_client = AsyncMock()
    mock_client.put_object = AsyncMock()
    mock_client.delete_object = AsyncMock()
    mock_client.head_object = AsyncMock(return_value={"ContentLength": 1024})

    mock_body = AsyncMock()
    mock_body.__aenter__.return_value = mock_body
    mock_body.read = AsyncMock(return_value=b"test file content")
    mock_client.get_object = AsyncMock(return_value={"Body": mock_body})

    import sys

    mock_session_inst = MagicMock()
    mock_client_context = AsyncMock()
    mock_client_context.__aenter__.return_value = mock_client
    mock_session_inst.client.return_value = mock_client_context

    mock_aioboto3 = MagicMock()
    mock_aioboto3.Session.return_value = mock_session_inst

    with patch.dict(sys.modules, {"aioboto3": mock_aioboto3}):
        # Save
        key = await provider.save("tenant-abc", "doc1.txt", b"test file content")
        assert key == "tenant-abc/doc1.txt"
        mock_client.put_object.assert_called_once_with(
            Bucket="prod-bucket",
            Key="tenant-abc/doc1.txt",
            Body=b"test file content",
        )

        # Get
        data = await provider.get("tenant-abc", "doc1.txt")
        assert data == b"test file content"

        # Exists
        exists = await provider.exists("tenant-abc", "doc1.txt")
        assert exists is True

        # Get size
        size = await provider.get_size("tenant-abc", "doc1.txt")
        assert size == 1024

        # Delete
        deleted = await provider.delete("tenant-abc", "doc1.txt")
        assert deleted is True
