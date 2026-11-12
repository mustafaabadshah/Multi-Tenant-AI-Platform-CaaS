"""S3-compatible object storage provider (AWS S3, MinIO, Cloudflare R2, Supabase Storage)."""

import os
from typing import Optional

from app.core.config import settings
from app.storage.base import StorageProvider


class S3StorageProvider(StorageProvider):
    """S3-compatible object storage provider with tenant key isolation.

    Keys are isolated under the tenant prefix: `{tenant_id}/{relative_key}`.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None,
    ) -> None:
        self.bucket_name = bucket_name or settings.S3_BUCKET_NAME or os.environ.get("S3_BUCKET_NAME")
        self.endpoint_url = endpoint_url or settings.S3_ENDPOINT_URL or os.environ.get("S3_ENDPOINT_URL")
        self.access_key_id = (
            access_key_id or settings.S3_ACCESS_KEY_ID or os.environ.get("S3_ACCESS_KEY_ID")
        )
        self.secret_access_key = (
            secret_access_key or settings.S3_SECRET_ACCESS_KEY or os.environ.get("S3_SECRET_ACCESS_KEY")
        )
        self.region_name = (
            region_name or settings.S3_REGION_NAME or os.environ.get("S3_REGION_NAME", "us-east-1")
        )

    def _get_full_key(self, tenant_id: str, relative_key: str) -> str:
        segments = [
            seg
            for seg in relative_key.replace("\\", "/").split("/")
            if seg not in ("", ".", "..")
        ]
        clean_key = "/".join(segments)
        return f"{tenant_id}/{clean_key}"

    def _check_configured(self) -> None:
        if not self.bucket_name:
            raise ValueError(
                "S3 storage backend selected, but S3_BUCKET_NAME is not configured. "
                "Please configure S3_BUCKET_NAME in environment."
            )

    async def save(self, tenant_id: str, relative_key: str, data: bytes) -> str:
        self._check_configured()
        full_key = self._get_full_key(tenant_id, relative_key)
        try:
            import aioboto3
        except ImportError:
            raise ImportError(
                "aioboto3 is required for S3StorageProvider. Install it via `pip install aioboto3`."
            )

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
        ) as s3_client:
            await s3_client.put_object(
                Bucket=self.bucket_name,
                Key=full_key,
                Body=data,
            )
        return full_key

    async def get(self, tenant_id: str, relative_key: str) -> bytes:
        self._check_configured()
        full_key = self._get_full_key(tenant_id, relative_key)
        try:
            import aioboto3
        except ImportError:
            raise ImportError(
                "aioboto3 is required for S3StorageProvider. Install it via `pip install aioboto3`."
            )

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
        ) as s3_client:
            resp = await s3_client.get_object(Bucket=self.bucket_name, Key=full_key)
            async with resp["Body"] as stream:
                return await stream.read()

    async def delete(self, tenant_id: str, relative_key: str) -> bool:
        self._check_configured()
        full_key = self._get_full_key(tenant_id, relative_key)
        try:
            import aioboto3
        except ImportError:
            raise ImportError(
                "aioboto3 is required for S3StorageProvider. Install it via `pip install aioboto3`."
            )

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
        ) as s3_client:
            await s3_client.delete_object(Bucket=self.bucket_name, Key=full_key)
            return True

    async def exists(self, tenant_id: str, relative_key: str) -> bool:
        self._check_configured()
        full_key = self._get_full_key(tenant_id, relative_key)
        try:
            import aioboto3
        except ImportError:
            raise ImportError(
                "aioboto3 is required for S3StorageProvider. Install it via `pip install aioboto3`."
            )

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
        ) as s3_client:
            try:
                await s3_client.head_object(Bucket=self.bucket_name, Key=full_key)
                return True
            except Exception:
                return False

    async def get_size(self, tenant_id: str, relative_key: str) -> int:
        self._check_configured()
        full_key = self._get_full_key(tenant_id, relative_key)
        try:
            import aioboto3
        except ImportError:
            raise ImportError(
                "aioboto3 is required for S3StorageProvider. Install it via `pip install aioboto3`."
            )

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
        ) as s3_client:
            resp = await s3_client.head_object(Bucket=self.bucket_name, Key=full_key)
            return int(resp.get("ContentLength", 0))
