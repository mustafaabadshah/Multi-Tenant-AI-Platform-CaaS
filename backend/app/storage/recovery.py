"""Disaster recovery and paired backup utilities for tenant-isolated file storage."""

import hashlib
import json
import logging
import os
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document

logger = logging.getLogger("mmaip.storage.recovery")


@dataclass
class StorageFileRecord:
    relative_path: str
    size_bytes: int
    sha256: str


@dataclass
class StorageBackupManifest:
    timestamp: str
    archive_file: str
    archive_size_bytes: int
    archive_sha256: str
    format: str
    total_files: int
    total_bytes: int
    status: str
    paired_database: dict[str, Any] | None = None
    files: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StorageRestoreResult:
    status: str
    archive_verified: bool
    restored_files_count: int
    restored_bytes: int
    verified_files: list[str] = field(default_factory=list)
    corrupted_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)


@dataclass
class StorageReconciliationReport:
    tenant_id: str
    total_documents: int
    matched_files: int
    missing_files: list[dict[str, Any]] = field(default_factory=list)
    hash_mismatches: list[dict[str, Any]] = field(default_factory=list)
    size_mismatches: list[dict[str, Any]] = field(default_factory=list)
    orphan_files: list[str] = field(default_factory=list)

    @property
    def is_consistent(self) -> bool:
        return (
            len(self.missing_files) == 0
            and len(self.hash_mismatches) == 0
            and len(self.size_mismatches) == 0
        )


def compute_file_sha256(path: Path | str) -> str:
    """Compute SHA-256 hash of a file efficiently in 64KB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_storage_backup(
    storage_path: Path | str,
    backup_dir: Path | str,
    paired_db_manifest: dict[str, Any] | None = None,
) -> StorageBackupManifest:
    """Create a verified, timestamped archive backup of the storage directory."""
    src_dir = Path(storage_path).resolve()
    dst_dir = Path(backup_dir).resolve()
    dst_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_filename = f"mmaip_storage_backup_{timestamp}.zip"
    archive_path = dst_dir / archive_filename
    manifest_path = dst_dir / f"{archive_filename}.manifest.json"
    checksum_path = dst_dir / f"{archive_filename}.sha256"

    file_records: list[dict[str, Any]] = []
    total_bytes = 0

    # Collect files
    files_to_archive: list[Path] = []
    if src_dir.exists():
        for p in src_dir.rglob("*"):
            if p.is_file():
                rel_path = str(p.relative_to(src_dir)).replace("\\", "/")
                file_size = p.stat().st_size
                file_hash = compute_file_sha256(p)
                total_bytes += file_size
                file_records.append(
                    {
                        "relative_path": rel_path,
                        "size_bytes": file_size,
                        "sha256": file_hash,
                    }
                )
                files_to_archive.append(p)

    # Build ZIP archive
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if files_to_archive:
            for fp in files_to_archive:
                rel = str(fp.relative_to(src_dir)).replace("\\", "/")
                zf.write(fp, arcname=rel)
        else:
            # Empty marker
            zf.writestr(".mmaip_empty_backup", "EMPTY_STORAGE")

    # Compute archive checksum
    archive_sha256 = compute_file_sha256(archive_path)
    archive_size = archive_path.stat().st_size

    # Write checksum file
    checksum_path.write_text(f"{archive_sha256} *{archive_filename}\n", encoding="utf-8")

    manifest = StorageBackupManifest(
        timestamp=datetime.now(timezone.utc).isoformat(),
        archive_file=archive_filename,
        archive_size_bytes=archive_size,
        archive_sha256=archive_sha256,
        format="mmaip_storage_v1",
        total_files=len(file_records),
        total_bytes=total_bytes,
        status="COMPLETED",
        paired_database=paired_db_manifest,
        files=file_records,
    )

    manifest_path.write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
    return manifest


def restore_storage_backup(
    archive_path: Path | str,
    target_storage_path: Path | str,
    verify_checksum: bool = True,
) -> StorageRestoreResult:
    """Safely restore storage directory from backup archive with path traversal protection."""
    arc_path = Path(archive_path).resolve()
    target_dir = Path(target_storage_path).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    if not arc_path.exists():
        raise FileNotFoundError(f"Backup archive not found: {arc_path}")

    archive_verified = False
    checksum_path = Path(f"{arc_path}.sha256")
    if checksum_path.exists() and verify_checksum:
        line = checksum_path.read_text(encoding="utf-8").strip()
        expected_hash = line.split()[0].lower()
        actual_hash = compute_file_sha256(arc_path).lower()
        if expected_hash != actual_hash:
            raise ValueError(
                f"Archive SHA-256 verification failed! Expected: {expected_hash}, Got: {actual_hash}"
            )
        archive_verified = True

    # Safely extract
    with zipfile.ZipFile(arc_path, "r") as zf:
        for member in zf.namelist():
            if member == ".mmaip_empty_backup":
                continue
            # Path traversal prevention
            norm_member = os.path.normpath(member)
            if norm_member.startswith("..") or os.path.isabs(norm_member):
                raise PermissionError(f"Zip slip path traversal detected: {member}")
            zf.extract(member, target_dir)

    # Manifest verification if available
    manifest_path = Path(f"{arc_path}.manifest.json")
    verified_files: list[str] = []
    corrupted_files: list[str] = []
    missing_files: list[str] = []
    restored_bytes = 0

    if manifest_path.exists():
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest_data.get("files", []):
            rel_path = entry["relative_path"]
            exp_hash = entry["sha256"].lower()
            exp_size = entry["size_bytes"]

            dest_path = target_dir / rel_path
            if not dest_path.exists():
                missing_files.append(rel_path)
                continue

            actual_hash = compute_file_sha256(dest_path).lower()
            actual_size = dest_path.stat().st_size
            restored_bytes += actual_size

            if actual_hash == exp_hash and actual_size == exp_size:
                verified_files.append(rel_path)
            else:
                corrupted_files.append(rel_path)

    status = "SUCCESS" if not corrupted_files and not missing_files else "FAILED"
    return StorageRestoreResult(
        status=status,
        archive_verified=archive_verified,
        restored_files_count=len(verified_files),
        restored_bytes=restored_bytes,
        verified_files=verified_files,
        corrupted_files=corrupted_files,
        missing_files=missing_files,
    )


async def reconcile_database_and_storage(
    session: AsyncSession,
    tenant_id: uuid.UUID | str,
    storage_path: Path | str,
) -> StorageReconciliationReport:
    """Reconcile PostgreSQL document records with local filesystem storage.

    Verifies existence, byte sizes, and SHA-256 checksums, and detects orphan files.
    """
    t_id = uuid.UUID(str(tenant_id)) if isinstance(tenant_id, str) else tenant_id
    base_storage = Path(storage_path).resolve()
    tenant_root = base_storage / "tenants" / str(t_id)

    # 1. Fetch all documents for this tenant
    stmt = select(Document).where(Document.tenant_id == t_id)
    docs = list((await session.execute(stmt)).scalars().all())

    matched = 0
    missing_files: list[dict[str, Any]] = []
    hash_mismatches: list[dict[str, Any]] = []
    size_mismatches: list[dict[str, Any]] = []
    expected_rel_paths: set[str] = set()

    for d in docs:
        if d.status == "DELETED":
            continue

        clean_key = d.file_path.replace("\\", "/").lstrip("/")
        if clean_key.startswith(f"tenants/{t_id}/"):
            clean_key = clean_key[len(f"tenants/{t_id}/") :]

        file_on_disk = tenant_root / clean_key
        expected_rel_paths.add(str(file_on_disk.resolve()))

        if not file_on_disk.exists() or not file_on_disk.is_file():
            missing_files.append(
                {
                    "document_id": str(d.id),
                    "filename": d.filename,
                    "expected_path": str(file_on_disk),
                }
            )
            continue

        actual_size = file_on_disk.stat().st_size
        if d.file_size and actual_size != d.file_size:
            size_mismatches.append(
                {
                    "document_id": str(d.id),
                    "filename": d.filename,
                    "expected_size": d.file_size,
                    "actual_size": actual_size,
                }
            )
            continue

        actual_hash = compute_file_sha256(file_on_disk)
        if d.file_hash and actual_hash.lower() != d.file_hash.lower():
            hash_mismatches.append(
                {
                    "document_id": str(d.id),
                    "filename": d.filename,
                    "expected_hash": d.file_hash,
                    "actual_hash": actual_hash,
                }
            )
            continue

        matched += 1

    # 2. Check for orphan files on disk
    orphan_files: list[str] = []
    if tenant_root.exists():
        for p in tenant_root.rglob("*"):
            if p.is_file() and str(p.resolve()) not in expected_rel_paths:
                orphan_files.append(str(p.relative_to(base_storage)).replace("\\", "/"))

    return StorageReconciliationReport(
        tenant_id=str(t_id),
        total_documents=len(docs),
        matched_files=matched,
        missing_files=missing_files,
        hash_mismatches=hash_mismatches,
        size_mismatches=size_mismatches,
        orphan_files=orphan_files,
    )
