# M10 Final Integration — Stage F: Runtime Reliability & Operational Readiness

**Date:** 2026-11-11
**Scope:** ingestion lifecycle, quotas, tracing, usage, storage, background tasks, DB connections, health endpoints. No redesign performed.

---

## 1. Process-local limitations (verified as still present)

| Mechanism | Implementation | After restart | Two backend instances | Two workers same job | Concurrent quota | Traces on restart | Interrupted ingestion |
|---|---|---|---|---|---|---|---|
| Ingestion jobs | DB-backed job rows (`IngestionJob`/`EmbeddingJob`) + `app/services/ingestion/worker.py` process | Jobs are durable in DB; **startup recovery (`services/ingestion/recovery.py`) marks orphaned PROCESSING jobs FAILED/INTERRUPTED and unlocks documents — it does NOT auto-resume them.** Retry is manual/API-driven. | Each instance runs its own worker; job claiming is not row-locked → **two workers can claim the same job** (no `SELECT ... FOR UPDATE SKIP LOCKED`). | Possible duplicate processing (idempotent chunk hashing mitigates duplicate embeddings; duplicate ingestion events possible). | — | — | Safely retryable via `/retry`; recovery prevents permanent document lock. |
| Quota reservations | In-process lock + in-flight reservation rows + 300s stale cleanup (`quota_service.reserve_quota`) | In-flight reservations orphaned; stale-cleanup reclaims them after 5 min. | **Two instances can both pass the quota check concurrently** (lock is per-process). | — | Race possible across instances; single-instance atomic. | — | — |
| Trace buffer | In-process ring buffer (500/tenant) + JSON-file persistence (`observability/tracer.py`) | Ring buffer (in-memory) is lost; persisted file survives, path is CWD-dependent (`_get_storage_path` heuristic). | Per-instance, no aggregation. | — | — | In-memory view lost on restart; file-based traces retained but location varies with launch dir. | — |
| Usage records | DB rows (`UsageRecord`), written post-stream | Durable. | Durable, shared. | — | — | — | — |
| Storage | local (dev) / S3 (prod adapter) with tenant prefixes | Durable (S3). Local FS is dev-only. | Shared bucket ok. | — | — | — | Upload-then-DB ordering: DB record after object write; on failure the object may be orphaned (no orphan sweep — cosmetic). |

**Verdict:** limitations are **acceptable for a controlled single-instance staging environment**; they must be addressed (job claim locking, cross-instance quota via DB advisory locks/counters, centralized trace store) before multi-instance production.

## 2. Ingestion lifecycle specifics

- Upload → `IngestionJob` (QUEUED) → worker processes → status transitions + `IngestionEvent` audit rows.
- Retry/cancel endpoints sync `Document.status` (QUEUED/CANCELLED) and write audit events (M10 stage 3 changes).
- Startup recovery verified by `tests/test_background_recovery.py` (5 tests pass).
- Worker is a separate compose profile (`profiles: ["workers", ...]`); in default compose the API process handles jobs via FastAPI background tasks (process-local).

## 3. Storage review

| Item | Status |
|---|---|
| Local storage dev-only | VERIFIED — `local.py` writes under `STORAGE_PATH` with tenant subdirectories; compose mounts a named volume. |
| Production storage durable | **PARTIAL** — S3 adapter implemented (lazy `aioboto3`), tenant-prefixed keys, explicit config guard; but `aioboto3` is **not declared in `pyproject.toml`** and `.env.production.example` still sets `STORAGE_BACKEND=local` (Render ephemeral FS). Remediation required before staging. |
| Tenant authorization independent of storage prefixes | VERIFIED — repository/middleware checks happen before storage access; prefix is defense-in-depth. |
| Upload/delete consistency | PARTIAL — deletes remove DB rows + storage object; failure mid-sequence can orphan objects (no sweep job). Acceptable for staging. |
| Backup coverage | PARTIAL — scripts cover Postgres + storage volume; **not executed** in this audit. |
| Restore documentation | VERIFIED — `docs/runbooks/backup-and-recovery.md` + `restore-*.ps1`. |

## 4. Health & readiness

- `/health` (process alive) and `/ready` (DB connectivity) verified live: both 200.
- Compose healthchecks defined for postgres/backend; backend healthcheck hits `/health` only (not `/ready`) — minor.
- Startup: role seeding + orphan-job recovery run inside lifespan with try/except that logs and continues (DB-dependent startup won't hard-crash the app).

## 5. Recovery / chaos drills inventory (separate from the 18 skipped tests)

| # | Drill | Script/plan | Status |
|---|---|---|---|
| 1 | Docker kill/restart | runbooks + compose restart | DEFERRED — NOT RUN |
| 2 | MinIO/S3 kill/restart | (staging infra) | DEFERRED — NOT RUN |
| 3 | Multi-container network partition | runbook (staging) | DEFERRED — NOT RUN |
| 4 | Multi-version PostgreSQL migration downgrade | `commands/drill_postgres_recovery.py`, runbook | DEFERRED — NOT RUN |

---

## Declarations

```text
RELIABILITY_REVIEW = PARTIAL
M05_STATUS = CONDITIONAL_PASS
M05_PHYSICAL_RECOVERY_DRILLS = DEFERRED — NOT RUN
```
Acceptable for controlled staging (single instance); multi-instance hardening (job locks, cross-instance quota, trace store) and the 4 physical drills are required before production.
