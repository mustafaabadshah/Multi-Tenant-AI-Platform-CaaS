# Disaster Recovery, Backup & Restore Runbook

**Status:** IMPLEMENTED AND AUDITED  
**Components:** PostgreSQL Relational Database, Storage Volumes (`STORAGE_PATH`), Qdrant Vector Store, Encryption Keys

---

## 1. Relational Database Backup Procedure

Database backups are automated via `infrastructure/scripts/backup-postgres.ps1` using PostgreSQL's custom archive format (`pg_dump -Fc`):

```powershell
# Create automated timestamped backup:
.\infrastructure\scripts\backup-postgres.ps1 -Host "localhost" -Port 5432 -Database "mmaip_db" -User "postgres" -OutputDir "./backups"
```

The script produces:
1. `mmaip_db_YYYYMMDD_HHMMSS.dump` (Compressed binary archive)
2. `mmaip_db_YYYYMMDD_HHMMSS.manifest.json` (Record metadata, schema version, checksum)
3. `mmaip_db_YYYYMMDD_HHMMSS.sha256` (SHA-256 verification hash)

Verify archive integrity before storing:
```powershell
.\infrastructure\scripts\verify-backup.ps1 -DumpFile "./backups/mmaip_db_YYYYMMDD_HHMMSS.dump"
```

---

## 2. Mandatory Raw File Storage Backup

> [!CRITICAL]
> PostgreSQL backups capture document metadata, extracted text, and vector chunk records. However, PostgreSQL `pg_dump` does NOT contain the raw uploaded PDF/DOCX/image binaries.

* **Local Storage (`STORAGE_BACKEND=local`):**
  Snapshot or archive the persistent volume mounted at `STORAGE_PATH`:
  ```powershell
  # Create storage directory archive
  tar -czf "./backups/storage_tenants_YYYYMMDD.tar.gz" -C "$env:STORAGE_PATH" tenants/
  ```
* **Object Storage (`STORAGE_BACKEND=s3`):**
  Enable S3 Bucket Versioning and Cross-Region Replication on `STORAGE_BUCKET_NAME`.

---

## 3. Database Restore Procedure

To restore into a fresh database:

```powershell
.\infrastructure\scripts\restore-postgres.ps1 -DumpFile "./backups/mmaip_db_YYYYMMDD_HHMMSS.dump" -TargetDatabase "mmaip_db" -Host "localhost" -Port 5432 -User "postgres"
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
