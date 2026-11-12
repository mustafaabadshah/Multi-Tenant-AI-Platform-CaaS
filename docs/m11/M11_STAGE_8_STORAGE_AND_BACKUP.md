# M11 Stage 8 — Storage, Backup and Data Lifecycle

| Field | Value |
|---|---|
| Milestone | M11 — Production Hardening / Staging Validation |
| Stage | 8 — Storage, Backup and Data Lifecycle |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Date | 2026-11-12 |
| Mode | READ-ONLY inspection. No code changes, cloud resources, real backups, real uploads, or git mutations. |
| Writes | This document only. |
| Executed in this stage | File inspection and static analysis only. No backup, restore, S3/MinIO, PostgreSQL, or Qdrant operation was run. |

> **Status statement**
>
> Every capability below is either inspected in the working tree and labelled, or explicitly marked **NOT RUN**. No result is inferred as a pass from an earlier milestone unless the prior evidence is named. Nothing in this document configures staging, creates a bucket, runs a backup, restores data, or uploads a document. Provider-specific backup/PITR claims are marked **TO-VERIFY** and must be confirmed against the actual staging provider.

---

## 0. Executive Summary

The storage abstraction is real: tenant-prefixed keys, local path containment, S3 key neutralisation, a fail-closed production check, and hermetic tests all exist. That is not the same as being operationally ready for real documents.

The central finding is that **staging is planned to use S3 (`render.yaml:88-101`) while every backup/restore script in the repository operates on a local filesystem path (`backup-storage.ps1`, `restore-storage.ps1`, `app/storage/recovery.py`).** There is no object-store backup, versioning, lifecycle, inventory, restore, or reconciliation procedure for the storage backend staging will actually use. The documented "paired" backup is a sequential dump-then-archive, not a consistent database-plus-object snapshot.

The second central finding is that **delete is not safe**. Document deletion removes the object first, suppresses every storage error, then deletes the database row and commits at request end (`documents.py:83-91`, `session.py:39-49`). A failed object delete silently produces an orphan; a failed database commit after a successful object delete silently produces a row pointing at missing bytes. Knowledge-base deletion removes database rows only (`knowledge.py:197-225`) and leaves every object behind. Qdrant points and persisted traces are not deleted on either path.

**Verdict: `STAGING_READY = NO` for real documents.** The platform is conditionally usable for a closed staging cohort with synthetic documents only after the P0 controls in §9 are in place and the live checks in §10 pass. Data-loss/destructive operations must not be exposed to real users before then.

### Top findings

| # | Severity | Finding |
|---|---|---|
| 1 | BLOCKER | No backup path exists for the S3 backend staging uses. All storage backup/restore scripts and the Python DR helper are local-filesystem only. |
| 2 | BLOCKER | Paired DB+object consistency is not atomic: `backup-paired.ps1` dumps PostgreSQL, then archives storage, with no write freeze, snapshot ID, LSN, or object-store inventory. Concurrent deletes can yield a DB restore that references missing objects. |
| 3 | BLOCKER | Delete ordering and error handling create silent divergence (orphan object or dangling DB row). KB deletion leaks all objects; Qdrant points and trace data are never purged. |
| 4 | HIGH | No tenant erasure / GDPR-style deletion workflow across DB, objects, object versions, Qdrant, traces, and backups. No retention schedule is implemented. |
| 5 | HIGH | Encryption-key recovery is undefined: `SECRET_ENCRYPTION_KEY` is generated into Render's environment with no escrow; the rotation command covers only `RetrievalConfig.encrypted_api_key`, not provider credentials or assistant keys. |
| 6 | HIGH | Durability is not validated live: no S3/MinIO round-trip test, no bucket probe at startup, `/ready` checks only PostgreSQL, and S3 `exists()` masks all errors as "missing". |
| 7 | HIGH | Staging can still start with `STORAGE_BACKEND=local`: the fail-closed guard rejects local only when `ENVIRONMENT == "production"`, not `staging`. |
| 8 | HIGH | Duplicate detection prevents self-healing: after an object is lost, re-uploading the same bytes returns the existing document and queues another failing job instead of restoring the object. |

---

## 1. Scope, Method, and Verdict Definitions

### 1.1 In scope

- `backend/app/storage/{base,local,s3,__init__,recovery}.py`.
- Consumers: `backend/app/api/v1/knowledge.py`, `backend/app/api/v1/documents.py`, `backend/app/services/ingestion/service.py`, `backend/app/services/ingestion/recovery.py`, `backend/app/services/ingestion/worker.py`.
- Backup/restore assets: `infrastructure/scripts/{backup-postgres,backup-storage,backup-paired,restore-postgres,restore-storage,verify-backup}.ps1`, `drill-live-postgres-backup-restore.sh`, `drill-live-qdrant-rebuild.sh`.
- `docs/runbooks/backup-and-recovery.md`.
- Compose volumes (`docker-compose.yml`, `docker-compose.m05-postgres.yml`, `docker-compose.m05-qdrant.yml`) and the staging blueprint (`render.yaml`).
- Encryption-key handling relevant to restore (`backend/app/core/crypto.py`, `backend/app/commands/rotate_encryption_keys.py`).
- Data-lifecycle surfaces: Qdrant points, persisted observability traces, conversations, document versions.

### 1.2 Out of scope / not performed

- No real S3/MinIO bucket, PostgreSQL backup, `pg_dump`, `pg_restore`, storage archive, upload, deletion, tenant purge, or cloud configuration.
- No provider PITR/backup API calls. Render-specific retention and PITR behaviour is **TO-VERIFY**.
- No test execution. Existing hermetic test evidence is cited only where a prior recorded pass exists.

### 1.3 Verdict legend

| Verdict | Meaning |
|---|---|
| **IMPLEMENTED** | The code path exists in the working tree and was inspected; there is no direct test evidence for this exact behaviour. |
| **TESTED** | Hermetic test coverage exists and a prior recorded pass is cited. Not re-executed in Stage 8. |
| **NOT RUN** | The capability requires a live provider, a real backup/restore, or a destructive drill. It was not executed in this stage. |
| **NOT IMPLEMENTED** | No code, script, or operational procedure exists for the requirement. |

---

## 2. Evidence Table

All paths are relative to `E:\MM Office\Multi-Tanant-CaaS`. Line numbers are from the inspected working tree.

| # | Evidence (file:line) | What it establishes |
|---|---|---|
| E01 | `backend/app/storage/base.py:22-63` | Storage interface (`save/get/delete/exists/get_size`) and the canonical key builder. |
| E02 | `backend/app/storage/base.py:8-19` | `sanitize_filename` strips directory components, replaces unsafe characters, removes leading dots, and collapses `..`. It does not bound length. |
| E03 | `backend/app/storage/local.py:17-35` | Local provider resolves under `STORAGE_PATH/tenants/{tenant}` and rejects paths escaping the tenant root. It strips a repeated `tenants/{tenant}/` prefix. |
| E04 | `backend/app/storage/local.py:37-49` | Local save writes a sibling `.tmp` file then atomically replaces the target. |
| E05 | `backend/app/storage/local.py:62-88` | Local delete returns `False` when absent; `exists` and `get_size` are local-only helpers. |
| E06 | `backend/app/storage/s3.py:36-43` | S3 full key is `{tenant_id}/{relative_key}` with empty, `.` and `..` segments removed. |
| E07 | `backend/app/storage/s3.py:52-75` | S3 save is a single `put_object` with `Bucket`, `Key`, `Body` only: no `ContentType`, metadata, checksum, SSE, or explicit timeout configuration. |
| E08 | `backend/app/storage/s3.py:99-118` | S3 delete calls `delete_object` and returns `True` unconditionally, including for a non-existent key. |
| E09 | `backend/app/storage/s3.py:120-142` | S3 `exists` catches every exception and returns `False`, masking auth, network, and permission failures as "missing". |
| E10 | `backend/app/storage/s3.py:144-163` | S3 `get_size` uses `head_object` and `ContentLength`. |
| E11 | `backend/app/storage/__init__.py:23-30` | Production + `STORAGE_BACKEND=local` is rejected; the check is keyed to `ENVIRONMENT == "production"` only. |
| E12 | `backend/app/storage/__init__.py:32-47` | S3/minio requires a bucket; an explicit endpoint requires static access keys. Connectivity is not checked. |
| E13 | `backend/app/storage/__init__.py:50-60` | Factory returns a cached singleton and runs configuration validation on first use. |
| E14 | `backend/app/core/config.py:61-73` | `STORAGE_BACKEND=s3`, `STORAGE_PATH`, S3 settings, `MAX_FILE_SIZE_BYTES=50 MiB`, `MAX_FILES_PER_REQUEST=10`, `MAX_EXTRACTED_TEXT_SIZE_BYTES=20 MiB`. |
| E15 | `backend/app/services/ingestion/service.py:49-90` | Upload order: size check, SHA-256, duplicate check, sanitize, build key, then `storage.save` before any DB write. |
| E16 | `backend/app/services/ingestion/service.py:58-76` | Duplicate hash in the same KB returns the existing document and creates a new `QUEUED` job; no object is written. |
| E17 | `backend/app/services/ingestion/service.py:96-143` | Document, version, job, and initial event are inserted and committed after the object is saved. |
| E18 | `backend/app/services/ingestion/service.py:90-108` | Verified MIME is detected after save; the client-supplied MIME is stored only in `metadata_json["original_mime"]`. |
| E19 | `backend/app/services/ingestion/service.py:183-198` | Ingestion reads the object back with `storage.get`; a missing object raises into the generic retry/failure path. |
| E20 | `backend/app/services/ingestion/service.py:421-451` | Failures increment `retry_count`, requeue up to `max_retries`, then mark job/document `FAILED`. |
| E21 | `backend/app/services/ingestion/service.py:456-535` | Reindex is DB-source-driven: it reads `DocumentChunk` rows, re-embeds, and upserts Qdrant points; it does not read original objects. |
| E22 | `backend/app/api/v1/knowledge.py:236-303` | Bulk upload reads each `UploadFile` fully, commits each document independently, and aborts the request on the first `ValueError`. |
| E23 | `backend/app/api/v1/knowledge.py:259-263` | Per-request file count is capped at `MAX_FILES_PER_REQUEST`; file size is not checked before `read()`. |
| E24 | `backend/app/api/v1/knowledge.py:197-225` | Knowledge-base delete removes DB rows only; no storage, Qdrant, or trace cleanup. |
| E25 | `backend/app/api/v1/documents.py:67-100` | Document delete calls `storage.delete` first, swallows every exception, then deletes the DB row. |
| E26 | `backend/app/database/session.py:39-49` | The request-scoped session commits after the handler returns, so the DB delete is committed after the object is already gone. |
| E27 | `backend/app/services/ingestion/recovery.py:27-91` | Startup recovery only converts `PROCESSING` ingestion/embedding jobs to `FAILED/INTERRUPTED`; it does not reconcile storage or recover `QUEUED` jobs. |
| E28 | `backend/app/services/ingestion/worker.py:18-62` | The optional worker polls `QUEUED` jobs with a plain `SELECT ... LIMIT 1`, with no storage reconciliation and no atomic claim. |
| E29 | `backend/app/storage/recovery.py:82-150` | Python storage backup hashes every local file into a ZIP plus manifest with an optional paired-DB reference. |
| E30 | `backend/app/storage/recovery.py:153-226` | Python storage restore verifies the archive checksum, blocks zip-slip, and verifies per-file SHA-256. |
| E31 | `backend/app/storage/recovery.py:229-314` | Reconciliation compares `Document.file_path` against a local filesystem path, detects missing/corrupt/orphan files, and does not use a storage provider. |
| E32 | `backend/app/storage/recovery.py:64-70` | `is_consistent` ignores `orphan_files`; a report with untracked objects can still be "consistent". |
| E33 | `backend/app/storage/recovery.py:239-260` | Reconciliation builds `STORAGE_PATH/tenants/{tenant}` directly, so it cannot run against S3. |
| E34 | `backend/tests/test_m05_file_recovery.py:70-388` | Hermetic local-filesystem paired backup/restore, reconciliation, tenant isolation, and zip-slip tests. |
| E35 | `backend/tests/test_remediation_stage3_storage.py:21-131` | Storage configuration matrix, tenant key separation, traversal neutralisation, filename sanitisation, and S3 error non-leakage tests. |
| E36 | `backend/tests/test_s3_storage.py:35-89` | S3 save/get/exists/get_size/delete are verified only with a mocked `aioboto3`. |
| E37 | `docs/m10/M10_GIT_STAGE_3_SECURITY_REVIEW.md:43-45` | Prior recorded pass: a 44-test combined security suite (including storage/S3 tests) and 3 M05 recovery tests passed. Not re-executed in Stage 8. |
| E38 | `infrastructure/scripts/backup-postgres.ps1:41-93` | Timestamped `pg_dump -Fc`, SHA-256 file, and manifest. Manifest has no Alembic revision. |
| E39 | `infrastructure/scripts/backup-postgres.ps1:54-59` | If `pg_dump` is absent, the script prints "Simulation Mode" and exits 0. |
| E40 | `infrastructure/scripts/backup-storage.ps1:59-128` | Local directory inventory, `Compress-Archive`, archive checksum, optional DB manifest reference. |
| E41 | `infrastructure/scripts/backup-paired.ps1:46-89` | DB dump first, storage archive second, then a coordination manifest. No quiesce, snapshot, LSN, or object inventory. |
| E42 | `infrastructure/scripts/restore-postgres.ps1:52-79` | Verifies checksum, skips restore when `pg_restore` is absent (exit 0), and treats a non-zero `pg_restore` exit as a warning. |
| E43 | `infrastructure/scripts/restore-storage.ps1:53-114` | Verifies archive checksum, uses `Expand-Archive` directly, then checks manifest hashes. No explicit zip-slip validation. |
| E44 | `infrastructure/scripts/verify-backup.ps1:34-68` | Verifies SHA-256 and `pg_restore --list` TOC; exits 0 if `pg_restore` is absent. |
| E45 | `infrastructure/scripts/drill-live-postgres-backup-restore.sh:65-136` | Live drill: seed encrypted BYOK, `pg_dump`, isolated disposable restore DB, schema/record/BYOK/source-untouched markers. NOT RUN in Stage 8. |
| E46 | `infrastructure/scripts/drill-live-qdrant-rebuild.sh:82-123` | Live drill: application-driven Qdrant rebuild from PostgreSQL chunks with tenant-filter and idempotency markers. NOT RUN in Stage 8. |
| E47 | `docker-compose.yml:16,54,101,112,136-139` | Named volumes: `postgres_data`, shared `backend_storage` for API+worker, `qdrant_data`, `redis_data`. Local storage is a dev-only mount. |
| E48 | `render.yaml:15,19-20,51-54,88-101,107-111` | Staging runs two uvicorn workers, `ENVIRONMENT=staging`, Render-generated `SECRET_ENCRYPTION_KEY`, S3 env vars, PostgreSQL starter plan. No worker service and no backup/cron service. |
| E49 | `docs/runbooks/backup-and-recovery.md:3,10-15,22-25,46-51` | Runbook claims "IMPLEMENTED AND AUDITED", but its PowerShell parameter names and artifact names do not match the scripts. |
| E50 | `backend/app/core/crypto.py:22-40` | Active key derives from `SECRET_ENCRYPTION_KEY` or falls back to `SECRET_KEY`; previous keys are comma-separated. |
| E51 | `backend/app/commands/rotate_encryption_keys.py:57-59` | Rotation scans only `RetrievalConfig.encrypted_api_key`. |
| E52 | `backend/app/models/provider.py:34`, `backend/app/models/knowledge.py:298`, `backend/app/models/assistant.py:37` | Three separate encrypted-key columns exist: provider credentials, retrieval config, assistant BYOK. |
| E53 | `backend/app/observability/tracer.py:149-237` | Traces are held in per-tenant ring buffers and persisted to `backend/data/observability_traces.json`; no purge API exists. |
| E54 | `backend/app/vectorstores/qdrant_store.py:239-262` | `delete_document` exists but is unused; it swallows errors and returns `1` regardless of outcome. |
| E55 | `backend/app/vectorstores/pgvector_store.py:237-244` | pgvector `delete_document` exists but is unused; DB cascade is the only deletion path. |
| E56 | `backend/app/services/ingestion/service.py:367,523` | Qdrant payload includes chunk `content`, so DB row deletion does not remove text from Qdrant. |
| E57 | `backend/app/retrieval/authorization.py:79-109` | Retrieval discards candidates whose document is absent or unauthorized in the DB; dangling Qdrant points are not served. |
| E58 | `backend/app/main.py:75-97` | `/health` is liveness only; `/ready` checks PostgreSQL only, not object storage. |
| E59 | `.gitignore:50-54` | `data/` is ignored; a top-level `backups/` directory is not. |
| E60 | `.env.production.example:54-74` | Production example uses S3, 50 MiB file limit, 10 files per request; no backup/retention settings exist. |

---

## 3. Storage Implementation Assessment

### 3.1 Abstraction and factory

`StorageProvider` exposes five asynchronous operations only: `save`, `get`, `delete`, `exists`, and `get_size` (`base.py:22-51`). There is no streaming API, multipart upload, presigned URL, list/iterate, copy, metadata update, or batch delete. This shape is adequate for the current ingestion flow, which reads whole files into memory, but it is not an object-lifecycle interface.

`get_storage_provider()` validates configuration and returns a cached singleton (`__init__.py:50-60`). Validation is meaningful:

- `ENVIRONMENT=production` + `STORAGE_BACKEND=local` → `RuntimeError` (`__init__.py:23-30`).
- S3/minio without `S3_BUCKET_NAME` → `RuntimeError` (`__init__.py:35-39`).
- S3 with an explicit endpoint but no static access/secret keys → `RuntimeError` (`__init__.py:41-47`).
- Any other backend → `ValueError` (`__init__.py:32-33`).

Two limits matter for staging:

1. **The guard is keyed to `production` only.** `render.yaml:19-20` sets `ENVIRONMENT=staging`; a staging deployment with `STORAGE_BACKEND=local` therefore passes validation. This is the same class of defect as the M10 STOR-1 finding, narrowed to the staging environment.
2. **Validation checks settings, not connectivity.** A wrong bucket name, expired credential, wrong region, or bucket policy denial passes startup and fails only on the first upload. `/ready` checks PostgreSQL only (`main.py:84-97`), and the Render health check points at `/health`, which is a static liveness response (`main.py:75-82`, `render.yaml:16`).

**Verdict: IMPLEMENTED**, with a staging configuration gap and no live connectivity check.

### 3.2 Tenant prefixes, filename safety, and key layout

**Local provider.** The tenant root is `{STORAGE_PATH}/tenants/{tenant_id}`. The provider strips a repeated `tenants/{tenant_id}/` prefix from the relative key, resolves the result, and rejects any path that is not relative to the tenant root (`local.py:17-35`). `resolve()` follows symlinks; the `relative_to` check then rejects an escape. Uploads are regular files, so a symlink can only be introduced by an external process, not by the upload path.

**S3 provider.** `_get_full_key` removes empty, `.` and `..` segments and prefixes the tenant: `{tenant_id}/{relative_key}` (`s3.py:36-43`). A leading-slash traversal payload cannot escape the tenant prefix; this is covered by E35.

**Key builder.** `build_storage_key` returns:

```text
tenants/{tenant_id}/kbs/{knowledge_base_id}/docs/{document_id}/v{version}/{safe_name}
```

(`base.py:53-63`). This already contains `tenants/{tenant_id}/`.

**Layout inconsistency (MEDIUM).** For local storage the effective path is:

```text
{STORAGE_PATH}/tenants/{tenant_id}/kbs/{kb}/docs/{doc}/v1/{file}
```

For S3 it is:

```text
{bucket}/{tenant_id}/tenants/{tenant_id}/kbs/{kb}/docs/{doc}/v1/{file}
```

The tenant prefix is applied twice. This is not a cross-tenant escape, but it is a real migration, reconciliation, purge, and restore hazard: tooling that assumes the local `tenants/{tenant}/` layout will not find S3 objects, and a future removal of one prefix will strand existing keys. The return value is also inconsistent: local `save` returns the input relative key (`local.py:49`), while S3 `save` returns the full key including the tenant prefix (`s3.py:75`), despite the abstract contract describing a "normalized storage key" (`base.py:26-31`). Current ingestion ignores the return value, so the inconsistency is latent.

**Filename handling.** `sanitize_filename` strips directory components, replaces non-alphanumeric characters (except `.`, `_`, `-`), removes leading dots, collapses consecutive dots, and generates a fallback name if empty (`base.py:8-19`). This is sound for traversal and unsafe-character suppression. It does **not** truncate length. `Document.filename`, `Document.safe_filename`, and `Document.file_path` are `String(255)`, `String(255)`, and `String(1024)` (`models/knowledge.py:98-100`). A very long multipart filename can therefore pass `sanitize_filename`, be written successfully to the object store, and then fail the PostgreSQL insert with a length error. SQLite-based tests would not catch this. This is a staging-specific risk because staging uses PostgreSQL.

**Tenant identity trust.** The provider accepts any `tenant_id` string; isolation depends on callers passing the authenticated tenant. Every production call site inspected passes `ctx.tenant.id` or `self.tenant_id` derived from it (`knowledge.py:274`, `documents.py:84-86`, `service.py:90`). `IngestionService` coerces its tenant to `uuid.UUID` (`service.py:28-33`). The storage layer is therefore defence-in-depth, not an independent authorization boundary. This matches the M10 design note.

**Verdict: IMPLEMENTED; TESTED (hermetic)** for traversal, filename sanitisation, and tenant key separation (E35, E36, E37). **Gap:** double prefix, return inconsistency, unbounded filename/key length.

### 3.3 Upload path, limits, and partial-upload behaviour

The upload sequence for the API path is:

1. Verify KB belongs to the active tenant (`knowledge.py:243-251`).
2. Reject empty request and more than `MAX_FILES_PER_REQUEST` files (`knowledge.py:253-263`).
3. For each file: take the original filename, read the **entire** body into memory, then call `IngestionService.upload_document` (`knowledge.py:269-279`).
4. In the service: reject `len(content) > MAX_FILE_SIZE_BYTES` (`service.py:50-55`).
5. SHA-256 the bytes (`service.py:57-58`).
6. Check for an existing document with the same hash in the same KB (`service.py:60-76`).
7. Sanitise the filename, generate a document UUID, build the storage key (`service.py:78-87`).
8. `storage.save` writes the object (`service.py:89-90`).
9. Detect the verified MIME type (`service.py:92-93`).
10. Insert document, version, job, and initial event; commit (`service.py:95-143`).

**Limits actually enforced.**

| Limit | Value | Enforcement point | Gap |
|---|---|---|---|
| File size | 50 MiB (`config.py:68`) | After the full body is read into memory (`service.py:50-55`) | No pre-read check; Starlette spools to disk but `read()` loads all bytes. Concurrent uploads can exhaust memory/disk before rejection. |
| Files per request | 10 (`config.py:69`) | Before the loop (`knowledge.py:259-263`) | A 400 aborts the response but earlier files in the loop are already committed. |
| URL-ingested content | 10 MiB (`url_ingestion.py:42,122-124`) | After `httpx` has downloaded the full response into memory | No streaming limit. |
| Extracted text | 20 MiB (`config.py:70`) | Character slice at `service.py:298` | Slice is by characters, not bytes; multi-byte text can exceed the nominal byte budget. |
| Per-KB max file size | `IngestionConfig.max_file_size_mb` (`models/knowledge.py:81`) | Stored and updated, never read by ingestion | The per-KB control is cosmetic; only the global 50 MiB limit applies. |

**Partial upload behaviour.**

- Local writes use a sibling `.tmp` then `replace` (`local.py:41-48`), so a crash mid-write does not expose a partial target under the final key. A leftover `.tmp` is possible.
- S3 uses a single `put_object` (`s3.py:70-74`). A single PUT is atomic at the object level; there is no multipart upload to leave incomplete parts.
- The dangerous boundary is **after** a successful object write and **before** the DB commit. If `flush`/`commit` fails, the object remains with no DB row. There is no compensating delete.
- The bulk loop commits per file (`service.py:143`). A failure on file 3 of 5 returns 400/500 after files 1-2 are durable. The client sees an error but partial success exists; retrying re-detects files 1-2 as duplicates (no duplicate objects) and creates new jobs for them.
- The audit event is written after the service commit (`knowledge.py:284-290`). If the audit insert/commit fails, the upload remains durable but the request returns an error.

**Content type and metadata.**

- The client-supplied `content_type` is stored only inside `metadata_json["original_mime"]` (`service.py:108`).
- The verified MIME from the parser registry is stored in `Document.mime_type` (`service.py:93,104`).
- No content type, content disposition, original filename, tenant ID, document ID, or checksum is written to S3 object metadata (`s3.py:70-74`). All mapping lives in the database and the key path.
- This is acceptable while the DB is authoritative, but it means an object restored without its DB row cannot be identified from object metadata alone; only the key path is available.

**Verdict: IMPLEMENTED**; **partial-upload/atomicity gap**; no live provider test.

### 3.4 Read, download, `exists`, and `get_size`

- `storage.get` is used in exactly one production path: ingestion loads the original object before parsing (`service.py:185`). There is no user-facing endpoint that serves original bytes. The document content endpoint returns `DocumentVersion.extracted_text` from PostgreSQL (`documents.py:164-189`), not the object.
- `exists` and `get_size` are defined but not called by any request path in `backend/app`; only tests exercise them. This means there is no pre-flight "object exists" check before a reprocess, and no cheap integrity probe in the API.
- S3 `get` raises the SDK's `ClientError`/`NoSuchKey`; local `get` raises `FileNotFoundError` (`local.py:55-58`). Ingestion treats both through the generic `except Exception` retry path (`service.py:421-451`), so the job eventually fails with an error category rather than a typed "object missing" state.

**Verdict: IMPLEMENTED; no raw-file download capability** (a product gap, and a reason the original bytes are only needed for reprocessing/DR).

### 3.5 Delete path and ordering

The document delete endpoint does the following, in order (`documents.py:67-100`):

1. Load the document with tenant scoping (`:74-81`).
2. `await storage.delete(str(ctx.tenant.id), doc.file_path)` (`:84-86`).
3. `except Exception: pass` (`:87-88`). The failure is not logged, audited, or returned.
4. `await repo.delete(document_id)` (`:91`), which cascades to versions, chunks, embeddings rows, jobs, and events.
5. Write an audit event (`:93-100`).
6. The request-scoped session commits after the handler returns (`session.py:44`).

This ordering is the wrong way round for a distributed store. The object is removed before the database transaction is known to succeed. Two failure shapes follow:

- **Object delete fails:** the DB rows are still deleted and the request returns 204. The object is orphaned silently. S3 `delete` reports success even for a missing key (`s3.py:117-118`), and the caller ignores the boolean anyway.
- **Object delete succeeds; DB commit fails:** the document row survives and points at missing bytes. The content endpoint still works from `extracted_text`, but reprocess fails, and the next delete attempt sees no object.

Additional gaps:

- Only `doc.file_path` is deleted. `DocumentVersion.file_path` is not iterated (`models/knowledge.py:157`). Today only v1 is created (`service.py:113-120`), so the paths are identical; as soon as real versioning exists, older version objects leak.
- **Knowledge-base deletion does not touch storage at all** (`knowledge.py:197-225`). The ORM cascade removes documents/versions/chunks/embeddings, but every S3/local object under the KB remains. This is the largest orphan generator in the product.
- **Qdrant points are not deleted.** `QdrantVectorStore.delete_document` exists but has no call sites (`qdrant_store.py:239-262`; E54). `PgVectorStore.delete_document` is also unused (`pgvector_store.py:237-244`) because the DB cascade handles pgvector rows. Qdrant payloads contain chunk `content` (`service.py:367,523`), so deleted text remains queryable at the vector-store layer, even though retrieval authorization filters it out at the application layer (`authorization.py:79-109`). This is a data-retention issue, not an immediate cross-tenant read issue.
- **Persisted traces are not deleted.** They live in `backend/data/observability_traces.json` with `tenant_id` fields and no purge path (`tracer.py:149-237`).

**Verdict: IMPLEMENTED but UNSAFE ordering; no atomicity; no cleanup for KB/tenant/vector/trace.**

### 3.6 Error handling, timeouts, and observability

- S3 exceptions are allowed to propagate raw. There is no wrapping into a storage-specific exception, no retry policy, and no classification of "not found" vs "access denied" vs "network". The API converts unhandled storage errors into a generic 500.
- `exists()` catches `Exception` and returns `False` (`s3.py:141-142`). A credential or network outage therefore reads as "object missing" to any future caller. No production caller currently uses it, but it is a trap for reconciliation tooling.
- `delete()` returns `True` unconditionally (`s3.py:117-118`). It cannot be used to prove deletion.
- No explicit `botocore`/`aioboto3` timeout, retry, or connection-pool configuration is passed. A new `aioboto3.Session()` and client are created per operation (`s3.py:62-74`, `:87-97`, etc.). Provider defaults apply; those defaults were not measured in this stage. A slow or hung object store can hold an upload request open for the SDK default duration.
- No storage metrics, latency, error counters, or structured audit of storage operations exist. The delete endpoint's bare `except` is the clearest example (`documents.py:87-88`).
- `/health` does not touch storage; `/ready` does not touch storage (`main.py:75-97`). Render's health check therefore cannot detect a bucket outage. A deployment can be "healthy" while every upload fails.

**Verdict: IMPLEMENTED with weak error semantics; no explicit timeouts; no storage health signal.**

### 3.7 Orphan handling and reconciliation

`app/storage/recovery.py` is a useful local-DR utility, not an operational control:

- `create_storage_backup` walks a local directory, hashes every file into a ZIP, and writes a manifest with an optional paired-DB reference (`recovery.py:82-150`).
- `restore_storage_backup` verifies the archive checksum, blocks zip-slip, and verifies per-file SHA-256 (`recovery.py:153-226`).
- `reconcile_database_and_storage` selects `Document` rows for one tenant and compares `Document.file_path` to `STORAGE_PATH/tenants/{tenant}` (`recovery.py:229-314`). It detects missing files, size mismatch, hash mismatch, and orphan files.
- It is **local-filesystem-only**: `base_storage = Path(storage_path)` and `tenant_root / clean_key` (`recovery.py:239-260`). It cannot reconcile an S3 bucket.
- It is **not wired** to any API, CLI command, scheduler, startup hook, or worker. A grep for its symbols finds only its definition and tests. It never deletes or quarantines an orphan.
- `is_consistent` excludes `orphan_files` (`recovery.py:64-70`). A restore can be declared consistent while untracked objects remain.
- It checks only `Document.file_path`, not `DocumentVersion.file_path`, and it skips documents whose status is `DELETED` (`recovery.py:253`). No production path currently sets `DELETED` for documents, but the assumption is fragile.
- For a missing file it records the expected key and document metadata but has no repair action.

**Verdict: IMPLEMENTED (local only); NOT operational; S3 reconciliation NOT IMPLEMENTED.**

### 3.8 Background recovery and document state after a restore

Startup recovery is narrowly scoped (`recovery.py:27-91`):

- `IngestionJob.status == "PROCESSING"` → `FAILED`, stage `INTERRUPTED`, error category `PROCESS_RESTART`, document `FAILED` if it was `PROCESSING`.
- `EmbeddingJob.status == "PROCESSING"` → `FAILED`, stage `INTERRUPTED`.
- `QUEUED` jobs are not recovered, re-dispatched, or failed. There is no lease, heartbeat, or claim.
- The recovery query is global, not tenant-scoped, which is appropriate for a system-level startup sweep but must be treated as privileged.

Staging topology matters here. `render.yaml:15` starts two uvicorn workers and defines no worker service. Ingestion is dispatched with `asyncio.create_task` in the API process (`knowledge.py:282`, `documents.py:150,280`). If the process dies before `execute_job` commits `PROCESSING`, the job remains `QUEUED` and no process picks it up; recovery ignores it. If it dies after `PROCESSING`, recovery marks it `FAILED` but does not resume it. The optional compose worker (`docker-compose.yml:82-101`) polls `QUEUED`, but it is not part of the staging blueprint and is not safe to run concurrently (M11 Stage 5 documents the duplicate-execution race).

After a database restore, this means document/job status is **not self-normalizing**: some rows will be `PROCESSING` until an API restart, some `QUEUED` forever, and some `COMPLETED` while their object is missing. §5.6 defines the required post-restore state procedure.

**Verdict: IMPLEMENTED (partial); NOT sufficient for restore.**

---

## 4. Backup and Restore Assets — What Exists (All NOT RUN)

Every asset in this section is marked **NOT RUN**. The descriptions are from source inspection, not execution.

### 4.1 Inventory

| Asset | Mechanism | Covers | Does not cover | Verdict |
|---|---|---|---|---|
| `backup-postgres.ps1` | `pg_dump -Fc` of one database; SHA-256 file; JSON manifest | Full relational DB, including pgvector rows, audit, encrypted BYOK ciphertext | PITR/WAL, per-tenant export, retention, encryption, offsite copy, Alembic revision in manifest | **NOT RUN** |
| `backup-storage.ps1` | Walks a local directory; `Compress-Archive`; per-file SHA-256; manifest | Local `STORAGE_PATH` files | S3/MinIO buckets, object versions, delete markers, bucket policy, replication | **NOT RUN** |
| `backup-paired.ps1` | Runs DB backup, then storage backup, then writes a coordination manifest | A human-readable link between one dump and one local archive | Atomic consistency, quiesce, LSN/snapshot ID, object inventory, S3 | **NOT RUN** |
| `restore-postgres.ps1` | Checksum + `pg_restore --clean --if-exists` | Restoring a custom-format dump into a target DB | Safe target verification, transactional restore, rollback, app-level verification | **NOT RUN** |
| `restore-storage.ps1` | Checksum + `Expand-Archive` + manifest hash check | Restoring a local archive | S3 restore, version restoration, zip-slip validation, deletion of extra files | **NOT RUN** |
| `verify-backup.ps1` | SHA-256 + `pg_restore --list` TOC | Detecting corrupt/truncated DB dumps | Actual restore, row counts, BYOK decryption, storage verification | **NOT RUN** |
| `app/storage/recovery.py` | Python library for local ZIP backup/restore and local reconciliation | Local storage snapshots and local DB↔file reconciliation | S3, scheduling, CLI, deletion, operational reporting | **NOT RUN** (but **TESTED** hermetically, E34) |
| `drill-live-postgres-backup-restore.sh` | Containerized dump → isolated disposable DB → schema/record/BYOK/source checks | Real PostgreSQL restore viability, including BYOK decryption | Storage/object restore, PITR, provider-managed backups, S3 | **NOT RUN** |
| `drill-live-qdrant-rebuild.sh` | Rebuild Qdrant from PostgreSQL chunks via the application service | Qdrant rebuild, tenant filter, idempotency | Object storage, DB backup, key escrow | **NOT RUN** |

### 4.2 PostgreSQL backup (`backup-postgres.ps1`)

What it does:

- Resolves the connection string from `-DatabaseUrl`, `DATABASE_SYNC_URL`, or `DATABASE_URL` (`:21-34`).
- Creates a timestamped `mmaip_backup_{yyyyMMdd_HHmmss}.dump` (`:41-45`).
- Runs `pg_dump --dbname=<url> --format=c --file=<dump> --no-password --verbose` (`:64`).
- Writes `<dump>.sha256` and a JSON manifest (`:71-88`).
- Manifest fields: timestamp, backup file, size, SHA-256, format, status (`:79-86`).

What it does not do:

- **No Alembic revision.** The docstring claims it "captures the current Alembic revision" (`:6`), but no `alembic_version` query or manifest field exists. Restore verification cannot bind a dump to a schema version from the artifact alone.
- **No PITR / WAL.** This is a logical dump, not a continuous archive. The best possible RPO is the dump interval.
- **No scheduling, retention, encryption, or offsite copy.** The script is manual and writes plaintext artifacts to `./backups`.
- **No per-tenant scoping.** The dump contains every tenant. A per-tenant restore requires extracting from a full restore or writing a filtered export; the script offers neither.
- **No restore verification.** `verify-backup.ps1` checks the archive TOC, not the data.
- **Simulation success.** If `pg_dump` is not on `PATH`, the script prints "Simulation Mode / Script syntax validated" and exits 0 (`:54-59`). An automation wrapper would treat that as a successful backup.

Authentication depends on the environment (`--no-password` plus `.pgpass`, trust, or a service file). That prerequisite is not documented in the script or runbook.

### 4.3 Local storage backup (`backup-storage.ps1`)

What it does:

- Resolves `-StoragePath` (default `./data/storage` or `$env:STORAGE_PATH`) and `-BackupDir` (`:23-33`).
- Enumerates every file recursively, computes SHA-256 per file, and records relative path, size, and hash (`:59-79`).
- Archives with `Compress-Archive` (`:82-92`).
- Computes the archive SHA-256 and writes a manifest, optionally embedding a paired DB manifest's file name and hash (`:94-128`).

What it does not do:

- **It backs up the wrong storage backend for staging.** Staging is configured for S3 (`render.yaml:88-101`); there is no local `STORAGE_PATH` with tenant data on Render. This script would archive an empty or irrelevant directory.
- **No object versions or delete markers.** Even if pointed at a mounted bucket, a ZIP of current files cannot restore noncurrent versions or undo a delete.
- **No encryption or offsite copy.**
- **No retention or pruning.**
- **Race with live uploads.** `save` writes a `.tmp` sibling then replaces (`local.py:43-46`). The archive walk can include a `.tmp` file, or hash a file while it is being replaced. There is no snapshot, freeze, or filesystem quiesce.
- **Empty-storage marker bug.** When no files exist, it compresses a temporary `empty_marker_<guid>.txt` into the archive (`:86-92`) but records zero files in the manifest. `restore-storage.ps1` expands the archive without skipping the marker, so a restore of an empty backup creates an orphan marker file in the storage root. The Python implementation uses `.mmaip_empty_backup` and explicitly skips it (`recovery.py:126-127,181-182`); the PowerShell path does not.
- **Size limits.** `Compress-Archive` on Windows PowerShell 5.1 has practical archive-size limits; a multi-gigabyte tenant store has not been tested. Mark **TO-VERIFY** if this script is retained.

### 4.4 Paired backup (`backup-paired.ps1`)

The sequence is:

1. Run `backup-postgres.ps1` (`:46-49`).
2. Find the newest `mmaip_backup_*.manifest.json` by `LastWriteTime` (`:51-54`).
3. Run `backup-storage.ps1` with that DB manifest (`:56-59`).
4. Find the newest storage manifest and write `mmaip_paired_backup_{timestamp}.manifest.json` referencing both (`:61-89`).

**There is no consistency mechanism.**

- No write freeze, maintenance window, database lock, `pg_backup_start/stop`, LSN, snapshot ID, or object-store inventory.
- The DB dump and the file archive are taken at different times. The pair is "paired" only by a manifest reference.
- **Concurrent uploads** between the dump and the archive produce objects with no DB row in the restored dump: an orphan object. This is usually the less harmful direction, because the object is unreferenced.
- **Concurrent deletes** are the harmful direction. A document present at dump time can have its object deleted before the archive runs. The restored database then references a missing object. Deletes are not blocked by either script.
- **No freeze means the pair is not reproducible.** Two runs with the same inputs can produce different consistency outcomes.
- **Stale pairing is possible.** If `backup-postgres.ps1` enters simulation mode and creates no new manifest, `backup-paired.ps1` still selects the newest **old** manifest and pairs it with a fresh storage archive. The resulting paired manifest claims a relationship that does not exist.
- **No S3 inventory.** For an S3 backend there is no list of keys, versions, sizes, ETags/checksums, or delete markers to compare with the DB dump.
- **No verification.** The script does not run `verify-backup.ps1` or a restore; it checks only that manifest files exist and parse.

**Verdict: paired DB+object consistency is NOT ADDRESSED.** The scripts produce adjacent artifacts, not a consistent recovery point.

### 4.5 Restore and verification scripts

**`restore-postgres.ps1`.**

- Requires `-ConfirmRestore` (`:36-39`), which prevents accidental invocation but does not verify that the target is disposable. A valid staging URL can be passed.
- Verifies the checksum via `verify-backup.ps1` (`:52-61`).
- If `pg_restore` is absent, prints "Simulation Mode" and exits 0 (`:63-69`).
- Runs `pg_restore --clean --if-exists --no-owner --no-privileges --dbname=<target> --verbose` (`:73`).
- **Treats a non-zero `pg_restore` exit as a warning and does not fail** (`:75-79`). A data error, permission failure, or partial restore can therefore end with a success-looking script. There is no `--single-transaction`, no post-restore row-count check, no `alembic_version` check, and no application smoke test.

**`restore-storage.ps1`.**

- Verifies the archive SHA-256 if a `.sha256` file exists (`:53-66`).
- Extracts with `Expand-Archive` (`:77`). There is **no explicit zip-slip validation**; the script relies on `Expand-Archive` behaviour, unlike the Python helper which explicitly rejects `..` and absolute members (`recovery.py:179-187`). A malicious or corrupted archive is not validated by this script before extraction.
- Verifies every manifest file's SHA-256 after extraction (`:79-113`) and exits 1 on corruption/missing files.
- **Restores in place, without deleting extra files.** Objects created after the backup remain. A database restored to the backup point will see them as orphans.
- **Local only.** There is no S3 restore path, no version restore, no delete-marker handling, and no restore to a disposable prefix.

**`verify-backup.ps1`.**

- Computes SHA-256 and compares it with the sidecar file if present (`:34-50`).
- Runs `pg_restore --list` and counts `TABLE DATA` entries (`:52-68`).
- If `pg_restore` is absent, exits 0 after the checksum (`:53-57`). A dump can pass "verification" without its TOC being readable.
- A missing `.sha256` sidecar is only a warning (`:48-50`); the script can exit 0 without ever comparing a hash. It does not restore, query, decrypt, or count rows. It is a corruption check, not a recovery test.

**`restore_storage_backup` (Python).**

- Verifies the archive checksum only if `<archive>.sha256` exists; if it is missing, `archive_verified=False` but the restore still proceeds (`recovery.py:166-176`).
- Blocks zip-slip explicitly (`:179-187`).
- Verifies per-file size and hash from the manifest (`:196-215`).
- Returns `SUCCESS` only when no corrupted or missing files were found (`:217-226`). If the manifest or checksum sidecar is absent, the verification loop is skipped and the function can still return `SUCCESS` with `archive_verified=False` and zero verified files. Callers must treat a missing manifest/checksum as an unverified restore, not a pass.
- Still local-only.

### 4.6 Python DR utility (`app/storage/recovery.py`)

This is the strongest DR code in the repository, and it is not operationalized:

- Backup and restore are synchronous filesystem functions; they are not exposed through an API, CLI, worker, or scheduled task.
- The manifest's `paired_database` field is an opaque dictionary (`recovery.py:39,145`). It records a reference, not a consistency proof or object inventory.
- Reconciliation is local-only and compares only `Document.file_path` (see §3.7).
- Nothing deletes or quarantines orphan files; the report is informational.
- No encryption, retention, offsite transfer, or access control.
- Tests cover the local happy path, missing/corrupt/orphan detection, tenant isolation, and zip-slip (E34). They do not cover S3, concurrent writes/deletes, partial restores, or PostgreSQL length constraints.

### 4.7 Live drills

**`drill-live-postgres-backup-restore.sh`** is the closest thing to a real recovery test:

- Requires a healthy PostgreSQL container (`:57-61`).
- Seeds an encrypted BYOK credential through the application crypto (`:65-76`).
- Runs `pg_dump -Fc` inside the container (`:78-80`).
- Computes SHA-256 (`:82-86`).
- Creates the fixed disposable database `m05_restore_drill_disposable` with explicit name guards (`:88-95`).
- Restores into it (`:97-101`).
- Verifies schema, records, live BYOK decryption/plaintext match, and that the source DB is untouched (`:103-124`).
- Drops the disposable DB and dump (`:126-132`).

It does **not** test object storage, PITR, provider-managed backups, key escrow outside the process, or a production-sized dataset. It is Linux/Docker only.

**`drill-live-qdrant-rebuild.sh`** verifies the PostgreSQL-authoritative rebuild pattern:

- Starts/uses PostgreSQL and Qdrant (`:50-80`).
- Runs `app.commands.drill_qdrant_rebuild` (`:82-95`).
- Requires markers for source persistence, collection loss simulation, reindex invocation/completion, tenant filtering, and idempotency (`:98-119`).

It does **not** test storage backup/restore or DB restore.

### 4.8 Compose volumes and staging topology

`docker-compose.yml` defines:

- `postgres_data:/var/lib/postgresql/data` (`:16`).
- `backend_storage:/app/data/storage`, mounted into both `backend` (`:54`) and `worker` (`:101`). The API and worker share local storage.
- `qdrant_data:/qdrant/storage` (`:112`).
- `redis_data:/data` (`:122`).
- Named volumes declared at `:136-139`.

These are **live data volumes, not backups**. `docker compose down -v`, host loss, or volume corruption destroys them. There is no backup sidecar, cron container, or volume snapshot configuration. The M05 compose files create disposable PostgreSQL and Qdrant volumes for drills (`docker-compose.m05-postgres.yml`, `docker-compose.m05-qdrant.yml`); they are test infrastructure, not staging backup.

On Render, the backend has no persistent disk in `render.yaml`; durable data is expected in PostgreSQL and S3. That is the correct topology, but it makes the local-only storage scripts irrelevant to staging and leaves S3 unbacked.

### 4.9 Runbook accuracy

`docs/runbooks/backup-and-recovery.md` is materially out of date:

| Runbook claim | Actual code | Impact |
|---|---|---|
| Status: "IMPLEMENTED AND AUDITED" (`:3`) | No scheduled backup, no S3 backup, no retention, no live drill executed | Overstates readiness. |
| `backup-postgres.ps1 -Host ... -Port ... -Database ... -User ... -OutputDir ...` (`:14`) | Script accepts `-DatabaseUrl` and `-BackupDir` only (`backup-postgres.ps1:20-27`) | Command fails with unknown parameters. |
| Output `mmaip_db_*.dump` (`:18-20`) | Script writes `mmaip_backup_*.dump` (`:41-43`) | Operators look for the wrong artifact. |
| `verify-backup.ps1 -DumpFile ...` (`:24`) | Script accepts `-BackupFilePath` (`verify-backup.ps1:16-20`) | Command fails. |
| `restore-postgres.ps1 -DumpFile ... -TargetDatabase ... -Host ...` (`:50`) | Script accepts `-BackupFilePath` and `-TargetDatabaseUrl` (`restore-postgres.ps1:22-32`) | Command fails. |
| S3: "Enable S3 Bucket Versioning and Cross-Region Replication" (`:40-41`) | No bucket policy, lifecycle, inventory, restore, or verification procedure | Guidance is a sentence, not an operable backup. |
| Qdrant: "batch CLI script" (`:59`) | Only per-KB reindex endpoint/service and a drill script exist | No batch rebuild command exists. |
| Keys: back up in enterprise secrets storage (`:64-71`) | No escrow procedure, no key fingerprint, no restore-decrypt test, no recovery owner | Key loss remains unmitigated. |

The runbook also omits RPO/RTO, retention, encryption, offsite storage, restore verification, tenant deletion, and backup access control.

### 4.10 Paired consistency conclusion

**Paired DB+object consistency is NOT IMPLEMENTED.** The current design can produce all three inconsistent outcomes:

- DB row present, object absent (delete raced the backup, object lost independently, or DB restored without the matching bucket state).
- Object present, DB row absent (upload raced the backup, DB restored to an earlier point, or KB/tenant rows deleted without object cleanup).
- Object content differs from the DB hash (overwrite, corruption, or a partial local restore).

A consistent pair requires either (a) a storage snapshot/versioned inventory taken at a known database recovery point, or (b) a quiesced backup window with verified per-object hashes and a manifest tied to a database snapshot ID. Neither exists.

---

## 5. Required Staging Backup Policy (Definition Only — Not Configured)

This section defines what must be true before staging holds real documents. It deliberately does not create or change cloud resources. Values marked **TO-VERIFY** depend on the selected provider/plan and must be confirmed live.

### 5.1 Objectives

| Objective | Proposed staging target | Notes |
|---|---|---|
| Database RPO | ≤ 15 minutes with PITR; otherwise ≤ 24 hours | A 24-hour RPO must be accepted in writing if the provider/plan has no PITR. |
| Object RPO | ≤ 24 hours for new objects; near-zero for overwrite/delete via versioning | Versioning does not protect against bucket/account loss; replication does. |
| RTO | ≤ 4 hours for a full staging restore | Measure in the live drill; do not assume. |
| Backup encryption | At rest and in transit, provider-managed KMS or equivalent | Backups contain tenant content, audit data, and encrypted BYOK ciphertext. |
| Backup isolation | Separate bucket/account/project from the live data | Same-account versioning alone does not survive account compromise or deletion. |
| Restore verification | Weekly automated DB restore; monthly full paired DB+object drill | A backup that has never been restored is not a backup. |
| Retention | 14 daily, 8 weekly, 3 monthly DB copies; 7-day PITR window; 30-day noncurrent object versions; 90-day object inventories | Adjust only with an explicit policy decision. |
| Ownership | Named backup owner and on-call escalation | Unowned backups rot silently. |

### 5.2 PostgreSQL backup policy

**Required baseline.**

1. Enable the provider's automated backup and PITR capability if the staging plan supports it. Confirm the actual PITR window and restore semantics, not the marketing page.
2. If PITR is unavailable, run `pg_dump -Fc` on a schedule (at minimum daily; 6-hourly if the business accepts the storage/CPU cost) from a host with network access to the database, and retain the artifacts off-instance.
3. Include the Alembic revision in every manifest. Query `SELECT version_num FROM alembic_version` at dump time and record it, or record it in a sidecar file. The current manifest does not (`backup-postgres.ps1:79-86`).
4. Encrypt each dump before it leaves the database host (KMS, `age`, or equivalent). Restrict decrypt permission to the restore role.
5. Copy the dump and manifest to a separate failure domain (different bucket/account/region) immediately after creation.
6. Verify every dump with SHA-256 and a restore-to-disposable test on a schedule. Do not rely on `verify-backup.ps1` alone; it checks the archive TOC, not the data.
7. Retain according to §5.10 and delete expired copies automatically, with an audit record.
8. Monitor backup job success, duration, size anomaly, and restore-test success. A silent skip (for example, `pg_dump` missing and "Simulation Mode" exit 0) must fail the job, not pass it.

**Provider PITR matrix — all entries TO-VERIFY against the actual staging account.**

| Provider / topology | Candidate mechanism | PITR granularity | Retention | What must be verified live |
|---|---|---|---|---|
| Render PostgreSQL (current blueprint, `plan: starter`, `region: oregon`, PG 16) | Provider automated backups and/or PITR depending on plan; logical dump fallback | **TO-VERIFY** | **TO-VERIFY** | Whether the selected plan has PITR at all; window; self-service restore target; whether restore creates a new instance; egress/allowlist for `pg_dump`; backup encryption; cost. |
| AWS RDS PostgreSQL | Automated backups + WAL archiving | Typically point-in-time within the configured window | Configurable; **TO-VERIFY** | Actual window, KMS key, cross-region copy, IAM auth, restore-to-point-in-time procedure. |
| Supabase PostgreSQL | Daily backups; PITR add-on depending on plan | **TO-VERIFY** | **TO-VERIFY** | Whether PITR is enabled, window, restore UI/API, project pause behaviour. |
| Neon PostgreSQL | Plan-dependent history/PITR and branch restore | **TO-VERIFY** | **TO-VERIFY** | Restore/branch semantics, role/credential recovery, retention. |
| Self-managed PostgreSQL | `pgBackRest` or `wal-g` to object storage | Continuous WAL | Configured | Archive command health, retention, restore into a clean cluster, encryption. |

**Do not claim PITR from the blueprint.** `render.yaml:107-111` provisions a starter PostgreSQL instance but says nothing about backup retention or PITR. That must be confirmed in the Render dashboard/API and recorded in the staging evidence file.

### 5.3 Source-file / object-store policy

**Required baseline.**

1. Enable bucket versioning on the live bucket. Keys are effectively immutable today (`documents/{doc}/v{n}/...`), so versioning is primarily protection against accidental or malicious delete/overwrite.
2. Block all public access; enforce TLS-only requests; enable default encryption (SSE-S3 or SSE-KMS with a customer-managed key); enable access logging or CloudTrail-style data events if the provider supports it.
3. Apply a lifecycle policy:
   - Abort incomplete multipart uploads (even though the current client uses single PUT).
   - Transition noncurrent versions to cheaper storage after 30 days and expire them after 90 days (or the retention decision in §5.10).
   - Configure delete-marker expiry and noncurrent-version expiration to match the recovery window; verify the provider-specific lifecycle semantics before relying on them.
4. Replicate or copy to a **separate backup bucket/account**:
   - Same-region replication is the minimum for staging; cross-region is preferred.
   - A daily scheduled inventory/export is required even with replication, so a restore can be verified against a known object set.
5. Produce a daily object inventory. It must include, at minimum: key, version ID, size, checksum/ETag, last-modified, storage class, and the derived tenant/document/version identifiers. Store it with the database backup manifest.
6. For restore, copy objects from the backup bucket into a **disposable prefix/bucket**, verify size and checksum, then reconcile against the restored database before promotion.
7. Never use the live bucket as its own only backup. Versioning in the same bucket does not survive bucket deletion, account compromise, or a lifecycle misconfiguration.

**S3/MinIO adapter gaps to close or explicitly accept.**

- No `ContentType`, original filename, tenant/document metadata, checksum, or SSE headers on `put_object` (`s3.py:70-74`). The backup inventory must therefore derive identity from the key and the database, or the adapter must start writing metadata/checksums.
- No explicit timeout/retry configuration (`s3.py:62-74`). Set a bounded connect/read timeout and a retry policy before staging.
- No list/copy/version API in the abstraction (`base.py:22-51`). Reconciliation and restore tooling must use the provider SDK directly, outside the storage abstraction, or the abstraction must be extended.

### 5.4 Object-to-database mapping integrity

The database is authoritative. The required invariant is:

> For every non-deleted `Document` and every `DocumentVersion`, `file_path` identifies exactly one object whose size and SHA-256 match the DB record; every object under a tenant prefix maps to exactly one DB row or is quarantined as an orphan.

**Required daily reconciliation.**

1. Enumerate objects per tenant prefix (S3 Inventory or paginated `ListObjectsV2`; local directory walk for development).
2. Build the expected set from `documents.file_path` **and** `document_versions.file_path`, scoped by `tenant_id`.
3. Compare in both directions:
   - DB → object: missing, size mismatch, checksum mismatch. Any missing object is a **P1** failure.
   - Object → DB: object with no row is an **orphan**. Orphans are a **P2** finding, quarantined for 30 days before deletion; they are not silently ignored.
4. Persist the report as an artifact alongside the DB backup manifest: tenant ID, document counts, expected objects, found objects, missing, orphans, size mismatches, hash mismatches, total bytes, run timestamp, tool version.
5. Alert on missing objects and on any increase in orphans. Do not treat "restore succeeded" as "consistency verified".
6. Reconcile both key layouts until the double-prefix issue (§3.2) is resolved.

The existing `reconcile_database_and_storage` is a useful reference but is local-only, unscheduled, and ignores orphans in its consistency verdict (`recovery.py:64-70,239-260`). It cannot satisfy this requirement as-is.

### 5.5 Tenant identifiers and per-tenant restore

- Every object key must contain the tenant UUID (already true through `build_storage_key`, plus the extra S3 prefix). Do not use tenant names or slugs in keys.
- The backup manifest must contain a tenant catalog: `tenant_id`, slug (optional), document count, object count, total bytes, status. This is metadata, not content.
- A full `pg_dump` is cluster-wide. Per-tenant restore/export requires one of:
  - restore the full dump into a disposable database and export the tenant's rows in FK order; or
  - a purpose-built filtered export tool (not present).
- Per-tenant restore must also restore only that tenant's object prefix and must prove that a token for tenant B cannot read tenant A's restored objects or rows. The tenant prefix and route authorization are defence-in-depth; the restore verification must still exercise the negative case.
- Tenant deletion must purge both possible key layouts: `tenants/{tenant}/...` and `{tenant}/tenants/{tenant}/...`, including all versions and delete markers.

### 5.6 Ingestion and document state after restore

A database restore restores status strings, not reality. Required post-restore procedure:

1. Run the application startup recovery (`recovery.py:27-91`) to convert `PROCESSING` jobs to `FAILED/INTERRUPTED` and `PROCESSING` documents to `FAILED`.
2. Normalize `QUEUED` jobs explicitly: re-dispatch them if a worker is running, or mark them `FAILED` with an operator-visible reason. They are not recovered today (`recovery.py:34-45` only selects `PROCESSING`).
3. Reconcile every `COMPLETED` document against the restored objects. A document is not restored-complete unless its object exists and its size/hash match. Introduce a `MISSING_OBJECT` state or a failure category; do not leave a `COMPLETED` row whose bytes are gone.
4. Re-run ingestion for documents whose object is restored but whose chunks/embeddings are absent; reprocess for documents marked `FAILED`.
5. Account for the duplicate-detection trap: re-uploading the same bytes after object loss returns the existing document and a new job (`service.py:58-76`). Provide a "replace/repair object" path (force a new version or explicitly overwrite the existing key) before telling a user to re-upload.
6. Choose and document the staging queue topology. With `render.yaml` as written, there is no worker service and two uvicorn workers; in-process `asyncio.create_task` jobs can strand after a restart. M11 Stage 5 covers the claim race; Stage 8 only records that it affects restore completeness.

### 5.7 Vector data and re-indexing strategy

**pgvector.** `ChunkEmbedding.vector` lives in PostgreSQL (`models/knowledge.py:307-343`). It is included in `pg_dump` and restored with the database. No separate vector backup is required. After restore, verify `chunk_embeddings` counts, non-null vectors, and dimensional consistency. If the embedding model/dimensions changed, re-embed; do not mix versions.

**Qdrant.** Qdrant is a derived index, not a source of truth. The rebuild path is:

1. Restore PostgreSQL and verify chunks.
2. Delete or recreate the affected Qdrant collections to remove stale points (there is no automatic purge; `delete_document` is unused and swallows errors — E54).
3. Call `POST /api/v1/knowledge/{kb_id}/reindex` (`knowledge.py:516-530`) or `IngestionService.reindex_knowledge_base` (`service.py:456-535`) for every KB.
4. Verify point counts, tenant/KB filters, and idempotency. The live drill exists (`drill-live-qdrant-rebuild.sh`) but was **NOT RUN** in this stage.
5. There is no batch "reindex all KBs" command; staging must either add one or iterate KBs with a script. The runbook's claim of a batch CLI script is inaccurate (`backup-and-recovery.md:59`).

**FTS.** The full-text index is database-derived; it rebuilds with PostgreSQL. No separate action.

**Deletion.** Qdrant payloads contain chunk `content` (`service.py:367,523`). Document/KB deletion does not remove points, so deleted text remains in the vector store even though retrieval authorization filters it (`authorization.py:79-109`). Any retention/GDPR policy must include Qdrant purge, not just DB cascade.

### 5.8 Encryption-key recovery

Three encrypted surfaces exist:

| Surface | Column | Used for |
|---|---|---|
| Provider credentials | `provider_credentials.encrypted_api_key` (`models/provider.py:34`) | BYOK provider keys. |
| Retrieval config | `retrieval_configs.encrypted_api_key` (`models/knowledge.py:298`) | KB-level embedding/retrieval credentials. |
| Assistant | `assistants.byok_encrypted_key` (`models/assistant.py:37`) | Assistant-level BYOK key. |

The active key is `SECRET_ENCRYPTION_KEY`, falling back to `SECRET_KEY` if unset (`crypto.py:22-29`). Previous keys are comma-separated in `PREVIOUS_SECRET_KEYS` (`crypto.py:32-40`).

**Required policy.**

1. Escrow the exact `SECRET_ENCRYPTION_KEY` and `PREVIOUS_SECRET_KEYS` values in an external secrets manager with version history and dual control. Render's environment is not an escrow: `render.yaml:51-52` uses `generateValue: true`, and the platform has no export path. Verify whether a Blueprint re-sync or service recreation regenerates the value; do not assume it persists.
2. Record a key fingerprint (SHA-256 of the derived Fernet key) in the backup manifest. Never record the key itself.
3. Test decryption after every restore: one provider credential, one retrieval config, and one assistant key. A restore that cannot decrypt is not complete.
4. Rotation procedure: add the old key to `PREVIOUS_SECRET_KEYS`, deploy, run `python -m app.commands.rotate_encryption_keys`, verify, then remove the old key after all rows are re-encrypted. The current command scans only `RetrievalConfig` (`rotate_encryption_keys.py:57-59`); provider credentials and assistant keys are **not** rotated. Extend the command or document a manual re-entry procedure for those surfaces.
5. Key-loss runbook: if the key and all previous keys are lost, BYOK ciphertext is unrecoverable. Tenants must re-enter credentials; assistants/retrieval configs must be re-keyed. This is a business-impacting event and must be recorded, not discovered during a restore.
6. Do not store the key in the database backup, the storage archive, the repository, or a plaintext runbook.

### 5.9 Restore verification steps (required sequence)

1. Declare a restore window and stop writes (maintenance mode, proxy block, or scale-to-zero). There is no application maintenance flag today.
2. Verify the DB dump and storage archive checksums and manifests before touching any target.
3. Provision a **disposable** PostgreSQL instance of the same major version with pgvector.
4. Restore with `pg_restore --single-transaction --no-owner --no-privileges` (the current script uses `--clean --if-exists` without `--single-transaction`).
5. Verify `alembic_version` matches the expected revision; run `alembic upgrade head` only forward, never downgrade.
6. Verify row counts for tenants, users, KBs, documents, versions, chunks, embeddings, jobs, and audit. Compare with the source/manifest.
7. Verify FK integrity and tenant scoping with spot queries.
8. Decrypt a sample BYOK credential, retrieval config, and assistant key using the escrowed keys.
9. Restore objects into a disposable bucket/prefix (never directly over live), preserving versions if restoring a versioned state.
10. Run reconciliation: zero missing objects; every hash/size matches; orphans triaged. Attach the report to the restore record.
11. Normalize job/document states (§5.6); rebuild Qdrant into disposable collections; run a retrieval smoke test (hybrid and FTS).
12. Run cross-tenant negative checks: tenant A token cannot read tenant B document/object; direct key access for tenant B fails.
13. Measure RTO and record evidence (timestamps, counts, commands, logs). Promote only after all checks pass.
14. After promotion, re-run reconciliation and monitor for 24 hours; retain the restore evidence with the backup ID.

### 5.10 Retention and deletion policy (including GDPR-style tenant erasure)

**Proposed retention (policy decision; not configured).**

| Data class | Store | Proposed retention | Deletion mechanism today |
|---|---|---|---|
| Documents + versions + chunks + embeddings | PostgreSQL | Tenant policy; default staging 90 days after tenant deletion request | Partial: document delete cascades DB rows; KB delete cascades DB rows; no tenant delete |
| Original objects | S3/local | Follows document retention | Partial: document delete removes only `doc.file_path` and suppresses errors; KB delete removes nothing |
| Qdrant points | Qdrant | Follows document; must be purged | **None** (method exists, unused) |
| Conversations/messages | PostgreSQL | Proposed 90 days staging / contractual for production | Conversation soft-delete only (`conversations.py:132`); messages remain |
| Observability traces | `backend/data/observability_traces.json` | Proposed 30 days | **None**; bounded ring buffer per tenant only |
| Audit logs | PostgreSQL | Proposed 1 year (legal) | **None**; retained in DB/backups |
| DB backups | Backup bucket | 14 daily / 8 weekly / 3 monthly; PITR 7 days | **None** (no pruning) |
| Object backup inventory | Backup bucket | 90 days | **None** |
| Provider snapshots | Provider | Provider retention; verify | Provider-managed |

**Required tenant erasure runbook (not implemented).**

1. Authorize and record the request (tenant admin/DPA, ticket, approver). Place the tenant in a deletion-pending state; disable access.
2. Export any contractually required data before deletion.
3. Collect all object keys for the tenant from `documents.file_path` and `document_versions.file_path`, plus a prefix listing for both layouts (`tenants/{tenant}/` and `{tenant}/tenants/{tenant}/`).
4. Delete all object versions and delete markers under both prefixes. A plain `delete_object` on a versioned bucket only adds a delete marker; it does not erase bytes.
5. Delete Qdrant points for the tenant across all collections/dimensions. This requires a tenant-wide delete operation; current code only offers per-document deletion and does not call it.
6. Delete tenant database rows in FK-safe order (or a verified `ON DELETE CASCADE` from `tenants`). Verify children: memberships, departments, KBs, documents, versions, chunks, embeddings, jobs/events, conversations/messages, API keys, credentials, assistants, publications, evaluations, audit rows as policy allows.
7. Remove the tenant's traces from the persisted trace file (stop the app or use a safe rewrite), then restart the tracer.
8. Leave a deletion audit event with counts and operator identity, excluding content.
9. Verify: zero DB rows, zero objects (all versions), zero Qdrant points, zero traces; run reconciliation for the tenant and record the report.
10. Backups: primary-store deletion is immediate; backup copies expire on the retention schedule. If the contract requires earlier erasure, use crypto-shredding (per-tenant encryption keys) or a provider capability that supports selective backup deletion; **neither is implemented today**. Document the residual backup window in the deletion record.
11. Legal hold: suspend deletion for the hold scope and record the exception.

**Current verdict: GDPR-style tenant erasure is NOT IMPLEMENTED.** There is no tenant-delete endpoint (M11 Stage 7 also records this), no Qdrant tenant purge, no trace purge, no backup pruning, and no deletion certificate.

### 5.11 Schedule, ownership, and evidence

| Activity | Frequency | Owner | Evidence |
|---|---|---|---|
| PostgreSQL backup/PITR check | Daily | Backup owner | Job log, dump SHA, `alembic_version`, PITR status |
| Object inventory + reconciliation | Daily | Platform on-call | Inventory file, reconciliation report, alert status |
| DB restore to disposable target | Weekly | Backup owner | Restore log, row counts, RTO |
| Full paired DB+object restore drill | Monthly | Platform lead | Signed checklist, reconciliation report, RTO/RPO |
| Key-escrow decrypt test | Monthly/after rotation | Security owner | Decrypt test result, key fingerprint |
| Tenant-erasure drill (synthetic tenant) | Quarterly | Security/Privacy | Deletion certificate, zero-residual report |
| Retention/pruning audit | Monthly | Platform lead | Expired-object/backup report |

Backup artifacts, manifests, and restore reports must be stored outside the application repository and access-controlled. `backups/` is not in `.gitignore` today (E59); do not commit dumps or archives.

---

## 6. Failure-Mode Analysis

### 6.1 Summary matrix

| # | Failure | Current behaviour | Detection today | User-visible effect | Required runbook |
|---|---|---|---|---|---|
| a | Object exists, DB row missing | Orphan object; no cleanup | Local reconciliation only; `is_consistent` ignores orphans; no S3 inventory | None directly (no raw-file route); storage cost and data remanence | Quarantine, wait out backup window, delete all versions, audit |
| b | DB row exists, object missing | Reprocess fails after retries; row stays `COMPLETED`; re-upload is treated as duplicate | Local reconciliation only; ingestion job error; no proactive alert | Reprocess/download of original impossible; extracted text/retrieval may still work | Restore object from backup/versioning, verify hash, reprocess; if unrecoverable, mark `MISSING_OBJECT` and use repair path |
| c | Delete partially succeeds | Object and DB diverge silently; endpoint returns 204 | None (bare `except`, no audit); reconciliation not scheduled | Orphan object or dangling row; later reprocess fails | Verify both stores, restore or purge, reconcile, audit; add outbox |
| d | Storage unavailable during upload | `storage.save` raises before DB row; HTTP 500; no partial object; request may hang | Provider errors only; `/ready` ignores storage | Upload fails; retry after recovery | Fail 503, verify bucket/credentials, reconcile orphans, resume |
| e | DB restored without object store | DB content and vectors usable; reprocess fails; duplicate re-upload blocked | Reconciliation (if run) reports all missing | Original bytes unavailable; retrieval works from chunks/extracted text | Restore objects to matching keys, verify hashes, reprocess; otherwise mark missing and communicate |
| f | Object store restored without DB | Objects unreachable; no import/list tool; new uploads create new keys | Orphan report (local only); S3 inventory diff | None directly; storage duplication; risk of accidental lifecycle deletion | Restore matching DB snapshot first; quarantine otherwise; controlled importer only with exact key/hash mapping |

### 6.2 (a) Object exists, database row missing

**Why it happens.**

- The object is written before the DB transaction (`service.py:89-143`). Any failure between `storage.save` and the commit leaves an object with no row.
- A document or KB delete removes DB rows but leaves objects (`documents.py:83-91`, `knowledge.py:197-225`); KB deletion leaves the entire KB prefix.
- The database is restored to an earlier point than the bucket state, or the bucket is restored to a later state than the database.
- An object is copied into the bucket manually or by a replication job without the corresponding DB row.
- A tenant/document purge deletes DB rows first and fails before object deletion.

**Current detection.** Only `reconcile_database_and_storage` reports `orphan_files`, and it only works on a local path (`recovery.py:239-260,299-304`). It is not scheduled. `is_consistent` ignores orphans (`recovery.py:64-70`). There is no S3 inventory comparison. There is no cost/anomaly alert.

**Impact.** No application route exposes raw objects, so this is not a direct data leak or user-visible failure. It is storage cost, data remanence, and a retention/GDPR problem. If the object belongs to a deleted tenant, it is a deletion failure.

**Required operational runbook.**

1. Take the object key from the reconciliation report/inventory. Parse tenant, KB, document, version, and filename from the key.
2. Query `documents` and `document_versions` by tenant and document ID. Confirm there is no row (or only a soft-deleted row).
3. Check the paired backup manifests and the object's last-modified time. If the object is newer than the last DB backup, treat it as an upload that raced the backup; do not delete until the next successful paired backup or the 30-day grace period.
4. If the object belongs to a deleted document/KB/tenant, confirm the deletion authorization and legal-hold status.
5. Quarantine: move/copy to a quarantine prefix if the bucket lifecycle does not already isolate it. Record the key, size, hash, and decision.
6. After the grace period, delete **all versions and delete markers** for the key, not just the current version.
7. Write an audit record with counts and the reason. Re-run reconciliation to confirm zero untracked objects in the tenant prefix.

**Required engineering control (not implemented).** A deletion outbox/tombstone, or a periodic orphan sweeper with a quarantine state. The sweeper must never delete an object whose DB row exists, and must never touch objects younger than the grace period.

### 6.3 (b) Database row exists, object missing

**Why it happens.**

- Delete ordering: the object is deleted before the DB commit; if the commit fails, the row survives (`documents.py:83-91`, `session.py:44`).
- Database restored without the object store, or the bucket is lost/emptied while PostgreSQL survives.
- An operator deletes an object directly, a lifecycle rule expires it, or versioning is disabled and a delete is irreversible.
- The upload committed the DB row but the provider lost the object (rare; check provider durability/versioning).

**Current behaviour.** Ingestion `storage.get` raises (`service.py:185`); the generic handler retries up to `max_retries` and then marks the job/document `FAILED` (`service.py:421-451`). The document may still have `status="COMPLETED"` from the original ingestion, so status alone is misleading. `GET /documents/{id}/content` still returns `extracted_text` from PostgreSQL (`documents.py:164-189`), and retrieval can still work from chunks/embeddings. There is no `MISSING_OBJECT` state. Re-uploading the same bytes is intercepted by duplicate detection (`service.py:58-76`) and does **not** write a new object; it only creates another job that will fail again.

**Impact.** The original file is unavailable; reprocess/OCR cannot run; a user cannot repair the document by re-uploading. The extracted text and vectors may remain usable, so the failure can be silent to retrieval users while the source of truth for the original is gone.

**Required operational runbook.**

1. Do not delete the database row. It is the only remaining record of the extracted content and the object key.
2. Query the backup inventory for the exact key (and all versions). Check the live bucket's version list and replication target.
3. If found, restore the object to the exact key, verify size and SHA-256 against `documents.file_size`/`file_hash`, then run reconciliation.
4. If the object is recoverable, reprocess the document (new ingestion job) and verify chunks/embeddings.
5. If not recoverable, mark the document `MISSING_OBJECT` (or `FAILED` with that category) and inform the owner. To accept a re-upload, use a repair path that replaces the object at the existing key or creates a new version; the current duplicate path does not do this.
6. If the content is unrecoverable and the tenant wants it deleted, run the document-deletion procedure and then the orphan/Object-version purge.
7. Record the incident, RPO gap, and whether the object was inside the backup window.

**Required engineering control.** A repair endpoint/CLI that can (i) restore bytes to an existing key after hash verification and (ii) force a new version/overwrite bypassing duplicate detection. Neither exists.

### 6.4 (c) Delete partially succeeds

**Current sequence and outcomes.**

| Sub-case | What happens | State left behind |
|---|---|---|
| Object delete fails; DB delete succeeds | `storage.delete` raises, is swallowed by `except Exception: pass` (`documents.py:87-88`); DB row is deleted; request returns 204 | Orphan object; no audit of failure |
| Object delete succeeds; DB delete/commit fails | Object removed first; `repo.delete` or the request commit fails | DB row points at missing bytes; subsequent delete sees no object |
| S3 object does not exist | `delete_object` succeeds and the provider returns `True` (`s3.py:117-118`); caller ignores the return | Indistinguishable from a real delete |
| Document version paths differ | Only `doc.file_path` is deleted; older `DocumentVersion.file_path` objects remain | Versioned-object leak when versioning is introduced |
| KB delete | No storage call at all (`knowledge.py:197-225`); DB cascade only | Entire KB prefix orphaned |
| Qdrant/traces | No delete call (`qdrant_store.py:239-262` unused); traces untouched | Text remains in Qdrant payload and traces |

**Impact.** A 204 response is not evidence of deletion. The system can accumulate objects after deletion, or retain rows that cannot be reprocessed. Both directions are silent.

**Required operational runbook.**

1. Treat any storage exception during delete as a failed delete; do not return 204 until the outcome is known. This requires a code change (remove the bare `except`, record an outbox entry).
2. On a reported partial delete, inspect both stores:
   - `head_object`/list versions for the key;
   - `SELECT` the document/version row scoped to the tenant.
3. If the row is gone and the object exists, purge all versions after the grace period and audit.
4. If the row exists and the object is gone, restore the object from backup if the document is still wanted; otherwise mark it and retry the delete.
5. For KB deletion, capture the document/version keys before the cascade (or list the tenant/KB prefix afterwards) and purge them. The prefix contains tenant, KB, and document IDs; the DB is gone, so the prefix listing is the only mapping.
6. Purge Qdrant points by tenant/KB and remove traces for the deleted scope.
7. Run reconciliation and attach the report to the incident.

**Required engineering control.** Delete-outbox/tombstone with retries and a reconciliation job; delete all version paths; call the vector-store delete; do not swallow errors.

### 6.5 (d) Storage unavailable during upload

**Current behaviour.**

- `storage.save` is called before any DB write (`service.py:89-90`). A connection/auth/5xx failure raises; no `Document` row is created; the API returns a generic 500 (no storage-specific handler). There is no partial object under the final key: local uses temp+replace (`local.py:41-48`); S3 uses a single atomic PUT (`s3.py:70-74`).
- A local `.tmp` file can remain after a crash/failure.
- If the S3 PUT succeeds but the response is lost or the DB commit fails, an orphan object is created (failure mode a).
- No explicit SDK timeout/retry configuration; a degraded store can hold the request open for the provider default.
- `/health` and `/ready` do not check storage (`main.py:75-97`); Render's health check remains green during a storage outage.
- The client may retry. If the DB row committed, duplicate detection returns the existing document and creates a new job (no duplicate object). If it did not commit, a new object/key may be written on retry.

**Impact.** Uploads fail (correctly, no DB row), but the failure is a generic 500, the platform reports healthy, and retries can create orphans at the storage/DB boundary.

**Required operational runbook.**

1. Surface storage unavailability as 503, not 500, and do not create a partial DB row.
2. Verify bucket existence, region, credentials, clock skew, bucket policy, and provider status. `exists()` must not be used for this diagnosis because it converts auth failures to `False` (`s3.py:120-142`).
3. Check for `.tmp` files (local) or orphan keys (S3) created around the failure window; reconcile.
4. If the provider is down for an extended period, pause uploads at the proxy/maintenance layer and communicate; do not queue unbounded retries inside the API.
5. After recovery, run a single-object PUT/GET/HEAD/DELETE probe and then reconciliation before resuming users.
6. Record the outage window so backup/restore decisions can account for objects that may have been written without rows.

### 6.6 (e) Backup restored without object store

**Current behaviour.**

- The application starts with restored PostgreSQL. Document rows, versions, chunks, embeddings (pgvector), extracted text, jobs, and audit are present.
- `GET /documents/{id}/content` works from `extracted_text`; retrieval works from chunks and pgvector/FTS; Qdrant can be rebuilt from chunks without objects (`service.py:456-535`).
- `POST /documents/{id}/reprocess` creates a job, but ingestion fails at `storage.get` and eventually marks the job/document failed (`service.py:185,421-451`).
- There is no raw-file download endpoint, so users may not notice the missing original unless they rely on reprocessing/OCR.
- Documents can remain `COMPLETED` while their objects are missing. Reconciliation (if run) reports every file as missing; it is not scheduled.
- Re-uploading the same bytes is blocked by duplicate detection.

**Impact.** This is the **least destructive** restore shape: text, chunks, and vectors survive; only the original bytes and reprocessing are lost. It is still not a complete restore, and the `COMPLETED` status is inaccurate.

**Required operational runbook.**

1. Restore objects from the backup bucket/versioning into the exact keys. Do not restore into a new prefix and expect the DB to find them.
2. Verify size and SHA-256 per document against the DB; run reconciliation to zero missing.
3. If objects are unrecoverable:
   - Keep the database content if the business accepts loss of originals; mark documents `MISSING_OBJECT`/`SOURCE_LOST` so status is truthful.
   - Offer re-upload through a repair path that replaces the object at the existing key; current duplicate detection prevents this.
   - If the tenant requires deletion, delete the document and purge any remaining versions.
4. Rebuild Qdrant from chunks if needed; run retrieval smoke tests.
5. Communicate the RPO gap and record which documents lost originals.

### 6.7 (f) Object store restored without database

**Current behaviour.**

- Objects exist under tenant prefixes, but there are no `Document`/`DocumentVersion` rows. The application has no bucket-listing, import, or raw-download route, so they are unreachable through the product.
- Reconciliation on a local path would report every object as an orphan; the S3 equivalent does not exist. `is_consistent` ignores orphans anyway.
- New uploads create new document UUIDs and therefore new keys; they do not attach to the restored objects. The bucket accumulates duplicates.
- If a matching DB snapshot is restored later, keys align because they contain the document UUID and version. If the DB snapshot is older/newer, some objects match and some do not.
- The objects are still tenant-prefixed and not public, so this is not immediately a cross-tenant exposure. It is a recovery and retention problem.

**Impact.** Object data is stranded. A lifecycle rule that treats orphans as garbage could delete the only surviving copy of the documents. A blind import could attach the wrong object to a document.

**Required operational runbook.**

1. Identify the paired DB backup/manifest for the object state (same backup window, same bucket prefix, same object count/bytes). Restore that DB snapshot first; do not import objects into an unrelated database.
2. If a matching DB snapshot exists, restore it, run reconciliation, and verify hashes before serving.
3. If no matching DB exists, quarantine the objects (copy to an isolated prefix/bucket or mark them with a hold) and disable lifecycle deletion for the quarantine scope.
4. Only if recovery is impossible and the business requires the content, build a controlled importer that:
   - parses tenant/KB/document/version from the key;
   - computes the real size/hash of the object;
   - creates the `Document`/`DocumentVersion` rows with the exact key and hash;
   - verifies tenant ownership and never crosses tenants;
   - records an audit event.
   No such importer exists.
5. Never make the bucket public or bypass the tenant prefix to "recover" access.
6. Record which objects remain quarantined and their retention deadline.

### 6.8 Cross-cutting controls required by all six modes

- **Deletion outbox/tombstone** with retries, so object and DB deletion converge.
- **Provider-aware reconciliation** (S3 inventory/list + DB), scheduled, with missing objects as P1 and orphans as P2.
- **Immutable/versioned objects** so a delete is recoverable within the window.
- **A `MISSING_OBJECT`/`SOURCE_LOST` document state** and a repair/force-new-version path.
- **Storage health in readiness** and explicit SDK timeouts.
- **A paired backup manifest** that binds a DB snapshot ID, Alembic revision, bucket/prefix, object inventory, and key fingerprint.
- **A tenant-erasure workflow** that covers DB, objects (all versions), Qdrant, traces, and backup expiry.

---

## 7. Current-Capability Verdict Matrix

| # | Capability | Verdict | Evidence | Notes |
|---|---|---|---|---|
| 1 | Local storage save/get/exists/get_size | **TESTED** (hermetic) | E03-E05, E34, E37 | Temp+replace write; tenant root containment. Local `delete` is implemented but not directly covered by the storage tests. |
| 2 | S3-compatible CRUD | **IMPLEMENTED; TESTED mocked only; NOT RUN live** | E06-E10, E36 | No real bucket/credential round-trip; `aioboto3` is mocked. |
| 3 | Fail-closed production local-storage rejection | **TESTED** | E11, E35 | Only for `ENVIRONMENT=production`. |
| 4 | Staging fail-closed storage selection | **NOT IMPLEMENTED** | E11, E48 | `staging` + `local` passes validation. |
| 5 | Tenant-prefixed keys | **TESTED** | E02, E06, E35 | Local `tenants/{t}/...`; S3 `{t}/tenants/{t}/...` (double prefix). |
| 6 | Local path-traversal containment | **TESTED** | E03, E34 | `resolve()` + `relative_to`. |
| 7 | S3 key traversal neutralisation | **TESTED** | E06, E35 | Empty/`.`/`..` segments removed. |
| 8 | Safe filename sanitisation | **TESTED** | E02, E35 | No length bound. |
| 9 | Filename/key length enforcement | **NOT IMPLEMENTED** | E02, E17, `models/knowledge.py:98-100` | PostgreSQL insert can fail after the object write. |
| 10 | Verified MIME detection | **IMPLEMENTED** | E18 | Stored in `Document.mime_type`. |
| 11 | Client MIME / original metadata | **IMPLEMENTED** | E18 | Client MIME stored in JSON metadata only. |
| 12 | Object-store content type / metadata | **NOT IMPLEMENTED** | E07 | No `ContentType`, checksum, SSE, or custom metadata on PUT. |
| 13 | Global max file size | **IMPLEMENTED** | E14, E15 | Enforced after full body read. |
| 14 | Per-KB max file size | **NOT IMPLEMENTED** | §3.3; `models/knowledge.py:81` | Stored but never read. |
| 15 | Max files per request | **IMPLEMENTED** | E23 | Per-file commits mean partial batch success. |
| 16 | Atomic object write | **IMPLEMENTED** | E04, E07 | Local temp+replace; S3 single PUT. |
| 17 | DB/object atomicity | **NOT IMPLEMENTED** | E15-E17 | Object is written before DB commit; no compensation. |
| 18 | Duplicate detection | **IMPLEMENTED** | E16 | Hash within KB; returns existing doc + new job. |
| 19 | Duplicate/repair path after object loss | **NOT IMPLEMENTED** | E16, §6.3 | Re-upload cannot restore the object. |
| 20 | Raw-file download | **NOT IMPLEMENTED** | E19; `documents.py:164-189` | Only extracted text is exposed. |
| 21 | `exists` / `get_size` in production paths | **IMPLEMENTED but unused** | E05, E09, E10 | Only tests call them. |
| 22 | Document delete | **IMPLEMENTED; UNSAFE** | E25, E26 | Object first, errors swallowed, DB commit later. |
| 23 | Knowledge-base delete cleanup | **NOT IMPLEMENTED** | E24 | DB cascade only; objects remain. |
| 24 | Qdrant point deletion | **NOT IMPLEMENTED** | E54, E55 | Methods exist; no call sites; payload retains content. |
| 25 | Local DB↔file reconciliation | **TESTED** (hermetic) | E31-E34 | Local only; unscheduled; ignores orphans in verdict. |
| 26 | S3 DB↔object reconciliation | **NOT IMPLEMENTED** | E31, E33 | No provider-aware implementation. |
| 27 | Scheduled reconciliation / orphan sweeper | **NOT IMPLEMENTED** | E31 | No scheduler, CLI, or deletion. |
| 28 | Startup job recovery | **TESTED** | E27; M11 Stage 5 | `PROCESSING` → `FAILED/INTERRUPTED` only. |
| 29 | `QUEUED` recovery / re-dispatch | **NOT IMPLEMENTED** | E27, E28 | No worker in `render.yaml`; stranded jobs. |
| 30 | PostgreSQL logical backup | **IMPLEMENTED; NOT RUN** | E38, E39 | Manual PowerShell; no schedule/retention/encryption. |
| 31 | PostgreSQL PITR | **NOT IMPLEMENTED / NOT RUN** | E38, E48 | Provider-specific; **TO-VERIFY**. |
| 32 | Local storage backup | **IMPLEMENTED; TESTED (Python helper); NOT RUN live** | E29, E34, E40 | PowerShell script not exercised; local only. |
| 33 | S3 versioning/lifecycle/replication backup | **NOT IMPLEMENTED** | E40, `runbook:40-41` | One sentence of guidance; no configuration or inventory. |
| 34 | Paired DB+object consistency | **NOT IMPLEMENTED** | E41, §4.4 | Sequential, no quiesce/snapshot/inventory. |
| 35 | PostgreSQL restore | **IMPLEMENTED; NOT RUN** | E42 | Treats non-zero exit as warning; no transactional restore. |
| 36 | Local storage restore | **TESTED (Python helper); NOT RUN (PowerShell/live)** | E30, E34, E43 | Python helper has zip-slip and hash checks; PowerShell uses in-place `Expand-Archive` with no explicit guard. |
| 37 | S3 storage restore | **NOT IMPLEMENTED** | E40-E43 | No script or procedure. |
| 38 | Backup integrity verification | **IMPLEMENTED; NOT RUN** | E44 | Checksum + TOC; no data restore. |
| 39 | Live PostgreSQL restore drill | **NOT RUN** | E45 | Containerized, disposable DB, BYOK check. |
| 40 | Live Qdrant rebuild drill | **NOT RUN** | E46 | DB-source rebuild, tenant filter, idempotency. |
| 41 | Encryption-key escrow | **NOT IMPLEMENTED** | E48, E50, §5.8 | Render `generateValue`; no external escrow or fingerprint. |
| 42 | Key rotation coverage | **PARTIAL / NOT IMPLEMENTED for 2 surfaces** | E51, E52 | Only `RetrievalConfig` is rotated. |
| 43 | Tenant erasure (DB+objects+Qdrant+traces) | **NOT IMPLEMENTED** | E24, E53-E55, M11 Stage 7 | No tenant delete endpoint or purge tooling. |
| 44 | Retention/pruning (backups, objects, traces) | **NOT IMPLEMENTED** | E40, E53, E59 | Scripts never prune; no lifecycle policy in repo. |
| 45 | Storage health in readiness | **NOT IMPLEMENTED** | E58 | `/ready` checks PostgreSQL only. |
| 46 | Backup scheduling/ownership | **NOT IMPLEMENTED** | E38-E44, E48 | Manual scripts; no cron/Render job. |
| 47 | Backup encryption/offsite/access control | **NOT IMPLEMENTED** | E38, E40 | Plaintext local artifacts; `backups/` not ignored. |

---

## 8. Gap Register

| ID | Severity | Gap | Evidence | Impact | Required action |
|---|---|---|---|---|---|
| S8-01 | BLOCKER | No S3 backup/versioning/lifecycle/inventory/replication for the staging backend | E40, E48, runbook:40-41 | Staging objects have no recoverable copy; bucket loss is total loss | Enable versioning, lifecycle, SSE, public-access block, replication/copy, daily inventory; store outside live account |
| S8-02 | BLOCKER | Paired DB+object backup is sequential, not consistent | E41, §4.4 | Restored DB can reference missing objects; objects can be orphaned | Quiesce or snapshot; bind DB snapshot ID + object inventory; verify before promotion |
| S8-03 | BLOCKER | Delete ordering + swallowed errors + no cleanup for KB/Qdrant/traces | E24-E26, E54-E56 | Silent orphans or dangling rows; deleted text remains in Qdrant/traces | Outbox/tombstone; delete DB after object success; all version paths; vector/trace purge; log/audit failures |
| S8-04 | HIGH | No tenant erasure or retention policy implementation | E24, E53-E55, §5.10 | GDPR/contract deletion cannot be honored; backups/traces/Qdrant retain data | Implement tenant purge tooling; define retention; deletion certificate; backup expiry decision |
| S8-05 | HIGH | Key escrow and rotation incomplete | E48, E50-E52 | Key loss makes BYOK unrecoverable; rotation misses two surfaces | External escrow + fingerprint; decrypt test; extend rotation to provider credentials and assistant keys |
| S8-06 | HIGH | No live S3/MinIO validation; storage not in readiness; errors masked | E07-E09, E36, E58 | Staging can be "healthy" while uploads fail; mocked tests miss auth/region/policy issues | Live PUT/GET/HEAD/DELETE probe; storage readiness; explicit timeouts/retries; fix `exists` semantics |
| S8-07 | HIGH | Staging can run local storage (guard is production-only) | E11, E48 | Ephemeral filesystem data loss in staging | Extend fail-closed guard to `staging`/non-development or require explicit override |
| S8-08 | HIGH | Duplicate detection prevents object-loss self-healing | E16, §6.3 | A user cannot repair a document by re-uploading | Add force-new-version/replace-object repair path |
| S8-09 | MEDIUM | Reconciliation is local-only, unscheduled, and ignores orphans | E31-E33 | S3 divergence invisible; orphan cost/remanence | Provider-aware scheduled reconciliation; missing=P1, orphan=P2; delete/quarantine workflow |
| S8-10 | MEDIUM | Filename/key length unbounded; object write precedes DB insert | E02, E17 | PostgreSQL insert failure after successful object write → orphan | Validate filename and key length before save; hash/length limits |
| S8-11 | MEDIUM | S3 key double prefix; provider return values inconsistent | E01, E06, `local.py:49`, `s3.py:75` | Restore/purge/migration tooling mismatches; future prefix change strands keys | Decide one canonical layout; align local/S3; document migration |
| S8-12 | MEDIUM | Runbook commands/artifacts do not match scripts; status overstated | E49 | Operators cannot follow the documented procedure | Rewrite runbook against actual parameters; mark live drills NOT RUN |
| S8-13 | MEDIUM | Backup artifacts unencrypted, local, unpruned; `backups/` not ignored | E38, E40, E59 | Confidentiality/retention risk; accidental commit | Encrypt, offsite, retention job; add ignore rule; access control |
| S8-14 | MEDIUM | Restore scripts unsafe semantics (non-zero warning; simulation exit 0; no `--single-transaction`; no explicit zip-slip) | E39, E42-E44 | Incomplete restore can look successful; malicious archive risk | Fail on non-zero; remove simulation success; transactional restore; explicit traversal validation |
| S8-15 | MEDIUM | No worker in staging blueprint; `QUEUED` jobs not recovered | E27, E28, E48; M11 Stage 5 | Jobs strand after restart; restored state never normalizes | Decide worker topology; recover/requeue `QUEUED`; lease/claim (Stage 5) |
| S8-16 | LOW | Upload buffers full body before size check; per-file commits; KB limit unused; text truncation by chars | E14, E22, E23; §3.3 | Memory/disk pressure; partial batch success; DB bloat | Pre-check size; per-file error isolation; enforce KB limit; byte-aware truncation |
| S8-17 | LOW | No S3 content-type/metadata/checksum/SSE; per-op session | E07 | Objects lack portable metadata; connection overhead | Add metadata/checksum/SSE; reuse client; document restore reliance on DB |
| S8-18 | LOW | Empty-storage backup marker restored as an orphan; PowerShell/Python mismatch | E40, `recovery.py:126-127,181-182` | Harmless but confusing orphan after empty restore | Align marker handling; skip marker on restore |
| S8-19 | LOW | No raw-file download; `exists`/`get_size` dead code | E19, E21 | Users cannot retrieve originals; no preflight integrity check | Product decision; wire a safe download if required; use checks in reprocess |
| S8-20 | LOW | `DocumentVersion.file_path` not reconciled or deleted | E25, E31, `models/knowledge.py:157` | Future versioning leaks objects; current v1 masks it | Include all version paths in delete/reconcile |


---

## 9. Recommended Pre-Staging Actions (Smallest Set)

These are recommendations only. No action below was performed in this stage.

### 9.1 P0 — required before any real document is uploaded

| ID | Action | Type | Acceptance evidence |
|---|---|---|---|
| P0-1 | Configure the live S3 bucket: versioning, default encryption, block public access, TLS-only policy, lifecycle for noncurrent versions/delete markers, and a separate backup bucket/account with replication or daily copy. | Config (cloud) | Bucket settings captured; versioned delete/restore demonstrated on a synthetic key. |
| P0-2 | Establish PostgreSQL backup: provider PITR if available, otherwise scheduled `pg_dump -Fc`; include `alembic_version`; encrypt; copy offsite; retain per policy. | Config + script | Three consecutive verified backups; PITR window confirmed **TO-VERIFY**; manifest contains revision. |
| P0-3 | Escrow `SECRET_ENCRYPTION_KEY` and `PREVIOUS_SECRET_KEYS` in an external secrets manager; record fingerprints; test decrypt after a restore. | Config/security | Restore test decrypts one credential/config/assistant key; escrow access is dual-control. |
| P0-4 | Make delete converge: delete DB row only after object deletion succeeds (or enqueue an outbox/tombstone); delete all version paths; purge KB objects, Qdrant points, and traces; log/audit failures; stop swallowing exceptions. | Code | Failure-injection test shows no orphan/dangling row; KB delete leaves zero objects/points; audit records outcome. |
| P0-5 | Implement provider-aware reconciliation (S3 inventory/list + DB) and schedule it; treat missing objects as P1 and orphans as P2; produce a report artifact. | Code + ops | Daily report for a synthetic tenant: zero missing, orphan count stable; missing-object alert fires. |
| P0-6 | Run a live paired restore drill: DB dump → disposable DB; object copy → disposable prefix; verify hashes; reconcile; rebuild Qdrant; retrieval smoke test; measure RTO. | Test | Signed drill report with counts, hashes, RTO, and zero missing. |
| P0-7 | Add length/size guards and a repair path: reject over-length filename/path before `storage.save`; pre-check body size; allow force-new-version/overwrite after object loss (bypass duplicate detection). | Code | Postgres boundary tests: 255/256-char filename, 50 MiB ± 1, 10/11 files, duplicate-after-delete repair. |
| P0-8 | Correct the runbook and artifact hygiene: fix parameter names/artifact names; mark live drills NOT RUN; encrypt/retain/prune backups; ignore `backups/`; add a storage readiness probe to `/ready`. | Docs/config/code | Runbook commands execute as written; no plaintext backup in repo; `/ready` fails on bucket outage. |

### 9.2 P1 — required before tenants whose data must be erasable

| ID | Action | Type | Acceptance evidence |
|---|---|---|---|
| P1-1 | Define and implement the tenant-erasure workflow across DB, objects (all versions), Qdrant, traces, and backup expiry; issue a deletion certificate. | Policy + code | Synthetic tenant purge leaves zero rows/objects/points/traces; backup residual documented. |
| P1-2 | Define retention for documents, conversations/messages, traces, audit, backups, and inventories; automate pruning. | Policy + ops | Retention job report; expired artifacts removed; no over-retention. |
| P1-3 | Decide staging queue topology: either a safe single-process API-only mode with explicit `QUEUED` recovery, or a leased worker with atomic claim. | Code/ops | Restart drill leaves no stranded `QUEUED` job. |
| P1-4 | Unify the S3 key layout (remove the double tenant prefix) or document it permanently and update all tooling. | Code + docs | New/old key migration plan; purge/restore handles both layouts. |
| P1-5 | Extend key rotation to provider credentials and assistant keys, or document a manual re-key procedure for both. | Code/docs | Rotation test re-encrypts all three surfaces. |

### 9.3 Explicitly deferred (not required for synthetic staging)

- Cross-region disaster recovery with automated failover.
- Per-tenant encryption keys / crypto-shredding (unless required by the retention decision).
- Raw-file download UX.
- Backup deduplication/archival tiering.
- Multi-provider object replication beyond the staging provider.

---

## 10. Live Validation Checklist (Required Before Real Documents)

No item below was executed in this stage. Each must be run against the real staging provider with synthetic data only, and the evidence retained.

### 10.1 Preflight (configuration and connectivity)

- [ ] Confirm the actual staging storage backend is `s3` (or `minio`) and `ENVIRONMENT` is not silently accepting `local`.
- [ ] `HeadBucket`/list permission works; wrong-bucket and wrong-region probes fail clearly.
- [ ] Bucket versioning is `Enabled`; a synthetic overwrite and delete can be restored from a noncurrent version.
- [ ] Default encryption is on (SSE-S3/SSE-KMS); public access is blocked; TLS-only policy is enforced.
- [ ] Lifecycle rules are visible and will not delete current objects.
- [ ] Backup bucket/account is separate and writable by the backup job only.
- [ ] `/ready` fails when the bucket is unreachable (after P0-8) and recovers when it returns.
- [ ] PostgreSQL PITR/backup status and retention are confirmed; record the exact plan and window (**TO-VERIFY**).

### 10.2 Storage CRUD and boundaries

- [ ] Upload a 1 KiB text file; `get` returns identical bytes; DB row/key match.
- [ ] Upload exactly 50 MiB (accepted) and 50 MiB + 1 byte (rejected before DB row/object write after P0-7).
- [ ] Upload 10 files in one request (accepted) and 11 files (rejected).
- [ ] Upload a 255-character filename and a 256+ character filename; confirm controlled rejection, no orphan object.
- [ ] Upload a Unicode filename and a filename containing `../`, backslashes, leading dots; confirm safe key and no escape.
- [ ] Upload the same bytes twice; confirm duplicate returns the existing document and creates a job, with no second object.
- [ ] Delete the document; confirm the object (and all versions) is gone and the DB row is gone.
- [ ] Attempt to read/delete tenant A's key as tenant B; confirm failure and no existence oracle.
- [ ] `exists`/`get_size` behave as intended (or remain unused) against the real provider.

### 10.3 Failure injection

- [ ] Revoke `PutObject` temporarily; upload returns a clear failure, no DB row, no partial object, and `/ready` reflects degradation.
- [ ] Allow upload, then delete the object directly; reprocess fails with `MISSING_OBJECT`, not a misleading `COMPLETED`.
- [ ] Simulate a DB commit failure after object write (constraint/length); confirm orphan is detected by reconciliation and cleaned by the sweeper.
- [ ] Kill the API process after object write and before commit; restart; reconcile; confirm orphan outcome is documented.
- [ ] Kill the API during ingestion; restart; confirm `PROCESSING` becomes `FAILED/INTERRUPTED` and `QUEUED` is handled per the chosen topology.
- [ ] Delete a document while storage is unavailable; confirm no 204 success and no silent divergence.
- [ ] Delete a knowledge base; confirm zero objects, zero Qdrant points, zero traces for that KB.
- [ ] Run reconciliation after every injection; attach the report.

### 10.4 Backup and restore

- [ ] Create a DB backup; verify SHA-256 and TOC; confirm `alembic_version` in the manifest.
- [ ] Restore the dump into a disposable PostgreSQL instance with `--single-transaction`; verify row counts and FKs.
- [ ] Decrypt one provider credential, one retrieval config, and one assistant key with escrowed keys.
- [ ] Copy objects to a disposable prefix/bucket; verify each size/hash against the DB.
- [ ] Restore DB only (no objects): confirm content/retrieval works, reprocess fails, `MISSING_OBJECT` is set, and repair path works.
- [ ] Restore objects only (no DB): confirm quarantine, no accidental lifecycle deletion, and no public exposure.
- [ ] Restore a paired DB+object set; reconcile to zero missing; run retrieval smoke tests.
- [ ] Restore PostgreSQL to a point in time within the PITR window (if available); verify the object pair matches or is reconciled.
- [ ] Rebuild Qdrant from restored chunks; verify point counts, tenant filters, and idempotency.
- [ ] Measure and record RTO/RPO for each path.

### 10.5 Lifecycle and privacy

- [ ] Delete a synthetic tenant: confirm zero DB rows, zero objects (all versions), zero Qdrant points, zero traces; issue a deletion record.
- [ ] Confirm backups retain the deleted tenant until expiry and document the residual window.
- [ ] Confirm retention/pruning removes expired backups/objects/inventories and retains the required audit evidence.
- [ ] Confirm `backups/` and any dump/archive cannot be committed (`.gitignore`, pre-commit check).

### 10.6 Evidence to retain

For every item: timestamp (UTC), environment, bucket/prefix, command or API call, result, counts, SHA-256/ETag, operator, and any deviation. Store outside the repository with the backup/restore record.

---

## 11. NOT RUN Register and Exit Criteria

### 11.1 NOT RUN in this stage

| Item | Reason | Next execution gate |
|---|---|---|
| `backup-postgres.ps1` | No execution; requires DB credentials and `pg_dump` | P0-2 |
| `backup-storage.ps1` | No execution; local-only and not applicable to S3 staging | P0-1/P0-6 |
| `backup-paired.ps1` | No execution; consistency defect already established statically | P0-2/P0-6 |
| `restore-postgres.ps1` | No execution; destructive by design | P0-6 |
| `restore-storage.ps1` | No execution | P0-6 |
| `verify-backup.ps1` | No execution | P0-2 |
| `drill-live-postgres-backup-restore.sh` | No Docker/live PostgreSQL execution in this stage | P0-6 |
| `drill-live-qdrant-rebuild.sh` | No live Qdrant execution in this stage | P0-6/P1-3 |
| Live S3/MinIO PUT/GET/HEAD/DELETE | No cloud resources or real credentials | P0-1/P0-6 |
| PITR restore | Provider/plan unconfirmed (**TO-VERIFY**) | P0-2 |
| Object-store backup/version restore | No object-store backup exists | P0-1 |
| Key escrow/decrypt-after-restore | No escrow configured | P0-3 |
| Tenant erasure drill | No workflow exists | P1-1 |
| Re-execution of storage pytest suites | Read-only stage; prior evidence cited (E34-E37) | Before release gate |

### 11.2 Exit criteria for Stage 8

| Criterion | Required result |
|---|---|
| Durable backend selected for staging | S3/minio, not local; guard covers `staging` |
| Object backup exists | Versioning + separate backup copy + daily inventory |
| DB backup exists | Automated/PITR or scheduled dump; encrypted; offsite; revision recorded |
| Paired restore verified | Disposable DB + disposable object prefix; zero missing; hashes match |
| Reconciliation operational | Scheduled provider-aware report; missing=P1, orphans triaged |
| Delete correctness | No silent orphans/dangling rows; KB/tenant/Qdrant/trace cleanup |
| Key recovery | Escrow + decrypt test pass; rotation coverage decided |
| Retention/erasure | Policy approved; tenant purge drill passes or is explicitly out of scope for the cohort |
| Evidence | Drill reports, counts, timestamps, and NOT RUN items recorded |

**Stage 8 cannot be marked complete for real documents until every BLOCKER/HIGH row in §8 is closed or explicitly accepted in writing by the product owner with a documented residual risk.**

---

## Appendix A — Key Layout Examples

Given `tenant=11111111-1111-1111-1111-111111111111`, `kb=2222...`, `doc=3333...`, version `1`, filename `Q3 Report.pdf`:

```text
sanitize_filename("Q3 Report.pdf") -> "Q3_Report.pdf"
build_storage_key(...)             -> "tenants/1111.../kbs/2222.../docs/3333.../v1/Q3_Report.pdf"

local effective path               -> "{STORAGE_PATH}/tenants/1111.../kbs/2222.../docs/3333.../v1/Q3_Report.pdf"
S3 effective key                   -> "{bucket}/1111.../tenants/1111.../kbs/2222.../docs/3333.../v1/Q3_Report.pdf"
```

S3 traversal normalisation:

```text
_get_full_key("tenant-A", "/../../etc/passwd") -> "tenant-A/etc/passwd"
```

The tenant prefix is preserved; `..` segments are removed rather than resolved. Both providers still require the caller to pass the authenticated tenant.

## Appendix B — Required Reconciliation and Paired-Manifest Fields

**Reconciliation report (per run, per tenant).**

| Field | Purpose |
|---|---|
| `run_id`, `started_at`, `finished_at`, `tool_version` | Reproducibility |
| `tenant_id`, `document_id`, `version_num` | Scope |
| `key` | Object identity |
| `expected_size`, `expected_sha256` | From `documents`/`document_versions` |
| `actual_size`, `actual_sha256`, `object_version_id`, `last_modified` | From the provider |
| `status` | `MATCH`, `MISSING`, `SIZE_MISMATCH`, `HASH_MISMATCH`, `ORPHAN` |
| `severity`, `action`, `quarantine_until` | Triage |
| `bucket`, `prefix_layout` | Distinguishes the two key layouts |

**Paired backup manifest.**

| Field | Purpose |
|---|---|
| `paired_backup_id` | Stable identifier |
| `db_dump_sha256`, `db_size_bytes`, `alembic_revision` | DB artifact identity and schema |
| `db_snapshot_id` / LSN / backup timestamp | Recovery point |
| `bucket`, `prefixes`, `inventory_uri`, `inventory_created_at` | Object-set identity |
| `object_count`, `total_bytes`, `per_tenant_counts` | Expected object set |
| `key_fingerprint` | Encryption-key recovery check |
| `tool_version`, `verified_at`, `verification_result` | Evidence |

## Appendix C — Cross-References

- **M11 Stage 5 — Background Ingestion and Worker Reliability:** job claim/lease gaps, `QUEUED` stranding, restart recovery, and the worker-profile race. Stage 8 does not re-litigate those; it records their effect on restore completeness.
- **M11 Stage 7 — Security and Private Testing Readiness:** no tenant deletion endpoint, open registration, and missing account lifecycle controls.
- **M10 Remediation Stage 3 — STOR-1:** fail-closed storage validation and S3 traversal fixes; residual "live S3/MinIO round-trip remains untested" (`M10_REMEDIATION_STAGE_3_STORAGE.md:60-64`).
- **M10 Git Stage 3 Security Review:** prior hermetic test pass for storage/recovery (`M10_GIT_STAGE_3_SECURITY_REVIEW.md:43-45`).
- **M05 file recovery tests:** local paired backup/restore, reconciliation, tenant isolation, zip-slip (`backend/tests/test_m05_file_recovery.py`).
- **Runbook:** `docs/runbooks/backup-and-recovery.md` — requires correction per §4.9.

---

## 12. Report-Back Summary

### 12.1 Top gaps

1. **No S3 backup path.** Staging uses S3; all backup/restore and reconciliation code is local-filesystem only. There is no versioning, lifecycle, inventory, replication, or restore procedure for the bucket.
2. **No consistent DB+object pair.** `backup-paired.ps1` dumps the DB and archives files sequentially with no freeze, snapshot ID, LSN, or object inventory. Concurrent deletes can produce a DB restore that references missing objects.
3. **Delete is unsafe and silent.** Object-first deletion, a bare `except: pass`, late DB commit, no KB cleanup, no Qdrant purge, and no trace purge. A 204 does not prove deletion.
4. **No tenant erasure/retention.** DB, objects (all versions), Qdrant, traces, and backups cannot be purged together; there is no retention schedule or deletion certificate.
5. **Key recovery is incomplete.** `SECRET_ENCRYPTION_KEY` is generated into Render with no escrow; rotation covers only `RetrievalConfig`, not provider credentials or assistant keys.
6. **Durability is untested live.** S3 is mocked in tests, storage is absent from readiness, `exists()` masks errors, and the staging guard does not reject local storage.
7. **Object-loss self-healing is blocked.** Duplicate detection prevents a re-upload from restoring a missing object; there is no `MISSING_OBJECT` state or repair path.
8. **Operational docs are inaccurate.** The runbook's commands/artifact names do not match the scripts, and it claims "IMPLEMENTED AND AUDITED" for a manual, local-only, never-run backup path.

### 12.2 Is durable storage staging-ready?

**No.** The S3 adapter is production-shaped enough to deploy, but durable storage in the operational sense — recoverable, reconcilable, deletable, and restorable — is not staging-ready. It is **conditionally usable for synthetic documents only** after P0-1 through P0-6 are complete; real documents should remain blocked until P0-7/P0-8 and the live checklist pass.

### 12.3 What must be validated live before real documents are uploaded

At minimum: real S3 PUT/GET/HEAD/DELETE with versioning and lifecycle; tenant A/B isolation and traversal attempts; 50 MiB and 10-file boundaries plus 255/256-character filenames; duplicate/repair behaviour; delete under storage failure; DB-only and object-only restores; a paired DB+object restore with reconciliation and Qdrant rebuild; PITR restore if the provider supports it; key escrow/decrypt after restore; and a synthetic tenant-erasure drill. All evidence must be retained before the first customer document is accepted.

### 12.4 Change statement

No source code, configuration, cloud resource, bucket, database, backup, upload, or git state was changed. The only write is this document.
