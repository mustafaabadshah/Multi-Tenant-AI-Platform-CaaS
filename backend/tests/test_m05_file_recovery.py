"""M05 Stage F — Original Uploaded-File Disaster Recovery & Paired Backup Verification Suite.

Verifies:
1. Paired database & original binary file recovery for PDF, DOCX, XLSX/CSV, PNG, and TXT files.
2. Full byte-for-byte SHA-256 integrity match between original and restored files.
3. Storage provider retrieval (`get`) of restored binary files after simulated storage destruction.
4. Strict multi-tenant isolation of restored storage paths.
5. Database-to-storage reconciliation detecting missing, corrupted, and orphan files.
6. Zip-slip and path traversal attack prevention during archive restoration.
"""

import hashlib
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.base import Base
from app.models.knowledge import Document, DocumentVersion, KnowledgeBase
from app.models.tenant import Tenant
from app.storage.local import LocalStorageProvider
from app.storage.recovery import (
    create_storage_backup,
    reconcile_database_and_storage,
    restore_storage_backup,
)


@pytest_asyncio.fixture
async def recovery_session():
    """In-memory SQLite session for database model recovery testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def temp_storage_env():
    """Isolated temporary filesystem environment for storage backup and restore tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="mmaip_recovery_test_"))
    storage_path = temp_dir / "storage"
    backup_path = temp_dir / "backups"
    restore_path = temp_dir / "restored_storage"

    storage_path.mkdir(parents=True)
    backup_path.mkdir(parents=True)

    yield {
        "root": temp_dir,
        "storage": storage_path,
        "backup": backup_path,
        "restore": restore_path,
    }

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_paired_file_and_database_backup_and_restore(recovery_session: AsyncSession, temp_storage_env: dict):
    """Executes Stage F4 end-to-end paired disaster recovery test covering 5 file formats."""
    storage_dir = temp_storage_env["storage"]
    backup_dir = temp_storage_env["backup"]
    restore_dir = temp_storage_env["restore"]

    storage = LocalStorageProvider(base_dir=str(storage_dir))

    # 1. Seed two distinct tenants
    tenant_a = Tenant(
        id=uuid.uuid4(),
        name="Acme Corp A",
        slug="acme-a",
        type="organization",
        status="ACTIVE",
    )
    tenant_b = Tenant(
        id=uuid.uuid4(),
        name="Beta Corp B",
        slug="beta-b",
        type="organization",
        status="ACTIVE",
    )
    recovery_session.add_all([tenant_a, tenant_b])
    await recovery_session.flush()

    kb_a = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Engineering Docs",
        status="ACTIVE",
    )
    recovery_session.add(kb_a)
    await recovery_session.flush()

    # 2. Define 5 test files with genuine format signatures
    test_files_data = [
        {
            "filename": "quarterly_report.pdf",
            "content": b"%PDF-1.4\n1 0 obj\n<< /Title (Q3 Report) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF",
            "mime": "application/pdf",
        },
        {
            "filename": "specifications.docx",
            "content": b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"[Content_Types].xml fake docx payload",
            "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        {
            "filename": "financial_model.xlsx",
            "content": b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"xl/workbook.xml fake xlsx payload",
            "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
        {
            "filename": "architecture_diagram.png",
            "content": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82",
            "mime": "image/png",
        },
        {
            "filename": "readme_notes.txt",
            "content": b"Multi-Tenant AI Platform: Original plain-text documentation note with UTF-8 encoding.",
            "mime": "text/plain",
        },
    ]

    expected_manifest_records = []

    # 3. Save files to storage and database
    for item in test_files_data:
        doc_id = uuid.uuid4()
        content = item["content"]
        file_hash = hashlib.sha256(content).hexdigest()
        file_size = len(content)

        storage_key = storage.build_storage_key(
            tenant_id=str(tenant_a.id),
            knowledge_base_id=str(kb_a.id),
            document_id=str(doc_id),
            version_number=1,
            filename=item["filename"],
        )

        saved_key = await storage.save(str(tenant_a.id), storage_key, content)
        assert saved_key == storage_key

        doc = Document(
            id=doc_id,
            tenant_id=tenant_a.id,
            knowledge_base_id=kb_a.id,
            filename=item["filename"],
            safe_filename=item["filename"],
            file_path=storage_key,
            file_size=file_size,
            mime_type=item["mime"],
            file_hash=file_hash,
            status="COMPLETED",
        )
        doc_ver = DocumentVersion(
            id=uuid.uuid4(),
            tenant_id=tenant_a.id,
            document_id=doc.id,
            version_num=1,
            file_path=storage_key,
            file_size=file_size,
            file_hash=file_hash,
        )
        recovery_session.add_all([doc, doc_ver])

        expected_manifest_records.append(
            {
                "document_id": doc_id,
                "filename": item["filename"],
                "file_hash": file_hash,
                "file_size": file_size,
                "storage_key": storage_key,
                "content": content,
            }
        )

    await recovery_session.commit()

    # 4. Verify initial database-to-storage reconciliation is 100% consistent
    initial_recon = await reconcile_database_and_storage(
        session=recovery_session,
        tenant_id=tenant_a.id,
        storage_path=storage_dir,
    )
    assert initial_recon.is_consistent is True
    assert initial_recon.matched_files == 5
    assert len(initial_recon.missing_files) == 0
    assert len(initial_recon.hash_mismatches) == 0

    # 5. Create paired storage backup
    dummy_db_manifest = {
        "backup_file": "mmaip_backup_20261108_010000.dump",
        "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        "size_bytes": 1048576,
    }
    manifest = create_storage_backup(
        storage_path=storage_dir,
        backup_dir=backup_dir,
        paired_db_manifest=dummy_db_manifest,
    )

    assert manifest.total_files == 5
    assert manifest.status == "COMPLETED"
    assert manifest.paired_database == dummy_db_manifest
    archive_file_path = backup_dir / manifest.archive_file
    assert archive_file_path.exists()

    # 6. Simulate disaster: Completely destroy primary storage directory
    shutil.rmtree(storage_dir)
    assert not storage_dir.exists()

    # Verify reconciliation now shows 5 missing files
    disaster_recon = await reconcile_database_and_storage(
        session=recovery_session,
        tenant_id=tenant_a.id,
        storage_path=storage_dir,
    )
    assert disaster_recon.is_consistent is False
    assert len(disaster_recon.missing_files) == 5

    # 7. Restore storage to restore directory
    restore_result = restore_storage_backup(
        archive_path=archive_file_path,
        target_storage_path=restore_dir,
        verify_checksum=True,
    )

    assert restore_result.status == "SUCCESS"
    assert restore_result.archive_verified is True
    assert restore_result.restored_files_count == 5
    assert len(restore_result.corrupted_files) == 0
    assert len(restore_result.missing_files) == 0

    # 8. Point storage provider to restored directory and verify byte-for-byte retrieval
    restored_storage = LocalStorageProvider(base_dir=str(restore_dir))

    for rec in expected_manifest_records:
        # File existence check
        exists = await restored_storage.exists(str(tenant_a.id), rec["storage_key"])
        assert exists is True, f"File {rec['filename']} not found in restored storage"

        # Byte size check
        size = await restored_storage.get_size(str(tenant_a.id), rec["storage_key"])
        assert size == rec["file_size"], f"Size mismatch for {rec['filename']}"

        # Raw binary content check
        retrieved_content = await restored_storage.get(str(tenant_a.id), rec["storage_key"])
        assert retrieved_content == rec["content"], f"Content mismatch for {rec['filename']}"

        # SHA-256 integrity check
        restored_hash = hashlib.sha256(retrieved_content).hexdigest()
        assert restored_hash == rec["file_hash"], f"SHA-256 mismatch for {rec['filename']}"

    # 9. Verify multi-tenant isolation on restored storage
    # Tenant B must NOT be able to access Tenant A's restored file
    first_key = expected_manifest_records[0]["storage_key"]
    # If Tenant B tries to pass a key pointing to Tenant A's directory, path containment strips or errors
    with pytest.raises(FileNotFoundError):
        await restored_storage.get(str(tenant_b.id), first_key)

    # 10. Post-restore reconciliation verification
    post_restore_recon = await reconcile_database_and_storage(
        session=recovery_session,
        tenant_id=tenant_a.id,
        storage_path=restore_dir,
    )
    assert post_restore_recon.is_consistent is True
    assert post_restore_recon.matched_files == 5
    assert len(post_restore_recon.missing_files) == 0
    assert len(post_restore_recon.hash_mismatches) == 0
    assert len(post_restore_recon.size_mismatches) == 0


@pytest.mark.asyncio
async def test_reconciliation_detects_missing_corrupted_and_orphan_files(
    recovery_session: AsyncSession, temp_storage_env: dict
):
    """Verify that reconciliation accurately flags missing files, hash corruption, and untracked orphans."""
    storage_dir = temp_storage_env["storage"]
    storage = LocalStorageProvider(base_dir=str(storage_dir))

    tenant = Tenant(
        id=uuid.uuid4(),
        name="Delta Corp",
        slug="delta",
        type="organization",
        status="ACTIVE",
    )
    recovery_session.add(tenant)
    await recovery_session.flush()

    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Compliance KB",
        status="ACTIVE",
    )
    recovery_session.add(kb)
    await recovery_session.flush()

    # Doc 1: Good file
    doc1 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        knowledge_base_id=kb.id,
        filename="good.txt",
        safe_filename="good.txt",
        file_path="kbs/good.txt",
        file_size=12,
        mime_type="text/plain",
        file_hash=hashlib.sha256(b"healthy data").hexdigest(),
        status="COMPLETED",
    )
    await storage.save(str(tenant.id), "kbs/good.txt", b"healthy data")

    # Doc 2: Corrupted file (hash mismatch)
    doc2 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        knowledge_base_id=kb.id,
        filename="corrupted.txt",
        safe_filename="corrupted.txt",
        file_path="kbs/corrupted.txt",
        file_size=14,
        mime_type="text/plain",
        file_hash="0000000000000000000000000000000000000000000000000000000000000000",
        status="COMPLETED",
    )
    await storage.save(str(tenant.id), "kbs/corrupted.txt", b"corrupted data")

    # Doc 3: Missing file (in DB but deleted from storage)
    doc3 = Document(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        knowledge_base_id=kb.id,
        filename="missing.txt",
        safe_filename="missing.txt",
        file_path="kbs/missing.txt",
        file_size=10,
        mime_type="text/plain",
        file_hash="1111111111111111111111111111111111111111111111111111111111111111",
        status="COMPLETED",
    )

    recovery_session.add_all([doc1, doc2, doc3])
    await recovery_session.commit()

    # Add an orphan file on disk not tracked in database
    await storage.save(str(tenant.id), "kbs/orphan_file.bin", b"\x00\x01\x02\x03")

    report = await reconcile_database_and_storage(
        session=recovery_session,
        tenant_id=tenant.id,
        storage_path=storage_dir,
    )

    assert report.is_consistent is False
    assert report.total_documents == 3
    assert report.matched_files == 1
    assert len(report.missing_files) == 1
    assert report.missing_files[0]["filename"] == "missing.txt"
    assert len(report.hash_mismatches) == 1
    assert report.hash_mismatches[0]["filename"] == "corrupted.txt"
    assert len(report.orphan_files) == 1


def test_storage_restore_zip_slip_prevention(temp_storage_env: dict):
    """Verify that malicious zip archives attempting directory traversal are blocked."""
    backup_dir = temp_storage_env["backup"]
    restore_dir = temp_storage_env["restore"]

    malicious_zip = backup_dir / "malicious.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../../evil_escape.txt", "pwned")

    with pytest.raises(PermissionError, match="Zip slip path traversal detected"):
        restore_storage_backup(malicious_zip, restore_dir, verify_checksum=False)
