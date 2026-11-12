# M11 — Durable Background Job Claim, Lease, and Dispatch

**Date:** 2026-11-12

**Scope:** Ingestion job reliability only (`IngestionJob`). Embedding jobs keep their existing fail-on-restart behavior.

**Migration status:** None. The design uses existing columns only (`status`, `started_at`, `completed_at`, `retry_count`, `max_retries`, `job_metadata`). No schema change, no `0011` migration.

**Verdict:** `READY_FOR_SINGLE_PROCESS_PRIVATE_STAGING`

The default deployment shape is one API OS process with the in-process dispatcher enabled and `INGESTION_MAX_CONCURRENCY=1`. A standalone worker is also safe against duplicate execution because claims are atomic, but it remains conditional on sizing `INGESTION_LEASE_SECONDS` above the longest job (there is no heartbeat).

---

## 1. Evidence

Paths are relative to `E:\MM Office\Multi-Tanant-CaaS`.

| # | Change | Evidence |
|---|---|---|
| 1 | Atomic single-job claim via conditional UPDATE | `backend/app/services/ingestion/job_queue.py:55` |
| 2 | Queue-head claim with `SKIP LOCKED` on PostgreSQL and retry-selection loop on SQLite | `backend/app/services/ingestion/job_queue.py:75` |
| 3 | Lease recovery: requeue while retry budget remains, else FAILED / `LEASE_EXPIRED` | `backend/app/services/ingestion/job_queue.py:137` |
| 4 | Sanitized, length-capped error text | `backend/app/services/ingestion/job_queue.py:41` |
| 5 | Bounded in-process dispatcher with stop event | `backend/app/services/ingestion/job_queue.py:367` |
| 6 | Dispatcher failure safety net | `backend/app/services/ingestion/job_queue.py:299` |
| 7 | `execute_job` claim guard and `claimed=True` hand-off | `backend/app/services/ingestion/service.py:268` |
| 8 | Failure rollback and retry/terminal state handling | `backend/app/services/ingestion/service.py:204` |
| 9 | Cancellation checkpoint and conditional terminal update | `backend/app/services/ingestion/service.py:601` |
| 10 | Worker claims atomically and runs startup lease recovery | `backend/app/services/ingestion/worker.py:59`, `:40` |
| 11 | Lifespan lease sweep and dispatcher start/drain | `backend/app/main.py:51`, `:61`, `:88` |
| 12 | Four new settings | `backend/app/core/config.py:78-85` |
| 13 | Settings documented in both env templates | `.env.example`, `.env.production.example` |
| 14 | Existing recovery delegates ingestion to lease recovery | `backend/app/services/ingestion/recovery.py` |
| 15 | Upload / retry / reprocess tasks still dispatch through the guarded `execute_job` | `backend/app/api/v1/knowledge.py:291`, `backend/app/api/v1/documents.py:150`, `:280`, `backend/app/api/v1/ingestion.py:100` |
| 16 | Retry clears lease timestamps; cancel unlocks QUEUED documents too | `backend/app/api/v1/ingestion.py` |
| 17 | New regression suite | `backend/tests/test_m11_job_reliability.py` |

---

## 2. Design

### 2.1 Claim atomicity

`claim_job(session, job_id)` executes:

```sql
UPDATE ingestion_jobs
SET status = 'PROCESSING', started_at = <UTC now>
WHERE id = :id AND status = 'QUEUED';
```

It commits and returns `True` only when `rowcount == 1`; otherwise it rolls back and returns `False`. No path processes a job whose claim did not win.

`claim_next_job(session)`:

1. PostgreSQL: `SELECT id ... WHERE status='QUEUED' ORDER BY created_at, id LIMIT 1 FOR UPDATE SKIP LOCKED`, then the same conditional UPDATE in the same transaction. A second claimer skips the locked row.
2. SQLite: plain ordered `SELECT`, then the conditional UPDATE. If another writer won, `rowcount == 0`; the function rolls back and retries the selection (bounded to 10 attempts). It never returns a job it did not flip.

The API path (`asyncio.create_task(run_ingestion_in_background(...))`) and the dispatcher/worker all pass through this claim. A duplicate dispatch either loses the claim or observes `PROCESSING` without a claim hand-off and returns without work.

### 2.2 Execution ownership hand-off

`IngestionService.execute_job(job_id, claimed=False)`:

| Loaded job status | Behavior |
|---|---|
| `QUEUED` | Attempt `claim_job`. On success, continue. On failure, re-read and return without processing. |
| `PROCESSING` + `claimed=True` | Continue; the dispatcher/worker already claimed it in a previous transaction/session. |
| `PROCESSING` + `claimed=False` | Return without processing; another runner owns it. |
| `COMPLETED` / `FAILED` | Return idempotently. |
| `CANCELLED` | Return idempotently and ensure the document is not left locked. |
| `PENDING` / unknown | Return without processing; only `QUEUED` is claimable. |

After the claim, the service performs a conditional `PROCESSING -> PARSING` transition and commits the document into `PROCESSING`. Completion is a conditional terminal UPDATE:

```sql
UPDATE ingestion_jobs
SET status='COMPLETED', ...
WHERE id=:id AND status='PROCESSING';
```

If a concurrent cancellation already changed the row, `rowcount == 0`; the service rolls back its uncommitted chunks/embeddings and settles the document according to the observed terminal job state instead of overwriting `CANCELLED`.

### 2.3 Lease semantics

- `started_at` is the lease timestamp. It is set at claim time, cleared when a job is requeued, and never refreshed (no heartbeat).
- `recover_stale_jobs(session, lease_seconds)` selects `PROCESSING` jobs where `started_at IS NULL OR started_at < now - lease_seconds`.
  - `started_at IS NULL` is treated as stale: every fresh claim writes it, so a null value is a legacy/interrupted row; leaving it `PROCESSING` would lock the document forever.
  - `retry_count < max_retries`: set `QUEUED`, `stage=RETRY_QUEUED`, `progress_pct=10`, `started_at=NULL`, `completed_at=NULL`, `retry_count += 1`, `error_category=LEASE_EXPIRED`, append a bounded `lease_recovery_notes` entry to `job_metadata`, reset the document to `QUEUED`, and insert a `LEASE_EXPIRED` / `RETRY_QUEUED` event.
  - Otherwise: set `FAILED`, `stage=FAILED`, `error_category=LEASE_EXPIRED`, a fixed sanitized message, `completed_at=now`, reset the document to `FAILED`, and insert a `LEASE_EXPIRED` / `FAILED` event.
  - Each mutation is guarded by a conditional UPDATE on `(id, status='PROCESSING', stale)` so concurrent recovery sweeps cannot double-recover a row.
- The document update is tenant-qualified (`id`, `tenant_id`) and skips `DELETED` rows.

**Documented limit:** there is no heartbeat. A live job that runs longer than `INGESTION_LEASE_SECONDS` looks identical to a dead job. If a second recovery sweep/process starts after the lease, it can requeue the job and a second runner can execute it. The default `3600` seconds is intentionally larger than expected private-staging jobs; deployments with longer jobs must raise it. Do not run a periodic sweep while long jobs may exceed the lease.

**Startup trade-off:** because recovery is lease based, a job that crashed shortly before restart is not requeued until the lease expires. This is the cost of not killing a live sibling process's job. For a single-process staging restart, operators may lower `INGESTION_LEASE_SECONDS` (for example `900`) or perform a restart after the lease window.

### 2.4 Recovery integration (changed semantics)

`recover_orphaned_jobs` previously marked **every** `PROCESSING` ingestion job `FAILED` on every startup. That would defeat requeue semantics and could fail a live sister process's job. It now delegates ingestion to `recover_stale_jobs` and keeps the existing fail-on-restart behavior only for `EmbeddingJob` rows (which have no lease/retry model).

This intentional change required updating two pre-existing assertions:

- `backend/tests/test_background_recovery.py`: a stale job with retry budget now expects `QUEUED / RETRY_QUEUED / retry_count=1 / started_at=NULL` and document `QUEUED` instead of `FAILED / INTERRUPTED`.
- `backend/tests/test_m10_stage3_knowledge_and_retrieval.py::test_09...`: same requeue expectation.

### 2.5 Dispatcher behavior

`dispatch_pending_jobs(session_factory, stop_event, poll_seconds, max_concurrency=1)`:

1. Starts `max_concurrency` slot tasks.
2. Each slot claims one job in a fresh session via `claim_next_job`.
3. If a job is claimed, it executes in another fresh session with `execute_job(..., claimed=True)`.
4. If the queue is empty, it waits up to `poll_seconds` or until `stop_event` is set.
5. An unexpected dispatcher-level exception is logged and `_ensure_recoverable` requeues/fails the job if it is still `PROCESSING`.
6. On `stop_event`, slots stop claiming and finish the current job. The lifespan waits up to 30 seconds for a drain, then cancels; any cancelled job stays `PROCESSING` and is handled by the next lease sweep.

The dispatcher only sleeps when the queue is empty, so a burst of jobs is drained without artificial polling delay.

### 2.6 Idempotency

- Claim is the primary idempotency guard: one conditional UPDATE winner executes.
- Terminal job states return immediately on repeated `execute_job` calls.
- The pipeline's existing chunk hashing/versioning and embedding content-hash reuse are unchanged.
- Cancellation is terminal in the database: completion uses a conditional UPDATE and rolls back its uncommitted pipeline work if cancellation already won.
- Retryable failure now also unlocks the document (`QUEUED`) and clears `started_at`, so a requeued job is not left holding a `PROCESSING` document.

---

## 3. Failure-mode matrix

| # | Crash / trigger point | Durable state | Recovery |
|---|---|---|---|
| F1 | Before upload commit | No job row; possibly an orphan temp file | Client retry; no queue state to recover |
| F2 | After upload/QUEUED commit, before claim | Job + document `QUEUED` | Dispatcher/worker claims on the next poll; no special recovery needed |
| F3 | After claim commit, before `PARSING` commit | Job `PROCESSING`, `started_at` set, document `QUEUED` | Lease sweep after lease: requeue (retry budget) or FAILED; document aligned |
| F4 | Mid-pipeline (after `PARSING` commit) | Job `PROCESSING`, document `PROCESSING`; uncommitted chunks/embeddings rolled back | Lease sweep after lease; requeue/terminal as in F3 |
| F5 | During final completion commit | Commit is atomic: `COMPLETED` or rollback to `PROCESSING` | If rolled back, lease sweep; if committed, terminal and idempotent |
| F6 | Concurrent cancel during pipeline | Job `CANCELLED`; pipeline transaction uncommitted | Service checkpoint rolls back and leaves the document `CANCELLED`; completion cannot overwrite cancellation |
| F7 | Duplicate dispatch (API task + dispatcher/worker) | One winner `PROCESSING`; loser sees claim failure or `PROCESSING` without hand-off | Loser returns without reading storage/parsing |
| F8 | Process killed during dispatcher shutdown cancel | Job `PROCESSING` with `started_at` | Next startup lease sweep after lease |
| F9 | Pipeline exception | Rollback, then `QUEUED/RETRY_QUEUED` with `started_at=NULL` and document `QUEUED`, or `FAILED` with document `FAILED` | Dispatcher/worker claims the requeued row on the next poll |
| F10 | Dispatcher-level exception outside `execute_job` | Job may still be `PROCESSING` | `_ensure_recoverable` requeues/fails immediately |
| F11 | Recovery sweep runs while a live job exceeds its lease | Job requeued and possibly processed again | Operational: set lease above max job duration; no heartbeat in this milestone |
| F12 | Two recovery sweeps race | Conditional UPDATE allows one winner; loser skips the row | No double document reset or duplicate recovery event |

---

## 4. Operational notes

- Defaults: inline dispatcher on, poll 2s, lease 3600s, concurrency 1.
- For a single API process, keep `INGESTION_MAX_CONCURRENCY=1` to avoid CPU-heavy parsers competing on the event loop.
- If running the standalone worker, either keep the inline dispatcher enabled (safe, redundant) or disable it to avoid two pollers. Claims remain atomic either way.
- Monitor `PROCESSING` jobs older than the lease and `QUEUED` jobs older than a few poll intervals.
- `job_metadata.lease_recovery_notes` is capped at the last 10 entries.

---

## 5. Residual risks

1. **No heartbeat.** Lease expiry can requeue a live long job. This is the main remaining reliability limitation.
2. **Slow crash recovery.** A recent `PROCESSING` job waits for the lease before recovery.
3. **In-process CPU work.** Parsers run on the API event loop; the dispatcher does not isolate them.
4. **Untracked API tasks.** Upload/retry/reprocess still use `asyncio.create_task`; the claim guard prevents duplicate processing, but a task can be garbage-collected or lost at loop shutdown. The dispatcher recovers `QUEUED` rows, and the lease recovers claimed rows.
5. **Shutdown cancel.** A dispatcher job cancelled after the 30-second drain remains `PROCESSING` until lease recovery.
6. **PostgreSQL lock path is not exercised by the SQLite suite.** The SQLite branch validates the conditional UPDATE/retry logic; `SKIP LOCKED` should be covered by a live PostgreSQL integration run before promoting beyond private staging.
7. **External vector store.** Qdrant writes remain outside the database transaction (pre-existing behavior); a cancelled/failed Qdrant path can leave external points.
8. **No backoff.** Automatic retries are requeued immediately; a persistent failure can consume the retry budget quickly.
9. **SQLite snapshot semantics.** The SQLite test suite may observe a concurrent cancellation later than PostgreSQL because a SQLite read transaction is snapshot-based. PostgreSQL is the source of truth for staging; the terminal conditional UPDATE remains the final guard against overwriting cancellation.
10. **No per-document exclusivity.** The claim is per job. A duplicate upload or reprocess creates a distinct job for the same document, and two different jobs can still run concurrently for that document (pre-existing behavior; the claim/lease work does not add a document lock).
11. **No claim generation token.** If a live job outlives its lease and is requeued, the original and the requeued runner can both execute; the conditional terminal UPDATE keeps the final state consistent, but the work is duplicated. A future heartbeat/claim-token column would close this gap.

---

## 6. Tests and evidence

Exact command:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_m11_job_reliability.py tests/test_background_recovery.py tests/test_ingestion_pipeline.py tests/test_m10_stage3_knowledge_and_retrieval.py -q --tb=short
```

Exact result line:

```text
37 passed, 1 warning in 58.24s
```

Additional checks:

```text
.\.venv\Scripts\python.exe -m compileall -q app   -> exit 0
.\.venv\Scripts\python.exe -m ruff check <changed files> -> All checks passed!
.\.venv\Scripts\python.exe -m pytest tests/test_document_tenant_isolation.py tests/test_ingestion_to_embedding.py -q -> 4 passed
```

New tests cover:

- Exactly one winner for concurrent `claim_job`.
- Concurrent `claim_next_job` claims distinct rows and never returns an unclaimed job.
- Stale requeue vs terminal failure vs fresh `PROCESSING` untouched, including document alignment and metadata notes.
- Concurrent duplicate `execute_job` executes the mocked storage read/pipeline once.
- `PROCESSING` without a claim hand-off is not processed.
- `CANCELLED` job is not claimed or processed and its document is released.
- Dispatcher processes exactly one job and stops on `stop_event` with `claimed=True`.

No real LLM, embedding provider, OCR, or network call is used.

---

## 7. Verdict

`READY_FOR_SINGLE_PROCESS_PRIVATE_STAGING`

Conditions: one API OS process, inline dispatcher enabled, `INGESTION_MAX_CONCURRENCY=1`, and `INGESTION_LEASE_SECONDS` above the longest expected job. The standalone worker path is implemented and claim-safe, but remains `CONDITIONAL` until lease sizing is validated against real job durations and a PostgreSQL `SKIP LOCKED` integration run is performed.
