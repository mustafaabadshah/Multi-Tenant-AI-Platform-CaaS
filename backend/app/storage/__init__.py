"""Storage package exports and factory."""

from functools import lru_cache

from app.core.config import Settings, settings
from app.storage.base import StorageProvider, sanitize_filename
from app.storage.local import LocalStorageProvider
from app.storage.s3 import S3StorageProvider


def validate_storage_configuration(app_settings: Settings) -> None:
    """Fail-closed storage configuration validation.

    - Local filesystem storage is development-only; production selection of
      ``local`` raises immediately instead of silently persisting uploads on
      an ephemeral filesystem.
    - S3-backed storage in production requires a bucket, and requires explicit
      credentials whenever an endpoint URL is configured (AWS IAM-role
      deployments without an endpoint URL may omit static keys).
    """
    backend = (app_settings.STORAGE_BACKEND or "").lower()

    if backend == "local":
        if app_settings.ENVIRONMENT == "production":
            raise RuntimeError(
                "Invalid production storage configuration: STORAGE_BACKEND=local is not "
                "allowed in production. Configure an S3-compatible durable object storage "
                "backend (STORAGE_BACKEND=s3)."
            )
        return

    if backend not in ("s3", "minio"):
        raise ValueError(f"Unsupported storage backend: {app_settings.STORAGE_BACKEND}")

    if not app_settings.S3_BUCKET_NAME:
        raise RuntimeError(
            "Invalid production storage configuration: S3 storage backend selected but "
            "S3_BUCKET_NAME is not configured."
        )

    if app_settings.S3_ENDPOINT_URL and not (
        app_settings.S3_ACCESS_KEY_ID and app_settings.S3_SECRET_ACCESS_KEY
    ):
        raise RuntimeError(
            "Invalid production storage configuration: S3_ENDPOINT_URL is configured but "
            "S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY are missing."
        )


@lru_cache
def get_storage_provider() -> StorageProvider:
    """Return configured storage provider singleton (fail-closed in production)."""
    validate_storage_configuration(settings)
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
    "validate_storage_configuration",
]
