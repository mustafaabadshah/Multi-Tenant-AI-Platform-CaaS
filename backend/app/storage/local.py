"""Local filesystem storage provider implementation."""

import asyncio
from pathlib import Path

from app.core.config import settings
from app.storage.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider with strict tenant path containment."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or settings.STORAGE_PATH).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_tenant_path(self, tenant_id: str, relative_key: str) -> Path:
        """Resolve and validate that the target path does not escape tenant boundary."""
        tenant_root = (self.base_dir / "tenants" / str(tenant_id)).resolve()
        tenant_root.mkdir(parents=True, exist_ok=True)

        # Normalize relative key by stripping leading slashes and tenant prefix if repeated
        clean_key = relative_key.replace("\\", "/").lstrip("/")
        if clean_key.startswith(f"tenants/{tenant_id}/"):
            clean_key = clean_key[len(f"tenants/{tenant_id}/"):]

        target_path = (tenant_root / clean_key).resolve()

        # Path traversal check
        try:
            target_path.relative_to(tenant_root)
        except ValueError as err:
            raise PermissionError(f"Path traversal detected: {relative_key}") from err

        return target_path

    async def save(self, tenant_id: str, relative_key: str, data: bytes) -> str:
        """Save raw bytes to tenant directory."""
        target_path = self._resolve_tenant_path(tenant_id, relative_key)

        def _sync_write() -> None:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            # Write to temporary file then replace for atomic persistence
            temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
            temp_path.write_bytes(data)
            temp_path.replace(target_path)

        await asyncio.to_thread(_sync_write)
        return relative_key

    async def get(self, tenant_id: str, relative_key: str) -> bytes:
        """Read raw bytes from tenant directory."""
        target_path = self._resolve_tenant_path(tenant_id, relative_key)

        def _sync_read() -> bytes:
            if not target_path.exists() or not target_path.is_file():
                raise FileNotFoundError(f"File not found: {relative_key}")
            return target_path.read_bytes()

        return await asyncio.to_thread(_sync_read)

    async def delete(self, tenant_id: str, relative_key: str) -> bool:
        """Delete file from tenant directory."""
        target_path = self._resolve_tenant_path(tenant_id, relative_key)

        def _sync_delete() -> bool:
            if target_path.exists() and target_path.is_file():
                target_path.unlink()
                return True
            return False

        return await asyncio.to_thread(_sync_delete)

    async def exists(self, tenant_id: str, relative_key: str) -> bool:
        """Check if file exists in tenant directory."""
        target_path = self._resolve_tenant_path(tenant_id, relative_key)
        return await asyncio.to_thread(lambda: target_path.exists() and target_path.is_file())

    async def get_size(self, tenant_id: str, relative_key: str) -> int:
        """Get file size in bytes."""
        target_path = self._resolve_tenant_path(tenant_id, relative_key)

        def _sync_size() -> int:
            if not target_path.exists():
                raise FileNotFoundError(f"File not found: {relative_key}")
            return target_path.stat().st_size

        return await asyncio.to_thread(_sync_size)
