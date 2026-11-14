# M11 Stage 3b - Paired Backup/Restore Validation Drill

| Field | Value |
|---|---|
| Date | 2026-11-12 |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Drill workspace | `C:\Users\MUSTAF~1\AppData\Local\Temp\m11_backup_drill_95578b0b` (disposable, deleted after evidence capture) |
| Host shell | Windows PowerShell 5.1.19041.6456 |
| Database topology | Disposable PostgreSQL 16.15 + pgvector 0.8.7 container (`pgvector/pgvector:pg16`, port 55433) |
| Storage topology | Local filesystem only (`LocalStorageProvider`, `tenants/<tenant_id>/...`) |
| Data | Synthetic tenant, user, role, membership, knowledge base, two plain-text documents (156 bytes total) |
| Real user data | None |
| Cloud calls | None |
| Package installs | None |
| Git mutations | None |

## Verdict

**`LOCAL_PAIRED_DRILL = PASS`**

The local PostgreSQL plus local-filesystem paired backup/restore data path was executed end to end. The restored database matched the source database, both stored objects restored with matching SHA-256 hashes, database `file_path` values resolved in the restored storage root, and a deliberately missing object was detected by verification.

This PASS is bounded. The repository scripts as shipped did **not** execute under Windows PowerShell 5.1 because all six scripts fail to parse (see Section 10.1). The drill used verbatim copies re-encoded as UTF-8 with BOM in the disposable workspace, plus temporary `pg_dump`/`pg_restore` shims that proxy into the disposable container because no PostgreSQL client tools are installed on the host. No repository script was edited.

| Verdict item | Result |
|---|---|
| `LOCAL_PAIRED_DRILL` | **PASS** |
| Repository scripts as shipped on Windows PowerShell 5.1 | **FAIL (parse error)** |
| Repository scripts after UTF-8/BOM normalization | **PASS** (logic executed) |
| S3/R2 or other object-store backup | **NOT TESTED** |
| Provider PITR / WAL archiving | **NOT TESTED** |
| Encryption-key escrow | **NOT TESTED / EXTERNAL REQUIREMENT** |

---

## 1. What was reviewed

- `infrastructure/scripts/backup-postgres.ps1`
- `infrastructure/scripts/backup-storage.ps1`
- `infrastructure/scripts/backup-paired.ps1`
- `infrastructure/scripts/restore-postgres.ps1`
- `infrastructure/scripts/restore-storage.ps1`
- `infrastructure/scripts/verify-backup.ps1`
- `docs/runbooks/backup-and-recovery.md`
- `docker-compose.yml`, specifically `postgres_data:/var/lib/postgresql/data` and `backend_storage:/app/data/storage` with `STORAGE_BACKEND=local` and `STORAGE_PATH=/app/data/storage`

No source file or repository script was modified.

## 2. Script capabilities and safety defaults

| Asset | Backend actually supported | Behaviour | Safety defaults and gaps |
|---|---|---|---|
| `backup-postgres.ps1` | PostgreSQL only | `pg_dump --format=c` custom archive, SHA-256 sidecar, JSON manifest (`format = custom_archive_v1`). | If `pg_dump` is missing it prints "Simulation Mode / Script syntax validated" and **exits 0 with no artifact**. It does not record the Alembic revision despite the docstring claim. No encryption, retention, offsite copy, WAL/PITR, or per-tenant export. |
| `backup-storage.ps1` | Local filesystem only | Recursively hashes every file under `StoragePath`, writes a ZIP with `Compress-Archive`, writes archive SHA-256 and a manifest containing every relative path, size, and hash. | Local path only; no S3/R2, bucket versioning, object versions, delete markers, lifecycle, or inventory. It creates a missing storage directory instead of failing. It archives the whole root, not only `tenants/`. Relative paths are built with `Substring` on `Resolve-Path` output, which is fragile when short/long path forms differ (observed in Section 10.3). No encryption at rest. |
| `backup-paired.ps1` | PostgreSQL + local filesystem | Runs the database backup, then the storage backup, then writes a paired manifest linking the two artifacts by name, size, and SHA-256. | Sequential, not atomic; no quiesce, LSN, snapshot ID, or write freeze. No `restore-paired.ps1` counterpart. It selects the newest manifest by `LastWriteTime`; a simulation-mode DB backup can leave a stale manifest and the script will still report `COMPLETED` (observed in Section 10.2). |
| `restore-postgres.ps1` | PostgreSQL only | Verifies SHA-256 and TOC, then `pg_restore --clean --if-exists --no-owner --no-privileges`. | Requires `-ConfirmRestore`; refusal without it was verified (exit 1). Does not create the target database, does not refuse a target equal to the source, and does not require an empty target. `--clean` can drop existing objects. Prints the full target URL, including the password, to the console/log. If `pg_restore` is missing it enters simulation mode and exits 0 without restoring. |
| `restore-storage.ps1` | Local filesystem only | Verifies archive SHA-256 if a sidecar exists, extracts with `Expand-Archive -Force`, then verifies every manifest file by SHA-256 and counts missing/corrupted files. | Requires `-ConfirmRestore`; refusal without it was verified (exit 1). Overwrites an existing target and does not delete extra files. Despite the comment claiming path-traversal prevention, the script does not validate ZIP entry paths before extraction. Missing files and hash mismatches cause `Write-Error` and exit 1 (verified). No S3 restore. |
| `verify-backup.ps1` | PostgreSQL dump only | Verifies SHA-256 and runs `pg_restore --list` to read the TOC; counts `TABLE DATA` blocks. | No restore, no row counts, no storage verification. If `pg_restore` is missing it skips the TOC check and exits 0. |
| Runbook | Documentation | Claims "IMPLEMENTED AND AUDITED" and gives commands for DB backup/restore, storage tar, Qdrant rebuild, and key handling. | Commands do not match the scripts: runbook uses `-Host`, `-Port`, `-Database`, `-User`, `-OutputDir`, `-DumpFile`, and `-TargetDatabase`, while the scripts accept `-DatabaseUrl`, `-BackupDir`, `-BackupFilePath`, and `-TargetDatabaseUrl`. Runbook artifact names (`mmaip_db_*`) also differ from script names (`mmaip_backup_*`). The storage example is `tar -czf`, while the script uses ZIP. S3 guidance is policy text only; no S3 backup script exists. |

**Compose storage configuration:** `docker-compose.yml` mounts the named volume `backend_storage` at `/app/data/storage` and sets `STORAGE_BACKEND=local`. The Postgres data volume is `postgres_data`. The compose stack therefore exercises local-volume storage only; it is not an S3/R2 deployment.

**Effective support answer:** PostgreSQL only for the database; local filesystem only for document storage; paired orchestration is sequential and local; S3/R2 is not implemented in any backup/restore script.

## 3. Drill topology

| Element | Value |
|---|---|
| Container | `m11drill_95578b0b` |
| Image | `pgvector/pgvector:pg16` (local image ID `sha256:31c6867f8fd38f4b75885aeb954d43cd4c2be714659d72b0dc4ae55bdcd9e967`) |
| PostgreSQL | 16.15 (Debian 16.15-1.pgdg12+2), x86_64 |
| pgvector | 0.8.7 |
| Port | `55433 -> 5432/tcp` |
| Source database | `m11_drill_src` |
| Restore database | `m11_drill_restore` (new, empty before restore) |
| DB user | `drilluser` (synthetic; password omitted from this document) |
| Alembic head | `0010_m10_remediation_schema_alignment` |
| Source storage | `storage_src` |
| Restored storage | `storage_restored` (new, empty before restore) |
| Missing-object copy | `storage_missing` (copy of restored storage with one object deleted) |
| Backup directory | `backups` |
| Docker resources | One disposable container; no named volume was created. Pre-existing Docker containers were left untouched. |

Resource check before start: Docker server 25.0.3, image already present locally, host free physical memory approximately 1.04 GB and Docker VM memory approximately 3.9 GB. The container started and accepted connections quickly, so the PostgreSQL path was used and the SQLite fallback was not needed.

## 4. Synthetic data preparation

The database was migrated with the repository Alembic chain:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://drilluser:<synthetic-password>@127.0.0.1:55433/m11_drill_src"
$env:DATABASE_SYNC_URL = "postgresql://drilluser:<synthetic-password>@127.0.0.1:55433/m11_drill_src"
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Result: `ALEMBIC_EXIT=0`, all ten revisions applied through `0010_m10_remediation_schema_alignment`.

A small script using the application models and `LocalStorageProvider` created the synthetic rows and stored the objects. It used the application key builder, not hand-written paths:

```text
tenants/11111111-1111-4111-8111-111111111111/kbs/55555555-5555-4555-8555-555555555555/docs/66666666-6666-4666-8666-666666666666/v1/m11_drill_alpha.txt
tenants/11111111-1111-4111-8111-111111111111/kbs/55555555-5555-4555-8555-555555555555/docs/77777777-7777-4777-8777-777777777777/v1/m11_drill_beta.txt
```

Seed result: `SEED_OK`, two stored files, 156 bytes total.

| Entity | ID | Key fields |
|---|---|---|
| Tenant | `11111111-1111-4111-8111-111111111111` | name `M11 Drill Tenant`, slug `m11-drill-tenant` |
| User | `22222222-2222-4222-8222-222222222222` | `m11.drill.user@example.invalid`, `M11 Drill User` |
| Role | `33333333-3333-4333-8333-333333333333` | `m11_drill_admin` |
| Membership | `44444444-4444-4444-8444-444444444444` | tenant + user above |
| Knowledge base | `55555555-5555-4555-8555-555555555555` | `M11 Drill Knowledge Base` |
| Document alpha | `66666666-6666-4666-8666-666666666666` | `m11_drill_alpha.txt`, 80 bytes |
| Document beta | `77777777-7777-4777-8777-777777777777` | `m11_drill_beta.txt`, 76 bytes |
| Version alpha | `88888888-8888-4888-8888-888888888888` | version 1 for alpha |
| Version beta | `99999999-9999-4999-8999-999999999999` | version 1 for beta |

Source object hashes:

| Object | Bytes | SHA-256 |
|---|---:|---|
| `m11_drill_alpha.txt` | 80 | `be2b5401de34d48e5e5e1afe144eca6c3462a00c9f192dbe5c183b56c98d9726` |
| `m11_drill_beta.txt` | 76 | `8ab74587daf862e1d74e340f0ecc137ae8ba0fa643da6a56c6ed2fcf676a547d` |

Source row counts before backup: tenants 1, users 1, roles 1, memberships 1, knowledge bases 1, documents 2, document versions 2.

## 5. Backup execution

### 5.1 Repository-script execution defect and workaround

All six scripts are UTF-8 without BOM and each contains exactly one U+2014 em dash inside a double-quoted `Write-Host` string. Windows PowerShell 5.1 decodes the file as ANSI, the em dash bytes decode as three Windows-1252 characters, including U+201D, and PowerShell treats the resulting right smart quote as a string terminator. Every script fails to parse. The exact errors are in Section 10.1.

Because the repository must not be edited, the drill copied each script verbatim to the disposable workspace and re-encoded the copy as UTF-8 with BOM. No other change was made. The copies then parsed with zero errors and were used for the drill. This is a test workaround, not a repository fix.

Host PostgreSQL client tools are absent (`pg_dump`, `pg_restore`, and `psql` are not on `PATH`). Temporary `pg_dump.cmd`/`pg_restore.cmd` shims in the drill workspace proxied the exact script arguments into the disposable container with `docker exec`, copied the dump back, and converted the drill host/port to the container-local PostgreSQL endpoint. The repository scripts and their flags were unchanged.

### 5.2 Command

```powershell
$env:PATH = "$drill\bin;$env:PATH"
$env:DATABASE_SYNC_URL = "postgresql://drilluser:<synthetic-password>@127.0.0.1:55433/m11_drill_src"
$env:STORAGE_PATH = "C:\Users\Mustafa Badshah\AppData\Local\Temp\m11_backup_drill_95578b0b\storage_src"
& "$drill\scripts_copy\backup-paired.ps1" -BackupDir "$drill\backups"
```

Result: `BACKUP_EXIT=0`. The paired script reported:

```text
 [PASS] Paired Disaster Recovery Backup Completed!
  Paired Manifest: ...\backups\mmaip_paired_backup_20261112_171142.manifest.json
  Database Dump:   mmaip_backup_20261112_171143.dump
  Storage Archive: mmaip_storage_backup_20261112_171146.zip
```

### 5.3 Artifacts and hashes

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `mmaip_backup_20261112_171143.dump` | 154534 | `4907676A4B62B21B6FA413ABE0692780E28A81044FFE326DCEF6407CE7DE2072` |
| `mmaip_backup_20261112_171143.dump.manifest.json` | 297 | `CB126E6740EE9EAA88E027C15E8F9437383E98A077E267DBC424E6A317AEE6E7` |
| `mmaip_backup_20261112_171143.dump.sha256` | 101 | `4B3A488582928E869419BE48F855E8204084048E85B91831918C7E3B8C40B060` |
| `mmaip_paired_backup_20261112_171142.manifest.json` | 1151 | `3CA4A80D19E385A702ED8EA496689BB53E5B36287D30AB35F3DB4CE0DB89EEE9` |
| `mmaip_storage_backup_20261112_171146.zip` | 2438 | `09DEA67C8CD9CB6C378B8A54E241304B38B4F13ADAA01768C7FF4CB4C20BFCA3` |
| `mmaip_storage_backup_20261112_171146.zip.manifest.json` | 1608 | `D27373157B6E27003F3950B874AF2E7F1DEFC24CCAA59751AC3EED25FA585DFD` |
| `mmaip_storage_backup_20261112_171146.zip.sha256` | 108 | `1F46A01780E1D1DB456871A7986F60F6A6533CF8DD068D6780A405414AC95957` |

The ZIP contains two file entries under `tenants/...` (eight entries including directories). The paired manifest was independently checked:

```text
db_file_exists=true
db_size_matches=true
db_sha_matches_manifest=true
storage_file_exists=true
storage_size_matches=true
storage_sha_matches_manifest=true
total_files_2=true
total_bytes_156=true
status_completed=true
PAIRED_MANIFEST_PASS
```

`verify-backup.ps1` reported:

```text
 [PASS] Checksum matches recorded value: 4907676A4B62B21B6FA413ABE0692780E28A81044FFE326DCEF6407CE7DE2072
 [PASS] Archive TOC readable. Found 47 table data blocks.
VERIFY_EXIT=0
```

### 5.4 Path-normalisation issue observed

The first storage backup passed the storage path in 8.3 short form (`C:\Users\MUSTAF~1\...`). `Resolve-Path` returned the long form (`C:\Users\Mustafa Badshah\...`), while the enumerated file names retained the short form, so the `Substring` calculation produced manifest paths beginning `age_src/tenants/...` instead of `tenants/...`. The ZIP entries themselves were correct. The backup was rerun with the long-form storage path; the main artifact set above uses the corrected manifest. This is recorded as a robustness defect in Section 10.3.

## 6. Restore execution

The source database and source storage were left intact for comparison. Disaster was simulated by restoring into new, empty targets.

### 6.1 Database restore

The target database was created explicitly because `restore-postgres.ps1` does not create it:

```powershell
docker exec m11drill_95578b0b psql -U drilluser -d postgres `
  -c "DROP DATABASE IF EXISTS m11_drill_restore;" `
  -c "CREATE DATABASE m11_drill_restore;"
```

Restore command and result:

```powershell
& "$drill\scripts_copy\restore-postgres.ps1" `
  -BackupFilePath "$drill\backups\mmaip_backup_20261112_171143.dump" `
  -TargetDatabaseUrl "postgresql://drilluser:<synthetic-password>@127.0.0.1:55433/m11_drill_restore" `
  -ConfirmRestore
```

```text
 [PASS] Checksum matches recorded value: 4907676A4B62B21B6FA413ABE0692780E28A81044FFE326DCEF6407CE7DE2072
 [PASS] Archive TOC readable. Found 47 table data blocks.
Restoring database schema and data...
 [PASS] pg_restore completed cleanly.
RESTORE_EXIT=0
```

### 6.2 Storage restore

```powershell
& "$drill\scripts_copy\restore-storage.ps1" `
  -ArchiveFilePath "$drill\backups\mmaip_storage_backup_20261112_171146.zip" `
  -TargetStoragePath "$drill\storage_restored" `
  -ConfirmRestore
```

```text
 [PASS] Archive SHA-256 verified: 09DEA67C8CD9CB6C378B8A54E241304B38B4F13ADAA01768C7FF4CB4C20BFCA3
Extracting storage archive to ...\storage_restored...
Verifying restored files against manifest...
Restoration Verification Summary:
  Files Verified:  2 / 2
  Missing Files:   0
  Corrupted Files: 0
 [PASS] Storage restoration completed successfully with 100% integrity.
```

The restored storage root contains exactly two files at the expected tenant keys.

## 7. Verification results

The verifier compared every public table in both databases, the key business rows, document/version fields, direct filesystem hashes, application-provider reads, and database-to-storage path resolution.

| Check | Expected | Actual | Result |
|---|---|---|---|
| Alembic revision | `0010_m10_remediation_schema_alignment` | same | PASS |
| Public table set | 47 tables in source | 47 tables in restore | PASS |
| Every table row count | source == restore | 47/47 equal | PASS |
| `tenants` | 1 | 1 | PASS |
| `users` | 1 | 1 | PASS |
| `roles` | 1 | 1 | PASS |
| `tenant_memberships` | 1 | 1 | PASS |
| `knowledge_bases` | 1 | 1 | PASS |
| `documents` | 2 | 2 | PASS |
| `document_versions` | 2 | 2 | PASS |
| Tenant name/slug/id | exact | exact | PASS |
| User email/full name/id | exact | exact | PASS |
| Role name/id | exact | exact | PASS |
| Membership tenant/user/id | exact | exact | PASS |
| Knowledge base name/tenant/id | exact | exact | PASS |
| Document alpha fields | filename, safe filename, path, size, hash, MIME exact | exact | PASS |
| Document beta fields | filename, safe filename, path, size, hash, MIME exact | exact | PASS |
| Version rows | path, size, hash match document | match | PASS |
| Alpha object in restored root | exists, hash matches | exists, hash matches | PASS |
| Beta object in restored root | exists, hash matches | exists, hash matches | PASS |
| App-provider read | `LocalStorageProvider.get()` returns same bytes | same bytes | PASS |
| Paired consistency | DB `file_path` starts `tenants/<tenant_id>/` and resolves under restored root | both resolved | PASS |
| Tenant/KB ownership | document tenant equals KB tenant | equal | PASS |
| Missing-object detection | verifier fails and reports | failed with exit 1 | PASS |
| Repository missing-file detection | restore-storage fails and reports | failed with exit 1 | PASS |
| Encryption-key scan | 0 marker matches | 0/23 files | PASS |
| ConfirmRestore refusal | exit 1 without switch | exit 1 for both restores | PASS |
| Paired manifest integrity | sizes and hashes match artifacts | all match | PASS |

Verifier final line: `VERIFICATION_PASS` (`VERIFY_DRILL_EXIT=0`).

Restored object hashes observed by direct filesystem read, application provider read, and database `file_hash`:

| Object | Restored SHA-256 |
|---|---|
| `m11_drill_alpha.txt` | `be2b5401de34d48e5e5e1afe144eca6c3462a00c9f192dbe5c183b56c98d9726` |
| `m11_drill_beta.txt` | `8ab74587daf862e1d74e340f0ecc137ae8ba0fa643da6a56c6ed2fcf676a547d` |

## 8. Missing-object scenario

Two independent checks were performed.

### 8.1 Delete one restored object and verify

A copy of the restored storage was made, the beta object was deleted, and the verifier was run against the same restored database:

```text
77777777-7777-4777-8777-777777777777: MISSING_OBJECT tenants/11111111-1111-4111-8111-111111111111/kbs/55555555-5555-4555-8555-555555555555/docs/77777777-7777-4777-8777-777777777777/v1/m11_drill_beta.txt
MISSING_OBJECT_DETECTED count=1
VERIFICATION_FAIL
  FAILURE: missing restored object: tenants/11111111-1111-4111-8111-111111111111/kbs/55555555-5555-4555-8555-555555555555/docs/77777777-7777-4777-8777-777777777777/v1/m11_drill_beta.txt
VERIFY_MISSING_EXIT=1
```

The alpha object still verified, proving the failure was specific to the deleted object.

### 8.2 Repository restore-storage verification with a damaged archive

A disposable archive containing only the alpha object was created, while the copied manifest still listed both objects. The repository verification logic reported:

```text
WARNING: Missing restored file:
tenants/11111111-1111-4111-8111-111111111111/kbs/55555555-5555-4555-8555-555555555555/docs/77777777-7777-4777-8777-777777777777/v1/m11_drill_beta.txt
Restoration Verification Summary:
  Files Verified:  1 / 2
  Missing Files:   1
  Corrupted Files: 0
... Storage restoration completed with validation errors!
DAMAGED_RESTORE_EXIT=1
```

This confirms the repository's per-file manifest verification detects a missing object and returns a non-zero exit status.

## 9. Encryption keys and escrow

The backup scripts never read or serialise `SECRET_ENCRYPTION_KEY` or `PREVIOUS_SECRET_KEYS`. They read only `DATABASE_SYNC_URL`/`DATABASE_URL`, `STORAGE_PATH`, and `BackupDir`. The DB dump contains relational data only; the scripts do not copy `.env` files, key files, or environment variables into artifacts.

During the successful backup, unique synthetic marker values were supplied through `SECRET_ENCRYPTION_KEY` and `SECRET_KEY`. A byte scan of all backup artifacts, the paired manifests, the checksum sidecars, the re-check backup set, and the available script logs searched for those markers, the synthetic database password, and the literal strings `SECRET_ENCRYPTION_KEY=` and `PREVIOUS_SECRET_KEYS=`:

```text
SCANNED_FILES=23
MATCHES=0
KEY_MATERIAL_SCAN_PASS
```

The synthetic dataset contained no assistant/provider BYOK rows, so no encrypted ciphertext was present in the dump. If such rows exist in a real database, the dump will contain ciphertext columns, but not the Fernet key material needed to decrypt them. Key escrow is an external requirement: `SECRET_ENCRYPTION_KEY` and any `PREVIOUS_SECRET_KEYS` values must be stored in a secrets manager and restored separately, never placed in backup logs, manifests, filenames, or the repository. Losing them makes encrypted BYOK credentials unrecoverable even when the database restore succeeds.

Separate credential-handling issue: `restore-postgres.ps1` prints the complete `TargetDatabaseUrl`, including the password, to the console/log (`restore-postgres.ps1:49`). The drill output line was redacted for this document, but the script does leak the target credential to its output stream. This is not an encryption-key export, but it must be fixed before production use.

## 10. Failures and defects observed

### 10.1 All six repository scripts fail to parse under Windows PowerShell 5.1

Each file is UTF-8 without BOM and contains one U+2014 em dash in a double-quoted string. Exact parser results:

```text
FILE=backup-postgres.ps1 PARSE_ERRORS=1
  L96C35: The string is missing the terminator: ".
FILE=backup-storage.ps1 PARSE_ERRORS=4
  L79C54: Unexpected token 'bytes' in expression or statement.
  L79C53: Missing closing ')' in expression.
  L79C59: Unexpected token ')' in expression or statement.
  L134C46: The string is missing the terminator: ".
FILE=backup-paired.ps1 PARSE_ERRORS=1
  L96C71: The string is missing the terminator: ".
FILE=restore-postgres.ps1 PARSE_ERRORS=1
  L82C46: The string is missing the terminator: ".
FILE=restore-storage.ps1 PARSE_ERRORS=1
  L116C84: The string is missing the terminator: ".
FILE=verify-backup.ps1 PARSE_ERRORS=1
  L71C48: The string is missing the terminator: ".
```

Non-ASCII inspection:

```text
backup-postgres.ps1: utf8_bom=False non_ascii=1
  L48 U+2014 :: Write-Host "  MM AI Platform <U+2014> PostgreSQL Backup Procedure"
backup-storage.ps1: utf8_bom=False non_ascii=1
  L53 U+2014 :: Write-Host "  MM AI Platform <U+2014> Storage Disaster Recovery Backup"
backup-paired.ps1: utf8_bom=False non_ascii=1
  L42 U+2014 :: Write-Host "  MM AI Platform <U+2014> Paired Disaster Recovery Backup"
restore-postgres.ps1: utf8_bom=False non_ascii=1
  L47 U+2014 :: Write-Host "  MM AI Platform <U+2014> PostgreSQL Disaster Recovery Restore"
restore-storage.ps1: utf8_bom=False non_ascii=1
  L48 U+2014 :: Write-Host "  MM AI Platform <U+2014> Storage Disaster Recovery Restore"
verify-backup.ps1: utf8_bom=False non_ascii=1
  L30 U+2014 :: Write-Host "  MM AI Platform <U+2014> Backup Integrity Verification"
```

Impact: none of the scripts can be executed directly with Windows PowerShell 5.1, which is the default shell on this host. PowerShell 7 (`pwsh`) is not installed. The drill's BOM-normalised copies are the only reason the backup/restore logic could be exercised.

### 10.2 Simulation mode and stale pairing

With no `pg_dump` on `PATH`, `backup-postgres.ps1` returns success without producing a dump:

```text
WARNING: pg_dump binary not found in PATH. Ensure PostgreSQL client tools are installed.
Simulation Mode / Script syntax validated.
SIM_BACKUP_DB_EXIT=0
SIM_ARTIFACTS=0
```

With an empty backup directory, `backup-paired.ps1` then fails, but only because indexing the empty manifest list throws:

```text
Cannot index into a null array.
SIM_BACKUP_PAIRED_EXIT=1
```

With a stale DB manifest present (and no dump file at all), `backup-paired.ps1` reported success:

```text
 [PASS] Paired Disaster Recovery Backup Completed!
  Database Dump:   mmaip_backup_20261112_171143.dump
  Storage Archive: mmaip_storage_backup_20261112_171808.zip
STALE_PAIR_EXIT=0
```

The generated paired manifest had `"status": "COMPLETED"` and linked the stale database manifest and a new storage archive. The referenced dump was not present in the directory. This is a false-success path: a monitoring system would record a completed paired backup that contains no fresh database backup. `backup-paired.ps1` must fail closed if the DB backup produced no new artifact, verify the dump file exists and is fresh, and only then write the paired manifest.

### 10.3 Fragile storage relative-path calculation

When the storage path was supplied in 8.3 short form, the manifest contained paths like:

```text
relative_path: age_src/tenants/11111111-1111-4111-8111-111111111111/kbs/...
```

instead of:

```text
relative_path: tenants/11111111-1111-4111-8111-111111111111/kbs/...
```

The ZIP entries were correct. The mismatch comes from `backup-storage.ps1:67` subtracting the length of a `Resolve-Path` string from a `Get-ChildItem` full name that may use a different short/long representation. Rerunning with the long-form path produced the corrected manifest. The script should normalise both paths through the same `[System.IO.Path]::GetFullPath`/resolved provider path before computing relative paths.

### 10.4 Runbook drift

`docs/runbooks/backup-and-recovery.md` is marked "IMPLEMENTED AND AUDITED" but its commands do not match the scripts:

| Runbook invocation | Actual script parameters |
|---|---|
| `-Host`, `-Port`, `-Database`, `-User`, `-OutputDir` | `-DatabaseUrl`, `-BackupDir` |
| `-DumpFile` | `-BackupFilePath` |
| `-TargetDatabase`, `-Host`, `-Port`, `-User` | `-TargetDatabaseUrl` |
| `mmaip_db_YYYYMMDD_HHMMSS.dump` / `.manifest.json` | `mmaip_backup_YYYYMMDD_HHMMSS.dump` / `.dump.manifest.json` |
| `tar -czf ... storage_tenants_...tar.gz` | `Compress-Archive` to `mmaip_storage_backup_*.zip` |

Following the runbook verbatim would fail parameter binding. The runbook also describes S3 versioning as the object-store policy but provides no executable S3 backup or restore procedure.

### 10.5 Restore safety and credential handling

Verified positive safety control: both restore scripts refuse to run without `-ConfirmRestore` and exit 1. Verified gaps:

- `restore-postgres.ps1` does not create the target database (the drill had to create it).
- It does not compare the target to the source and does not require a disposable or empty target.
- `--clean --if-exists` can drop objects in an existing target.
- It prints the full target URL, including the password, to the console/log.
- `restore-storage.ps1` extracts with `-Force` into the target and does not require an empty directory or take a pre-restore snapshot.
- `restore-storage.ps1` does not validate archive entry paths for zip-slip despite the comment claiming path-traversal prevention.
- There is no `restore-paired.ps1`; database and storage restore are separate manual operations with no coordinated cutover or consistency check built into the scripts.

### 10.6 No object-store path

There is no S3/R2 backup or restore implementation. `backup-storage.ps1` and `restore-storage.ps1` are local-filesystem only, and `docker-compose.yml` uses the local `backend_storage` volume. A staging deployment that uses S3 cannot use these scripts to protect its documents.

## 11. Limitations of this drill

- PostgreSQL plus local filesystem only. No S3, R2, MinIO, bucket versioning, object versions, lifecycle rules, cross-region replication, or cloud provider snapshot was tested.
- No PITR, WAL archiving, LSN consistency, or provider-managed continuous backup. The dump is a point-in-time logical export, not a recoverable WAL timeline.
- The backup is sequential and not atomic. No writes were occurring during the drill, so consistency under concurrent ingestion was not tested.
- Data volume is tiny (156 bytes, two objects). No large file, many-file, throughput, timeout, or storage-quota behaviour was measured.
- No chunk, embedding, conversation, assistant, BYOK, audit, or evaluation rows were seeded. `chunk_embeddings` and related tables were empty. pgvector restore correctness for populated embedding columns was not exercised beyond the schema.
- No Qdrant backup or rebuild was tested. The application's documented strategy is to rebuild vectors from PostgreSQL, but that was out of scope here.
- No encryption at rest for the dump or ZIP. They are plaintext artifacts in the local backup directory.
- No key escrow or rotation drill. The key scan proves the key material was not exported by these scripts, not that an operator can recover it after a disaster.
- No retention policy, scheduling, monitoring, alerting, offsite copy, or restore-time objective was tested.
- No zip-slip, malicious archive, symlink, or path-traversal test.
- No tenant-scoped partial restore, tenant deletion, or GDPR erasure procedure was tested.
- The host lacked PostgreSQL client tools, so container-proxied shims were used. The drill validates the scripts' logic and SQL dump/restore, but not a host-client installation.
- The repository scripts had to be BOM-normalised in the disposable workspace. The drill therefore does not prove that the files as committed can run on Windows PowerShell 5.1; it proves the opposite in Section 10.1.

## 12. Mandatory before real documents

1. **Fix the script encoding defect.** Add a UTF-8 BOM or remove the U+2014 characters, then rerun this drill from the actual repository files on Windows PowerShell 5.1. Alternatively, standardise on PowerShell 7 and document that prerequisite. Until then, the repository's DR scripts are not executable as shipped.
2. **Implement object-store backup.** Enable versioning, lifecycle, inventory, and cross-region replication for the live S3/R2 bucket; define and test a restore procedure. The current local ZIP path does not protect the staging/production storage backend.
3. **Enable provider PITR and define RPO/RTO.** Use managed PostgreSQL continuous backup or WAL archiving, verify restore to a timestamp, and record the achievable RPO/RTO. `pg_dump` alone is not PITR.
4. **Create encryption-key escrow.** Store `SECRET_ENCRYPTION_KEY` and `PREVIOUS_SECRET_KEYS` in a secrets manager outside the backup artifacts, with access control, rotation, and a tested recovery procedure. Never write them to backup logs or manifests.
5. **Schedule and monitor backups.** Add automated paired backups, retention, integrity checks, alerting on failure or staleness, and periodic restore drills. Fix the simulation/stale-pairing false-success paths first.
6. **Fix paired consistency.** Add a `restore-paired.ps1` or equivalent orchestrated restore with a quiesce/snapshot point, LSN or backup ID, object inventory, and a hard failure when either half is missing or stale. Do not claim `COMPLETED` without a fresh DB dump.
7. **Harden restore safety.** Refuse source/production targets, create and validate an empty target database, require an empty or explicitly approved storage target, take a pre-restore backup, redact passwords from output, and validate ZIP entry paths.
8. **Rehearse on staging with realistic data.** Use production-like file sizes and row counts, concurrent ingestion if applicable, real S3/R2, real key escrow, and the corrected runbook. Measure restore time and verify application-level reads after restore.
9. **Correct the runbook.** Replace parameter names and artifact names with the actual script contract, document the PostgreSQL client prerequisite, and remove or replace the non-existent S3 procedure.
10. **Encrypt backup artifacts at rest and restrict access.** The current dump and ZIP are plaintext; use encrypted storage, TLS transport, least-privilege credentials, and audit logging.
11. **Test tenant-scoped recovery and deletion.** Verify that a single tenant can be restored without cross-tenant data, and that deletion/erasure procedures also remove stored objects, versions, and backups as required.
12. **Test a populated vector restore.** Seed chunks and embeddings, restore, and verify pgvector rows and retrieval. This drill verified the schema and relational rows but left vector tables empty.

## 13. Cleanup

After the evidence above was captured, cleanup removed only the disposable container and its anonymous data, then deleted the drill workspace:

```powershell
docker rm -f -v m11drill_95578b0b
Remove-Item -LiteralPath "C:\Users\MUSTAF~1\AppData\Local\Temp\m11_backup_drill_95578b0b" -Recurse -Force
```

Pre-existing Docker containers (`meta-graph-redis`, `meta-graph-neo4j`) and all pre-existing volumes were left untouched. No repository file other than this document was created or modified.

## 14. Conclusion

The local paired data path is demonstrably recoverable: a PostgreSQL logical dump plus a local storage ZIP restored into new targets with exact row counts, key fields, object hashes, and resolvable database-to-object paths. The missing-object checks fail correctly. The DR data plane is therefore proven for the tested topology.

The operational tooling is not ready. The scripts as committed do not parse on the stated Windows PowerShell environment, `backup-postgres.ps1` can return success without a backup, `backup-paired.ps1` can emit a false `COMPLETED` manifest using a stale database manifest, the storage manifest path calculation is fragile, and the runbook's commands do not match the scripts. S3/R2, PITR, key escrow, encryption at rest, scheduling, retention, and staging rehearsal remain mandatory before real documents.

**`LOCAL_PAIRED_DRILL = PASS`**

---

## 15. Script Remediation (2026-11-12)

This section is appended after the drill evidence above. The original drill record is unchanged. No database, storage, cloud, or real backup path was touched during remediation.

### 15.1 Files changed

| File | Change |
|---|---|
| `infrastructure/scripts/backup-postgres.ps1` | Encoding normalization; simulation mode now fails; help examples use credential placeholders. |
| `infrastructure/scripts/backup-storage.ps1` | Encoding normalization only. |
| `infrastructure/scripts/backup-paired.ps1` | Encoding normalization; fresh-artifact and hash validation; non-zero child exit handling. |
| `infrastructure/scripts/restore-postgres.ps1` | Encoding normalization; target URL redaction; simulation mode now fails; help example sanitized. |
| `infrastructure/scripts/restore-storage.ps1` | Encoding normalization only. |
| `infrastructure/scripts/verify-backup.ps1` | Encoding normalization; missing `pg_restore` is now a non-success partial verification. |
| `docs/runbooks/backup-and-recovery.md` | Parameter and artifact names aligned with the scripts; storage ZIP procedure documented. |
| `docs/m11/M11_BACKUP_RESTORE_DRILL.md` | This appended remediation section. |

### 15.2 Encoding remediation

One consistent policy was applied to all six scripts: **ASCII-only content, saved as UTF-8 with BOM**.

- Each file contained exactly one U+2014 em dash in a double-quoted `Write-Host` string. It was replaced with the ASCII hyphen `-`.
- No other non-ASCII characters were present before or after the change.
- Every file now starts with the UTF-8 BOM (`EF BB BF`) and contains zero characters above U+007F.
- Byte inspection after the fix: `BOM=True non_ascii=0` for all six files.

This makes parsing independent of the code page used by Windows PowerShell 5.1. Future edits to these scripts must keep them ASCII-only and BOM-preserving.

### 15.3 Secret-print removal

- `restore-postgres.ps1` previously printed the complete `TargetDatabaseUrl`, including the password. The line now prints `Target: [REDACTED]`. The URL is still passed directly to `pg_restore`; only console/log output was changed.
- Comment-based help examples in `backup-postgres.ps1` and `restore-postgres.ps1` used the literal `postgres:postgres`. They now use `<user>:<password>` placeholders, so `-?` output does not display a credential-looking value.
- A scan of every `Write-Host`, `Write-Output`, `Write-Warning`, `Write-Error`, `Write-Verbose`, and `Write-Debug` statement in all six scripts for `Url`, `Password`, `Secret`, `Key`, or `Token` variables and literals found no credential-printing statements after the fix.
- Runtime check with a synthetic marker password in a temporary shimmed environment: the restore output contained `Target: [REDACTED]` and did not contain the marker.

### 15.4 Behavioral fixes

**Simulation and partial modes now fail non-zero and are explicitly labeled:**

| Script | Previous behavior | Current behavior |
|---|---|---|
| `backup-postgres.ps1` | Missing `pg_dump`: printed "Simulation Mode / Script syntax validated", exit 0, no artifact. | Prints `SIMULATION MODE: no backup was created. This run is NOT a successful backup.`, exit 2, no artifact. |
| `restore-postgres.ps1` | Missing `pg_restore`: printed "Simulation Mode / Script syntax validated", exit 0, no restore. | Prints simulation warnings, exit 2, no restore. |
| `verify-backup.ps1` | Missing `pg_restore`: skipped the TOC check and exit 0. | Prints `PARTIAL VERIFICATION: checksum-only result. This is NOT a full backup verification.`, exit 2. |

**Stale paired artifacts are rejected.** `backup-paired.ps1` now records a run-start time and, after each child backup:

1. Checks the child exit code.
2. Requires a manifest written during this run (2-second timestamp tolerance).
3. Requires the manifest to reference an artifact.
4. Requires the artifact to exist, to have been written during this run, and to match the manifest size.
5. Recomputes the artifact SHA-256 and requires it to match the manifest.
6. Writes the paired manifest with `status = COMPLETED` only after both database and storage halves pass.

On any failure the script writes an error and exits 1 without creating a paired manifest. The previous null-array failure when no manifest exists is replaced by an explicit error.

**Runbook drift corrected.** `docs/runbooks/backup-and-recovery.md` now uses the actual script contract:

| Old runbook name | Current name |
|---|---|
| `-Host`, `-Port`, `-Database`, `-User`, `-OutputDir` | `-DatabaseUrl`, `-BackupDir` |
| `-DumpFile` | `-BackupFilePath` |
| `-TargetDatabase`, `-Host`, `-Port`, `-User` | `-TargetDatabaseUrl` plus `-ConfirmRestore` |
| `mmaip_db_*` artifacts | `mmaip_backup_*.dump`, `.dump.manifest.json`, `.dump.sha256` |
| `tar -czf` storage example | `backup-storage.ps1` ZIP plus manifest and SHA-256 sidecar |

The runbook also now documents the `pg_dump`/`pg_restore` prerequisite, target-database creation, and the storage restore command.

### 15.5 Parser results

Verification host: Windows PowerShell 5.1.19041.6456 (`powershell.exe -NoProfile`). Command:

```powershell
$errors=$null; [System.Management.Automation.Language.Parser]::ParseFile('<path>', [ref]$null, [ref]$errors) | Out-Null; $errors.Count
```

| Script | Errors before | Errors after | `-?` help exit |
|---|---:|---:|---:|
| `backup-paired.ps1` | 1 | 0 | 0 |
| `backup-postgres.ps1` | 1 | 0 | 0 |
| `backup-storage.ps1` | 4 | 0 | 0 |
| `restore-postgres.ps1` | 1 | 0 | 0 |
| `restore-storage.ps1` | 1 | 0 | 0 |
| `verify-backup.ps1` | 1 | 0 | 0 |

The `-?` invocation only displays comment-based help; it does not execute the script body and did not touch data.

### 15.6 Sandbox verification performed

A disposable sandbox under `%TEMP%\kilo\m11-script-remediation-test` contained one synthetic storage file and synthetic `pg_dump`/`pg_restore` shims. The shims never connected to PostgreSQL; they wrote a fixed test file or printed a fixed TOC line. No real database, storage volume, backup directory, or cloud endpoint was used.

| Test | Result |
|---|---|
| Paired backup happy path with shims | Exit 0; paired manifest `COMPLETED`; database and storage size/hash checks passed. |
| Paired backup with backdated database artifact | Exit 1; `Stale database backup artifact detected`; paired-manifest count unchanged. |
| Paired backup with no `pg_dump` | Child backup exited 2; paired backup failed and wrote no `COMPLETED` manifest. |
| `backup-postgres.ps1` without `pg_dump` | Exit 2; `SIM_ARTIFACTS=0`. |
| `restore-postgres.ps1` with synthetic marker password | Exit 0; output contained `[REDACTED]`; marker absent from output. |
| `verify-backup.ps1` without `pg_restore` | Checksum passed, partial-verification warning printed, exit 2. |

Sandbox artifacts were deleted after the checks. The full paired drill was **not** re-run.

### 15.7 Remaining limitations

- S3/R2/MinIO backup and restore remain unimplemented; the storage scripts are local-filesystem only.
- No PITR, WAL archiving, LSN consistency, or provider continuous backup.
- The paired backup remains sequential and non-atomic; there is no quiesce, snapshot, or write-freeze point.
- The storage relative-path calculation uses `Substring` on `Resolve-Path` output and remains sensitive to short/long path forms (Section 10.3).
- `restore-storage.ps1` still does not validate ZIP entry paths before extraction (no zip-slip guard), and `Expand-Archive -Force` still overwrites the target.
- There is no `restore-paired.ps1` or coordinated restore/cutover procedure.
- Backup artifacts are still unencrypted at rest; no retention, scheduling, monitoring, offsite copy, or key escrow was added.
- Connection URLs are still passed as process arguments to `pg_dump`/`pg_restore`; local process inspection could expose them. Moving to `PGPASSFILE` or a service file is still recommended.
- `backup-storage.ps1` still creates a missing storage directory instead of failing, and an empty storage root still produces a marker archive reported as `COMPLETED`.
- `restore-postgres.ps1` still treats a non-zero `pg_restore` exit code as a warning rather than a hard failure.
- `verify-backup.ps1` now requires `pg_restore` for a full PASS; hosts without PostgreSQL client tools will receive exit 2 (partial verification).

### 15.8 Recommendation

Re-run the full paired backup/restore drill separately from the repository files on Windows PowerShell 5.1, including the missing-object scenario and a scan of console output for credential leakage. This remediation verifies parsing, help loading, encoding, redaction, and stale-artifact failure using synthetic shims; it is not a replacement for the drill and does not change the original `LOCAL_PAIRED_DRILL` evidence.
---

## 16. Drill re-run with remediated repository scripts (2026-11-12)

This section is appended after Sections 1-15; earlier evidence is unchanged. The six remediated scripts in `infrastructure/scripts/` were executed **directly from the repository**, with no copies, no BOM normalization, and no edits. No git mutation, cloud call, package install, or real data was used.

### 16.1 Verdict

**`LOCAL_PAIRED_DRILL_RERUN = PASS`**

| Verdict item | Result |
|---|---|
| `LOCAL_PAIRED_DRILL_RERUN` | **PASS** |
| Six remediated repository scripts under Windows PowerShell 5.1 | **PASS** (0 parser errors; executed directly) |
| Paired database + storage backup | **PASS** |
| Database + storage restore into new targets | **PASS** |
| Field-level and object-level verification | **PASS** |
| Missing-object detection | **PASS** (exit 1) |
| Stale paired-artifact rejection | **PASS** (exit 1; no `COMPLETED` manifest) |
| Simulation/partial modes | **PASS** (non-zero exits) |
| Credential scan of logs and artifacts | **PASS** (0 matches) |
| S3/R2 object-store path | **NOT TESTED** |
| Provider PITR / WAL archiving | **NOT TESTED** |
| Encryption-key escrow | **NOT TESTED / EXTERNAL REQUIREMENT** |

### 16.2 Environment and topology

| Field | Value |
|---|---|
| Date | 2026-11-12 |
| Host shell | Windows PowerShell 5.1.19041.6456 |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Drill workspace | `C:\Users\Mustafa Badshah\AppData\Local\Temp\m11_backup_drill2_59f7b24f` (deleted after evidence capture) |
| Container | `m11drill2_59f7b24f` (`c62122f9ff208afe4dfd934ffc8ea8100964f7b802edfdd080614bf6cd9c75c0`) |
| Image | `pgvector/pgvector:pg16` (`sha256:31c6867f8fd38f4b75885aeb954d43cd4c2be714659d72b0dc4ae55bdcd9e967`) |
| PostgreSQL / pgvector | 16.15 (Debian 16.15-1.pgdg12+2) / 0.8.7 |
| Port | `127.0.0.1:55435 -> 5432/tcp` |
| Source database | `m11_drill2_src` |
| Restore database | `m11_drill2_restore` (new database, empty before restore) |
| DB user | `drilluser` (synthetic; password omitted from this document) |
| Alembic head | `0010_m10_remediation_schema_alignment` |
| Source storage | `storage_src` |
| Restored storage | `storage_restored` (new, empty before restore) |
| Missing-object copy | `storage_missing` (copy of restored storage with one object deleted) |
| Damaged-archive target | `storage_missing_repo` |
| Backup directory | `backups` (plus `backups_stale` and `backups_sim` for negative checks) |
| Docker resources | One disposable container plus its anonymous volume; both removed. No named volume was created for the drill. |

### 16.3 Script inspection and invocation contract

The parameter blocks and the runbook were read before execution. The runbook now matches the script contract. All invocations used `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <repository script>` with explicit parameters:

| Script | Parameters used | Exit |
|---|---|---:|
| `backup-postgres.ps1` | `-DatabaseUrl <source-url> -BackupDir <workspace>\backups` | 0 |
| `backup-storage.ps1` | `-StoragePath <workspace>\storage_src -BackupDir <workspace>\backups -PairedDatabaseManifest <db-manifest>` | 0 |
| `backup-paired.ps1` | `-DatabaseUrl <source-url> -StoragePath <workspace>\storage_src -BackupDir <workspace>\backups` | 0 |
| `verify-backup.ps1` | `-BackupFilePath <paired dump>` | 0 |
| `restore-postgres.ps1` | `-BackupFilePath <paired dump> -TargetDatabaseUrl <restore-url> -ConfirmRestore` | 0 |
| `restore-storage.ps1` | `-ArchiveFilePath <paired zip> -TargetStoragePath <workspace>\storage_restored -ConfirmRestore` | 0 |

Exact command sequence (synthetic password shown as a placeholder):

```powershell
$repo = "E:\MM Office\Multi-Tanant-CaaS"
$ws   = "C:\Users\Mustafa Badshah\AppData\Local\Temp\m11_backup_drill2_59f7b24f"

docker run -d --name m11drill2_59f7b24f `
  -e POSTGRES_USER=drilluser `
  -e POSTGRES_PASSWORD=<synthetic-password> `
  -e POSTGRES_DB=m11_drill2_src `
  -p 127.0.0.1:55435:5432 pgvector/pgvector:pg16

$env:PATH = "$ws\bin;$env:PATH"
$env:DATABASE_URL = "postgresql+asyncpg://drilluser:<synthetic-password>@127.0.0.1:55435/m11_drill2_src"
$env:DATABASE_SYNC_URL = "postgresql://drilluser:<synthetic-password>@127.0.0.1:55435/m11_drill2_src"
$env:STORAGE_PATH = "$ws\storage_src"

# Alembic
cd "$repo\backend"
& .\.venv\Scripts\python.exe -m alembic upgrade head

# Backups (individual scripts, then paired orchestration)
& "$repo\infrastructure\scripts\backup-postgres.ps1" `
  -DatabaseUrl $env:DATABASE_SYNC_URL -BackupDir "$ws\backups"

& "$repo\infrastructure\scripts\backup-storage.ps1" `
  -StoragePath "$ws\storage_src" -BackupDir "$ws\backups" `
  -PairedDatabaseManifest "$ws\backups\mmaip_backup_20261112_191239.dump.manifest.json"

& "$repo\infrastructure\scripts\backup-paired.ps1" `
  -DatabaseUrl $env:DATABASE_SYNC_URL -StoragePath "$ws\storage_src" `
  -BackupDir "$ws\backups"

# Integrity verification of the paired dump
& "$repo\infrastructure\scripts\verify-backup.ps1" `
  -BackupFilePath "$ws\backups\mmaip_backup_20261112_191249.dump"

# Restore into new targets
& "$repo\infrastructure\scripts\restore-postgres.ps1" `
  -BackupFilePath "$ws\backups\mmaip_backup_20261112_191249.dump" `
  -TargetDatabaseUrl "postgresql://drilluser:<synthetic-password>@127.0.0.1:55435/m11_drill2_restore" `
  -ConfirmRestore

& "$repo\infrastructure\scripts\restore-storage.ps1" `
  -ArchiveFilePath "$ws\backups\mmaip_storage_backup_20261112_191250.zip" `
  -TargetStoragePath "$ws\storage_restored" -ConfirmRestore
```

Host PostgreSQL client tools are absent. Disposable `.cmd` shims in `$ws\bin` proxied the exact script arguments into the container with `docker exec` (and `docker cp` for the dump). The shims are test harness only; no repository script was copied or modified.

### 16.4 Synthetic data

The repository Alembic chain was applied to the fresh source database: `ALEMBIC_EXIT=0`, ending at `0010_m10_remediation_schema_alignment`. A script using the application models and `LocalStorageProvider` created the rows and stored the objects; the provider built the keys, not hand-written paths.

| Entity | ID | Key fields |
|---|---|---|
| Tenant | `11111111-1111-4111-8111-111111111111` | `M11 Drill Rerun Tenant`, `m11-drill-rerun-tenant`, `ORGANIZATION` |
| User | `22222222-2222-4222-8222-222222222222` | `m11.rerun.user@example.invalid`, `M11 Rerun User` |
| Role | `33333333-3333-4333-8333-333333333333` | `m11_rerun_admin` |
| Membership | `44444444-4444-4444-8444-444444444444` | tenant + user + role above, `Drill Admin` |
| Knowledge base | `55555555-5555-4555-8555-555555555555` | `M11 Rerun Knowledge Base` |
| Document alpha | `66666666-6666-4666-8666-666666666666` | `m11_rerun_alpha.txt`, 85 bytes |
| Document beta | `77777777-7777-4777-8777-777777777777` | `m11_rerun_beta.txt`, 73 bytes |
| Version alpha | `88888888-8888-4888-8888-888888888888` | version 1 for alpha |
| Version beta | `99999999-9999-4999-8999-999999999999` | version 1 for beta |

Storage keys (identical layout to the application provider):

```text
tenants/11111111-1111-4111-8111-111111111111/kbs/55555555-5555-4555-8555-555555555555/docs/66666666-6666-4666-8666-666666666666/v1/m11_rerun_alpha.txt
tenants/11111111-1111-4111-8111-111111111111/kbs/55555555-5555-4555-8555-555555555555/docs/77777777-7777-4777-8777-777777777777/v1/m11_rerun_beta.txt
```

| Object | Bytes | SHA-256 |
|---|---:|---|
| `m11_rerun_alpha.txt` | 85 | `c1cdc6edebdab4d612e98e8c404512d8965ee86c712607e0f62b392dcfafe42c` |
| `m11_rerun_beta.txt` | 73 | `d57c5de8b77409fae84de987dd9c299696b403b041d6e057b920c2d9ed40d0d8` |

Source row counts before backup: tenants 1, users 1, roles 1, memberships 1, knowledge bases 1, documents 2, document versions 2. Total stored bytes: 158.

### 16.5 Backup artifacts

Both individual-script runs and the paired orchestration completed. The paired set was used for restore.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `mmaip_backup_20261112_191239.dump` | 154507 | `D220ECD6628FDC998D58BCF6CD7BBD1DDF5C82F959B5AB1EDC19DA8E6D579839` |
| `mmaip_backup_20261112_191239.dump.manifest.json` | 297 | `EAA577B53BFECEC1EEBCD9F58FA6EC4A3E941FD9CCB7999B4E56AF27CAB6A278` |
| `mmaip_backup_20261112_191239.dump.sha256` | 101 | `D303AA9FD45C3187C4C4A968AEB28EED05D2E778A510EA930FD33BD2C3F845E3` |
| `mmaip_storage_backup_20261112_191243.zip` | 2430 | `A009A7A48AB2A45FE1F541DAB212E27ADB9F291F30C1F4EDE6CE59B3DE3E3A8E` |
| `mmaip_storage_backup_20261112_191243.zip.manifest.json` | 1609 | `8EBAE35C6E18E30A94C937936AE4AE937858D00A803E4191D14F36CCC82BAF73` |
| `mmaip_storage_backup_20261112_191243.zip.sha256` | 108 | `7AC9ABD1D1FC572D585A16E957D351B6D399E98D008469867EB939AB2203CA7A` |
| `mmaip_backup_20261112_191249.dump` | 154507 | `45D0CB94C63E91EB61DF3213BE3B678240BC5377D1CBC59BEB83A4AA73995825` |
| `mmaip_backup_20261112_191249.dump.manifest.json` | 297 | `DDB0C53DB2504E232427FAC894499C3BBE04DA5C9BDF69E58D6AA267C4B76554` |
| `mmaip_backup_20261112_191249.dump.sha256` | 101 | `0AA035E5A721371831AFAD5E940C64F3B0BCAA1FEDA32CB4212A389C4B531C69` |
| `mmaip_storage_backup_20261112_191250.zip` | 2430 | `4F09DABF59C114BB4067BC8D96CA838D5BF94046872C8A94DD621DEBAC1BEC6D` |
| `mmaip_storage_backup_20261112_191250.zip.manifest.json` | 1609 | `D5E5FDB7D13150C4FABAB24BF15B08A43DB0732E350AD4D9545899EF3E06E6B2` |
| `mmaip_storage_backup_20261112_191250.zip.sha256` | 108 | `D891A93E7D5B9392B6ED453A1374CB924138757BEC04DC4293ACA5674A4255F3` |
| `mmaip_paired_backup_20261112_191249.manifest.json` | 1153 | `49EC11014A387DBC2479675CA8DA9A34E7FBC8565C53B3F3095752B03ECD7E45` |

The individual storage backup correctly embedded the paired database manifest:

```text
paired_database.database_backup = mmaip_backup_20261112_191239.dump
paired_database.database_sha256 = D220ECD6628FDC998D58BCF6CD7BBD1DDF5C82F959B5AB1EDC19DA8E6D579839
```

The paired manifest reported `status = COMPLETED`, database size/hash matching the dump, storage size/hash matching the ZIP, `total_files = 2`, and `total_bytes = 158`. The ZIP contains 8 entries: 6 directory entries plus the 2 document files under `tenants/...`.

`verify-backup.ps1` output: checksum matched, archive TOC readable, `Found 47 table data blocks`, exit 0.

### 16.6 Restore and verification

`restore-postgres.ps1` required an existing target database (the script does not create it), so `m11_drill2_restore` was created empty first. The unchanged script verified the dump checksum/TOC, restored, and reported `[PASS] pg_restore completed cleanly`, exit 0. `restore-storage.ps1` verified the ZIP SHA-256, extracted into the new storage root, verified every manifest entry, and reported `Files Verified: 2 / 2`, `Missing Files: 0`, `Corrupted Files: 0`, exit 0.

Verification compared the source and restore databases directly and checked both stored objects through the filesystem and `LocalStorageProvider`:

| Check | Expected | Observed | Result |
|---|---|---|---|
| Alembic revision | `0010_m10_remediation_schema_alignment` | same | PASS |
| Public table set | 47 source tables | 47 restore tables, identical set | PASS |
| Every table row count | source == restore | 47/47 equal, no mismatches | PASS |
| `tenants` / `users` / `roles` | 1 / 1 / 1 | 1 / 1 / 1 | PASS |
| `tenant_memberships` / `knowledge_bases` | 1 / 1 | 1 / 1 | PASS |
| `documents` / `document_versions` | 2 / 2 | 2 / 2 | PASS |
| Key row fields | exact source == restore | tenant, user, role, membership, KB, documents, versions, Alembic all equal | PASS |
| Document fields | filename, safe name, path, size, hash, MIME, status, version | exact | PASS |
| Version fields | path, size, hash, parser, version number | exact | PASS |
| Alpha object exists in restored root | yes | yes | PASS |
| Beta object exists in restored root | yes | yes | PASS |
| Alpha object SHA-256 | `c1cdc6edebdab4d612e98e8c404512d8965ee86c712607e0f62b392dcfafe42c` | same | PASS |
| Beta object SHA-256 | `d57c5de8b77409fae84de987dd9c299696b403b041d6e057b920c2d9ed40d0d8` | same | PASS |
| DB `file_path` tenant prefix | `tenants/<tenant_id>/...` | both documents | PASS |
| `LocalStorageProvider.get()` | same bytes/hash | both documents | PASS |
| `LocalStorageProvider.exists()` / `get_size()` | true / exact size | both documents | PASS |
| Storage manifest per-file hashes | 2/2 | 2/2 | PASS |
| Paired DB size/hash | matches dump | matches | PASS |
| Paired storage size/hash | matches ZIP | matches | PASS |
| Paired `total_files` / `total_bytes` | 2 / 158 | 2 / 158 | PASS |
| Paired `status` | `COMPLETED` | `COMPLETED` | PASS |

Verifier final line: `VERIFICATION_PASS` (`VERIFY_DRILL_EXIT=0`).

Harness note: the first two proxied restore attempts completed the database (47 tables) but the proxy did not return before the harness timeout. The cause was the test shim buffering `pg_restore --verbose` stderr and writing it through PowerShell's `2>$null` redirection, which deadlocked the proxy pipe. After the shim wrote its stderr to a file, the unchanged repository script returned 0 in 4.2 seconds. This was a harness artifact, not a repository-script failure.

### 16.7 Negative checks

| Check | Method | Observed | Exit |
|---|---|---|---:|
| Deleted restored object | Copied restored storage, deleted beta, checked the storage manifest | `CHECKED=2 MISSING=1 MISMATCH=0`, `STORAGE_VERIFY_FAIL` | 1 |
| Deleted object through repository verification | Built a ZIP containing only alpha while retaining the original 2-file manifest and a valid sidecar for the damaged ZIP; ran `restore-storage.ps1 -ConfirmRestore` | `Files Verified: 1 / 2`, `Missing Files: 1`, `Corrupted Files: 0`, `Storage restoration completed with validation errors!` | 1 |
| Stale paired artifact | Added a shim that backdated the dump by 2 hours; ran `backup-paired.ps1` against a separate `backups_stale` directory | `Stale database backup artifact detected ... No paired manifest was written.` Paired-manifest count: 0 | 1 |
| Database backup simulation | Ran `backup-postgres.ps1` with `pg_dump` absent from PATH | `SIMULATION MODE: no backup was created. This run is NOT a successful backup.` Artifact count: 0 | 2 |
| Verification partial mode | Ran `verify-backup.ps1` with `pg_restore` absent from PATH | Checksum passed; `PARTIAL VERIFICATION: checksum-only result. This is NOT a full backup verification.` | 2 |
| Database restore simulation | Ran `restore-postgres.ps1 -ConfirmRestore` with `pg_restore` absent from PATH | `SIMULATION MODE: nothing was restored. This run is NOT a successful restore.` | 2 |

The stale check used unchanged `backup-paired.ps1` logic and produced no `mmaip_paired_backup_*.manifest.json` file, so no `COMPLETED` paired manifest was emitted.

### 16.8 Credential scan

All captured script stdout/stderr logs and all backup artifacts (dumps, ZIPs, manifests, checksum sidecars, damaged archive) were scanned as bytes. Counts only:

| Pattern | Files with match | Total matches |
|---|---:|---:|
| Synthetic DB password literal | 0 | 0 |
| `postgres:` | 0 | 0 |
| `postgresql://` | 0 | 0 |
| `postgres://` | 0 | 0 |

```text
SCANNED_FILES=36
SECRET_SCAN_PASS
```

`restore-postgres.ps1` printed `Target: [REDACTED]`; no URL or password appeared in that log. The scan did not include the harness scripts or shell command lines, which necessarily contained the synthetic URL.

### 16.9 Cleanup

The disposable container was removed with its anonymous volume:

```powershell
docker rm -f -v m11drill2_59f7b24f
# RM_EXIT=0
```

The container `m11drill2_59f7b24f` and anonymous volume `e0f9c124206ca9b694f56b69587033fdc1cd4bab882f1377bb950041a6b68c43` no longer exist. Pre-existing resources were preserved: containers `meta-graph-redis` and `meta-graph-neo4j` remained running; volumes `meta-graph-codebase-navigator_neo4j_data`, `meta-graph-codebase-navigator_neo4j_logs`, and `meta-graph-codebase-navigator_redis_data` remained. The workspace was deleted after evidence capture (`Test-Path` returned `False`).

### 16.10 Script defects and observations

No new functional failure was found in the six remediated scripts during this rerun. All six parsed with 0 errors under Windows PowerShell 5.1 and executed with the documented parameters.

Persistent observations, reported but not fixed:

- `restore-postgres.ps1` still treats a non-zero `pg_restore` exit code as a warning and does not fail the restore. A partially failed restore could therefore return success if the script reaches that branch.
- `restore-storage.ps1` still does not validate ZIP entry paths before `Expand-Archive`, so there is no zip-slip guard; `-Force` still overwrites the target.
- `backup-storage.ps1` still creates a missing storage directory and still emits a marker archive reported as `COMPLETED` for an empty root.
- `backup-postgres.ps1` still claims in its comment-based help that it records the current Alembic revision, but the manifest contains no Alembic field.
- `backup-paired.ps1` remains sequential and non-atomic: there is no quiesce point, snapshot, LSN, or write freeze between the database and storage halves.
- Out-of-scope observation: `infrastructure/scripts/run-live-integration-tests.ps1` reports 4 parser errors under Windows PowerShell 5.1. It is not one of the six M11 backup/restore scripts and was not modified or used.

### 16.11 Remaining gaps

- S3/R2 or other object-store backup and restore remain unimplemented; the storage scripts are local-filesystem only.
- No PITR, WAL archiving, LSN consistency, or provider continuous backup.
- No zip-slip protection in `restore-storage.ps1`, and no restricted extraction policy.
- No `restore-paired.ps1` or coordinated database-plus-storage restore/cutover procedure.
- Backup artifacts are unencrypted at rest; no retention, scheduling, monitoring, offsite copy, or key escrow was added.
- Connection URLs are still passed as process arguments to `pg_dump`/`pg_restore`; local process inspection could expose them. `PGPASSFILE` or a service file remains preferable.
- `restore-postgres.ps1` does not create the target database and does not refuse a target equal to the source.

---

**`LOCAL_PAIRED_DRILL_RERUN = PASS`**
