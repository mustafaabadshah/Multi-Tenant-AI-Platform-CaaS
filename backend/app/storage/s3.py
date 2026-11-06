"""S3-compatible storage provider stub for future cloud deployments."""

from app.storage.base import StorageProvider


class S3StorageProvider(StorageProvider):
    """S3-compatible cloud storage provider (AWS S3, MinIO, Cloudflare R2).

    Prepared for enterprise scale; raises clear configuration errors if selected without credentials.
    """

    def __init__(self, bucket_name: str | None = None, endpoint_url: str | None = None) -> None:
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url

    async def save(self, tenant_id: str, relative_key: str, data: bytes) -> str:
        raise NotImplementedError("S3 storage provider requires AWS credentials and boto3 installed.")

    async def get(self, tenant_id: str, relative_key: str) -> bytes:
        raise NotImplementedError("S3 storage provider requires AWS credentials and boto3 installed.")

    async def delete(self, tenant_id: str, relative_key: str) -> bool:
        raise NotImplementedError("S3 storage provider requires AWS credentials and boto3 installed.")

    async def exists(self, tenant_id: str, relative_key: str) -> bool:
        raise NotImplementedError("S3 storage provider requires AWS credentials and boto3 installed.")

    async def get_size(self, tenant_id: str, relative_key: str) -> int:
        raise NotImplementedError("S3 storage provider requires AWS credentials and boto3 installed.")
