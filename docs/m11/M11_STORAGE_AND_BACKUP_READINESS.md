# M11 Storage and Backup Readiness — Consistency and Lifecycle Hardening

| Field | Value |
|---|---|
| Milestone | M11 — Production Hardening / Staging Validation |
| Document | Storage consistency, delete ordering, failed-ingestion cleanup, reconciliation |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Date | 2026-11-12 |
| Execution | Local storage and mocked providers only. No S3/MinIO/cloud call, no real upload, no backup/restore, no git mutation. |

---

## 1. Baseline and confirmed gaps

The Stage 8 review (`docs/m11/M11_STAGE_8_STORAGE_AND_BACKUP.md`) established that the storage abstraction itself existed and was tenant-prefixed, but the lifecycle was unsafe. This continuation confirms the same gaps in the working tree before remediation:

| Gap | Evidence (pre-fix) |
|---|---|
| Upload writes the object before any DB row, with no compensation | `backend/app/services/ingestion/service.py` upload path |
| Delete removes the object first, swallows every storage error, and relies on a late request-scoped commit | `backend/app/api/v1/documents.py` delete handler; `backend/app/database/session.py` `get_db` |
| No reconciliation between DB `file_path` values and stored objects | No tenant-scoped, provider-neutral service existed |
| Failed ingestion could retain chunks/embeddings from an interrupted attempt | Terminal failure only updated job/document status |
| Knowledge-base deletion leaves every object behind | `backend/app/api/v1/knowledge.py` still deletes DB rows only (residual, see §6) |

---

## 2. Implemented fixes

### 2.1 Compensating upload

`backend/app/services/ingestion/service.py:94-180`

The upload path now tracks whether the object was stored. If MIME detection or any document/version/job/event write fails, the session is rolled back and the just-stored object is deleted before a sanitized `RuntimeError` is re-raised. A `ValueError` (for example an unsupported format) is re-raised unchanged so the API keeps its existing 400 mapping. If the compensating delete itself fails, the error is logged by type only and the orphan is left for reconciliation.

### 2.2 Delete ordering and error surfacing

`backend/app/api/v1/documents.py:71-141`

The order is now:

1. Tenant/document authorization (unchanged).
2. Delete the object. A storage exception returns HTTP `502` and leaves the DB row untouched. `delete()` returning `False` (object already absent) is treated as success because the desired end state is reached.
3. Delete the DB records and `commit()` explicitly. A DB failure rolls back and returns HTTP `500`.
4. Write the audit event only after the DB deletion commits.

No exception is swallowed. No storage path, credential, or document content is logged; only tenant ID, document ID, and exception class name.

### 2.3 Terminal ingestion failure cleanup

`backend/app/services/ingestion/service.py:282-310` and `backend/app/services/ingestion/job_queue.py:54-106`

When retries are exhausted and the job becomes terminal `FAILED`, the shared `purge_failed_version_artifacts` helper removes:

- `DocumentChunk` rows for the job's `document_version_id` (or unversioned rows when a legacy job has no version ID);
- `ChunkEmbedding` rows for that document/version and for the removed chunk IDs.

The document is marked `FAILED`, its `total_chunks` is recalculated, and the failure event records the number of chunks removed. The same helper runs for lease-expiry terminal failures (`recover_stale_jobs`) and the dispatcher safety net (`_ensure_recoverable`), so partial artifacts do not survive any terminal failure path. Error text is sanitized through the existing `sanitize_error_message`.

### 2.4 Reconciliation service

`backend/app/services/storage_reconciliation.py`

`async def reconcile_storage(session, storage, tenant_id=None, fix=False, delete_orphans=False, batch_size=500)`:

- Resolves one tenant or all tenants (tenant table plus tenants still referenced by documents).
- Reports documents whose `Document.file_path` object is missing through `storage.exists`.
- With `fix=True`, marks those documents `FAILED` and stores a sanitized note under `metadata_json["storage_reconciliation"]`. It never deletes DB rows.
- Lists objects under the tenant prefix through the provider's `list_keys` and reports keys with no DB reference.
- With `fix=True, delete_orphans=True`, deletes only reported orphans under the same tenant prefix. `delete_orphans` without `fix` is a dry run.
- Never performs an unscoped query or delete; report items include the tenant ID.
- `list_keys` is implemented for local filesystem (`backend/app/storage/local.py:90`) and S3 (`backend/app/storage/s3.py:165`). A provider that cannot list raises `NotImplementedError`, which the service reports as `object_listing: unsupported` instead of pretending the tenant is clean.

### 2.5 CLI

`backend/app/commands/reconcile_storage.py`

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.commands.reconcile_storage --dry-run
.\.venv\Scripts\python.exe -m app.commands.reconcile_storage --fix
.\.venv\Scripts\python.exe -m app.commands.reconcile_storage --fix --delete-orphans
.\.venv\Scripts\python.exe -m app.commands.reconcile_storage --dry-run --tenant <tenant-uuid>
```

Dry-run is the default. `--delete-orphans` is ignored with a stderr note unless `--fix` is present. The command prints a JSON report and exits non-zero on an unhandled failure.

---

## 3. Failure-mode table

| Scenario | Before | After | Residual / owner action |
|---|---|---|---|
| Object save fails | No DB rows, error propagates | No DB rows, sanitized failure | None |
| Object saved, DB document/version/job write fails | Orphan object remained | Object is deleted; sanitized error | If compensation delete fails, an orphan remains and reconciliation reports it |
| Object delete fails | Error swallowed; DB row deleted; silent orphan | HTTP 502; DB row intact; error logged | Retry deletion; investigate provider connectivity/permissions |
| Object delete succeeds, DB commit fails | Could report success / late failure | HTTP 500; object is an orphan; DB row remains and now points at missing bytes | Reconciliation reports orphan and marks the document FAILED |
| Ingestion fails terminally | Partial chunks/embeddings could remain | Version chunks and embeddings removed; document/job FAILED | Qdrant points are not purged here (see §6) |
| Process restarts mid-ingestion | Lease recovery requeues or fails the job; no storage check | Existing lease recovery unchanged; run reconciliation after restart | Run `--dry-run` after any restart, then `--fix` if missing objects are reported |
| Orphan object from any cause | No inventory path | Reported by `--dry-run`; deleted only with both `--fix --delete-orphans` | Keep deletion opt-in and tenant-scoped |

---

## 4. Reconciliation procedure

1. Take a normal database backup and storage backup/inventory before the first fix run.
2. Confirm the configured storage backend is reachable (for S3, a live `head_object`/`list_objects_v2` probe). Reconciliation must not be used to diagnose provider credentials.
3. Run a dry run and review the JSON:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m app.commands.reconcile_storage --dry-run
   ```
4. Apply missing-object handling: documents are marked `FAILED` with a reconciliation note; no DB rows or objects are deleted.
   ```powershell
   .\.venv\Scripts\python.exe -m app.commands.reconcile_storage --fix
   ```
5. After reviewing the orphan list, delete orphans only for the intended scope. Prefer one tenant at a time:
   ```powershell
   .\.venv\Scripts\python.exe -m app.commands.reconcile_storage --fix --delete-orphans --tenant <tenant-uuid>
   ```
6. Re-run the dry run. A second run should report no new missing documents or orphans. Fix counters are idempotent for already-marked documents.

Recommended cadence: after every interrupted deployment/restart, after storage incidents, and at least daily in staging. Run orphan deletion only during a maintenance window with a fresh backup.

---

## 5. Test evidence

New file `backend/tests/test_m11_storage_consistency.py` (8 tests, all passing):

1. Upload compensation removes the object when DB creation fails.
2. Delete storage failure keeps the DB row and returns HTTP 502.
3. Delete success removes both the DB row and the object.
4. Terminal ingestion failure removes partial chunks/embeddings and marks the document FAILED.
5. Reconciliation dry run reports missing objects and orphans without changes.
6. Reconciliation fix marks only missing documents FAILED and keeps orphan objects.
7. Orphan deletion requires the explicit flag and preserves referenced objects.
8. Reconciliation is tenant-scoped and cannot mark or delete another tenant's data.

Required regression command and exact result:

```text
cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_m11_storage_consistency.py tests/test_s3_storage.py tests/test_ingestion_pipeline.py tests/test_m10_stage3_knowledge_and_retrieval.py -q --tb=short
37 passed, 1 warning in 65.92s (0:01:05)
```

Compilation: `python -m compileall -q app` → exit 0. Ruff on the changed files → all checks passed.

---

## 6. Remaining gaps and S3-live NOT RUN items

| Item | Status | Required before real documents |
|---|---|---|
| Live S3/MinIO save/get/exists/get_size/delete/list_keys round-trip | NOT RUN | Execute against a disposable staging bucket with tenant A/B prefixes and verify no cross-tenant key access |
| S3 bucket versioning, lifecycle, retention, and object-lock policy | TO-VERIFY | Confirm in the actual staging provider; versioning is required for recovery of overwritten/deleted objects |
| S3 `exists()` masks every exception as missing | NOT FIXED | Harden to distinguish 404 from auth/network failures before running `--fix` in production; currently run a connectivity probe first |
| S3 backup/restore procedure | NOT IMPLEMENTED | Real object-store backup, inventory manifest, restore drill, and checksum verification; local ZIP scripts do not cover S3 |
| Qdrant point cleanup on document delete and terminal ingestion failure | NOT IMPLEMENTED | Purge/rebuild vectors for the affected document/version; current cleanup is DB-only |
| Knowledge-base deletion object cleanup | NOT IMPLEMENTED | Delete/cascade all document objects or run tenant-scoped reconciliation with orphan deletion |
| Multi-version object deletion | NOT APPLICABLE TODAY | Current upload path writes v1 only; if versioning is added, delete every referenced version path |
| Encryption-key escrow for restored objects/credentials | OPEN | Escrow `SECRET_ENCRYPTION_KEY`; document rotation/restore procedure |
| Tenant erasure across DB, objects, vectors, traces, and backups | NOT IMPLEMENTED | GDPR-style purge workflow and retention schedule |
| Duplicate upload after object loss | OPEN | Duplicate detection returns the existing document; the operator must restore the object or reprocess after reconciliation marks the document FAILED |

---

## 7. Verdict

**CONDITIONAL — staging is usable for synthetic documents only.**

Concrete conditions for synthetic-document staging:

1. Use `STORAGE_BACKEND=local` (development/staging) or a disposable S3 bucket; never real user documents.
2. Keep the required regression suite green and run `reconcile_storage --dry-run` after every restart.
3. Do not expose document deletion to a closed cohort until the delete-failure test and 502 behavior are accepted.

Concrete conditions before any real document:

1. Live S3 round-trip and tenant-prefix isolation check pass.
2. Bucket versioning/lifecycle and an S3 backup/inventory/restore drill pass.
3. S3 `exists()` no longer masks auth/network failures; `--fix` runs only after a connectivity probe.
4. Qdrant point cleanup and knowledge-base deletion cleanup are implemented or explicitly accepted with a rebuild procedure.
5. Tenant erasure and encryption-key escrow procedures are documented and drilled.
