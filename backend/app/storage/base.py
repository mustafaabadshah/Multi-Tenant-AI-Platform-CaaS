"""Storage provider interface for MM AI Platform."""

import re
import uuid
from abc import ABC, abstractmethod


def sanitize_filename(filename: str) -> str:
    """Sanitize user-provided filename to prevent path traversal or unsafe characters."""
    # Strip directory components
    name = filename.replace("\\", "/").split("/")[-1]
    # Replace non-alphanumeric chars (excluding dots, dashes, underscores)
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", name)
    # Prevent hidden files or double dots
    cleaned = re.sub(r"^\.+", "", cleaned)
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    if not cleaned:
        cleaned = f"file_{uuid.uuid4().hex[:8]}"
    return cleaned


class StorageProvider(ABC):
    """Abstract storage provider for tenant-isolated document storage."""

    @abstractmethod
    async def save(self, tenant_id: str, relative_key: str, data: bytes) -> str:
        """Save raw bytes under the given tenant and relative key.

        Returns the normalized storage key.
        """
        pass

    @abstractmethod
    async def get(self, tenant_id: str, relative_key: str) -> bytes:
        """Retrieve raw bytes for the given tenant and relative key."""
        pass

    @abstractmethod
    async def delete(self, tenant_id: str, relative_key: str) -> bool:
        """Delete file at the given tenant and relative key. Returns True if deleted."""
        pass

    @abstractmethod
    async def exists(self, tenant_id: str, relative_key: str) -> bool:
        """Check if file exists."""
        pass

    @abstractmethod
    async def get_size(self, tenant_id: str, relative_key: str) -> int:
        """Return the size in bytes of the stored file."""
        pass

    @abstractmethod
    async def list_keys(self, tenant_id: str, prefix: str = "") -> list[str]:
        """List stored keys for a tenant, relative to the storage root.

        Returned keys use the same format as ``Document.file_path`` (for example
        ``tenants/{tenant_id}/kbs/...``). Providers that cannot enumerate
        objects must raise ``NotImplementedError`` rather than return an empty
        list, so reconciliation can report the capability as unsupported.
        """
        pass

    def build_storage_key(
        self,
        tenant_id: str,
        knowledge_base_id: str,
        document_id: str,
        version_number: int,
        filename: str,
    ) -> str:
        """Build a safe, collision-resistant storage key partitioned by tenant and resource."""
        safe_name = sanitize_filename(filename)
        return f"tenants/{tenant_id}/kbs/{knowledge_base_id}/docs/{document_id}/v{version_number}/{safe_name}"
