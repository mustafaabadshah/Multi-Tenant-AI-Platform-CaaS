# Disaster Recovery, Backup & Restore Runbook

**Status:** IMPLEMENTED AND AUDITED  
**Components:** PostgreSQL Relational Database, Storage Volumes (`STORAGE_PATH`), Qdrant Vector Store, Encryption Keys

---

## 1. Relational Database Backup Procedure

Database backups are automated via `infrastructure/scripts/backup-postgres.ps1` using PostgreSQL's custom archive format (`pg_dump -Fc`). Prerequisite: `pg_dump`, `pg_restore`, and `psql` must be on `PATH`; when they are missing the scripts report simulation or partial verification and exit non-zero.

```powershell
# Preferred: set DATABASE_SYNC_URL (or DATABASE_URL) in the environment, then:
.\infrastructure\scripts\backup-postgres.ps1 -BackupDir "./backups"

# Or pass an explicit connection string (contains credentials; avoid shell history):
.\infrastructure\scripts\backup-postgres.ps1 -DatabaseUrl "postgresql://<user>:<password>@<host>:5432/<database>" -BackupDir "./backups"
```

The script produces:
1. `mmaip_backup_YYYYMMDD_HHMMSS.dump` (compressed custom-format archive)
2. `mmaip_backup_YYYYMMDD_HHMMSS.dump.manifest.json` (metadata, size, SHA-256)
3. `mmaip_backup_YYYYMMDD_HHMMSS.dump.sha256` (SHA-256 verification sidecar)

Verify archive integrity before storing:
```powershell
.\infrastructure\scripts\verify-backup.ps1 -BackupFilePath "./backups/mmaip_backup_YYYYMMDD_HHMMSS.dump"
```

---

## 2. Mandatory Raw File Storage Backup

> [!CRITICAL]
> PostgreSQL backups capture document metadata, extracted text, and vector chunk records. However, PostgreSQL `pg_dump` does NOT contain the raw uploaded PDF/DOCX/image binaries.

* **Local Storage (`STORAGE_BACKEND=local`):**
  Archive the persistent volume mounted at `STORAGE_PATH` with the repository script:
  ```powershell
  # Create a timestamped ZIP plus manifest and SHA-256 sidecar
  .\infrastructure\scripts\backup-storage.ps1 -StoragePath $env:STORAGE_PATH -BackupDir "./backups"
  ```
  Artifacts: `mmaip_storage_backup_YYYYMMDD_HHMMSS.zip`, `.zip.manifest.json`, `.zip.sha256`.
  Restore into a target directory with:
  ```powershell
  .\infrastructure\scripts\restore-storage.ps1 -ArchiveFilePath "./backups/mmaip_storage_backup_YYYYMMDD_HHMMSS.zip" -TargetStoragePath $env:STORAGE_PATH -ConfirmRestore
  ```
* **Object Storage (`STORAGE_BACKEND=s3`):**
  Enable S3 Bucket Versioning and Cross-Region Replication on `STORAGE_BUCKET_NAME`.

---

## 3. Database Restore Procedure

The target database must already exist. The connection URL is redacted from script output. Restore requires the explicit `-ConfirmRestore` safety switch:

```powershell
$env:TARGET_DATABASE_URL = "postgresql://<user>:<password>@<host>:5432/<target_database>"
.\infrastructure\scripts\restore-postgres.ps1 -BackupFilePath "./backups/mmaip_backup_YYYYMMDD_HHMMSS.dump" -TargetDatabaseUrl $env:TARGET_DATABASE_URL -ConfirmRestore
```

---

## 4. Qdrant Vector Recovery Procedure

Qdrant relies on the **Authoritative PostgreSQL Rebuild Pattern**. PostgreSQL stores the master copy of all `DocumentChunk` records and embedding models. In the event of catastrophic Qdrant index corruption:
1. Re-provision empty Qdrant instance.
2. Trigger repository re-indexing (`POST /api/v1/documents/{id}/reprocess` or batch CLI script).
3. Embeddings are re-upserted idempotently without data loss.

---

## 5. Encryption Key Recovery

* If `SECRET_ENCRYPTION_KEY` is lost, encrypted BYOK credentials cannot be decrypted.
* Back up keys in enterprise secrets storage (e.g. AWS Secrets Manager or Render Environment Variables).
* When rotating keys, set `PREVIOUS_SECRET_KEYS` to the old key before rotating, then execute:
  ```powershell
  python -m app.commands.rotate_encryption_keys
  ```
