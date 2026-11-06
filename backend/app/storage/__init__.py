"""Storage package exports and factory."""

from functools import lru_cache

from app.core.config import settings
from app.storage.base import StorageProvider, sanitize_filename
from app.storage.local import LocalStorageProvider
from app.storage.s3 import S3StorageProvider


@lru_cache
def get_storage_provider() -> StorageProvider:
    """Return configured storage provider singleton."""
    backend = settings.STORAGE_BACKEND.lower()
    if backend == "local":
        return LocalStorageProvider(base_dir=settings.STORAGE_PATH)
    elif backend in ("s3", "minio"):
        return S3StorageProvider()
    else:
        raise ValueError(f"Unsupported storage backend: {settings.STORAGE_BACKEND}")


__all__ = [
    "StorageProvider",
    "LocalStorageProvider",
    "S3StorageProvider",
    "get_storage_provider",
    "sanitize_filename",
]
