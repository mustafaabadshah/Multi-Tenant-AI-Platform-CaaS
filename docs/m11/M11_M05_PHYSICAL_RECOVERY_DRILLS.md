# M11 Stage 6 — M05 Physical Recovery Drills

**Milestone:** M11 — Production Hardening / Stage 6
**Date:** 2026-11-12
**Environment:** Windows PowerShell 5.1, Docker Desktop (Linux containers), backend venv `backend\.venv`, PostgreSQL image `pgvector/pgvector:pg16` (already present locally)
**Scope:** Disposable local resources only. No git mutations, no cloud, no installs, no image pulls, no changes to pre-existing containers/volumes.

**Verdict summary**

| Drill | Verdict |
|---|---|
| 1 — PostgreSQL kill/restart + lease recovery | `PASS` |
| 2 — MinIO kill/restart | `DEFERRED — NOT RUN (no local image)` |
| 3 — Dependency partition/outage (`docker pause`) | `PASS` |
| 4 — Multi-version Alembic downgrade on PostgreSQL | `PASS` |

`M05_PHYSICAL_RECOVERY_DRILLS = PARTIAL — 3/4 EXECUTED, 3/3 EXECUTED PASSED, MINIO DRILL DEFERRED`

---

## 0. Asset inspection and method

Inspected before execution:

- `backend/app/commands/drill_postgres_recovery.py` — historical M05 seed/verify helper (disposable DB name guards, seed in source, verify restored DB with in-memory BYOK decryption).
- `backend/app/commands/drill_qdrant_rebuild.py` — Qdrant rebuild helper (not applicable to these four drills).
- `docker-compose.m05-postgres.yml`, `docker-compose.m05-qdrant.yml` — isolated M05 test environments bound to `127.0.0.1:55432` / `:6333`.
- `docs/runbooks/backup-and-recovery.md` — PostgreSQL backup/restore, storage backup, Qdrant rebuild, encryption-key recovery.
- `docs/m10/M10_FINAL_RELIABILITY_AUDIT.md` §5 — historical drill inventory (all four `DEFERRED — NOT RUN`).
- `docs/m11/M11_STAGE_5_BACKGROUND_JOB_RELIABILITY.md` — lease/claim recovery semantics later implemented in `backend/app/services/ingestion/job_queue.py` (`recover_stale_jobs`, `INGESTION_LEASE_SECONDS=3600`) and invoked from `backend/app/main.py` lifespan.

**Replicated logic:** Drill 1/4 reused the *intent* of the M05 helper (dedicated disposable database, synthetic tenant/user/KB/document seed, row-count evidence, strict disposable-only guard). The historical Python helper was **not executed** because it targets the old `m05_integration` / `m05_restore_drill_disposable` databases on port 55432 and its seed SQL is stale relative to the current schema (see §6, D4). Drill-local SQL and Alembic commands were used instead. No production or staging database, container, volume, image, or credential was touched.

---

## 1. Preconditions

- Docker Desktop running; `pgvector/pgvector:pg16` present locally (no pull performed).
- Ports `127.0.0.1:55434` (PostgreSQL) and `127.0.0.1:8016` (temporary API) free.
- Backend venv present (`backend\.venv`); Alembic 1.20.1, SQLAlchemy 2.1.8, Python 3.12.3.
- Baseline Docker state before work: only `meta-graph-redis` and `meta-graph-neo4j` running; three `meta-graph-codebase-navigator_*` volumes. `minio/minio` absent from `docker images`.
- Disposable local-only PostgreSQL password used and redacted below as `<DRILL_PG_PASSWORD>`.

---

## 2. Drill 1 — PostgreSQL service kill/restart and stale-lease recovery

### 2.1 Commands

```powershell
docker run -d --name m11-m05-drill-pg --label m11-m05-drill=true `
  -e POSTGRES_DB=m11_drill -e POSTGRES_USER=m11_drill -e POSTGRES_PASSWORD=<DRILL_PG_PASSWORD> `
  -p 127.0.0.1:55434:5432 --memory 512m pgvector/pgvector:pg16
# exit 0 -> e66b327ccc01

# readiness loop
docker exec m11-m05-drill-pg pg_isready -U m11_drill -d m11_drill   # ready after 2s

$env:DATABASE_URL      = "postgresql+asyncpg://m11_drill:<DRILL_PG_PASSWORD>@127.0.0.1:55434/m11_drill"
$env:DATABASE_SYNC_URL = "postgresql://m11_drill:<DRILL_PG_PASSWORD>@127.0.0.1:55434/m11_drill"
backend\.venv\Scripts\alembic.exe upgrade head   # exit 0
backend\.venv\Scripts\alembic.exe current        # 0010_m10_remediation_schema_alignment (head)
```

Synthetic seed (disposable IDs):

| Row | ID | State |
|---|---|---|
| tenant | `11111111-1111-4111-8111-111111111111` | `m11-drill-tenant` |
| user | `22222222-2222-4222-8222-222222222222` | `m11-drill@example.invalid` |
| knowledge base | `33333333-3333-4333-8333-333333333333` | `M11 Drill KB` |
| target document | `44444444-4444-4444-8444-444444444444` | `PROCESSING` (locked) |
| control document | `55555555-5555-4555-8555-555555555555` | `COMPLETED`, `total_chunks=1` |
| document versions | `6666...`, `8888...` | v1 for each document |
| stuck ingestion job | `77777777-7777-4777-8777-777777777777` | `PROCESSING`, `started_at = now() - 2h`, `retry_count=1`, `max_retries=3` |

The stuck job was inserted **after** the temporary API reached `/ready`, so the first lifespan sweep could not consume it before the kill/restart cycle.

Temporary API:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8016
# DATABASE_URL -> 127.0.0.1:55434/m11_drill, local temp storage path
```

### 2.2 Expected vs actual

| Step | Expected | Actual |
|---|---|---|
| `GET /ready` at start | 200 | `200`, body `{"status":"ready","database":"connected",...}` |
| `GET /health` | 200 | `200` |
| `docker stop m11-m05-drill-pg` | container stopped, exit 0 | exit 0 after ~1.2s; `Exited (0)` |
| `GET /ready` while PG down | 503, process alive | `503`; uvicorn log shows only the dispatcher claim failure |
| `GET /health` while PG down | 200 (process liveness) | `200` |
| App process after stop | alive | alive (same PID) |
| `docker start` + `pg_isready` | ready | ready immediately; `GET /ready` -> `200` |
| Seeded data after restart | intact | intact (table below) |
| Fresh app process startup recovery | stale job requeued, retry+1, document unlocked | job `QUEUED/RETRY_QUEUED`, `retry_count 1 -> 2`, `started_at NULL`, document `QUEUED` |

Recovery log lines from the fresh process (inline dispatcher disabled so the requeued job was not immediately re-claimed):

```text
[WARNING] mmaip.job_queue: Lease recovery complete: requeued=1 failed=0 lease_seconds=3600
[WARNING] mmaip.recovery: Startup recovery complete: recovered 1 orphaned ingestion jobs and 0 orphaned embedding jobs.
[Lifespan] Recovered orphaned background jobs: {'recovered_ingestion_jobs': 1, 'recovered_embedding_jobs': 0}
```

Job state evidence:

```text
77777777-... | QUEUED | RETRY_QUEUED | retry_count=2 | max_retries=3
             | started_at=NULL | completed_at=NULL
             | error_category=LEASE_EXPIRED
             | error_message="Processing lease expired. Job requeued for retry."
ingestion_events: 77777777-... | LEASE_EXPIRED | RETRY_QUEUED | "Processing lease expired. Job requeued for retry."
job_metadata.lease_recovery_notes[0]:
  {"event":"LEASE_EXPIRED","lease_seconds":3600,"prior_started_at":"2026-11-12T10:42:33.814409+00:00",
   "retry_count":1,"max_retries":3,"action":"REQUEUED"}
```

### 2.3 Row counts

| Table | Before kill | After PG restart (before app restart) | After startup recovery |
|---|---|---|---|
| tenants | 1 | 1 | 1 |
| users | 1 | 1 | 1 |
| knowledge_bases | 1 | 1 | 1 |
| documents | 2 | 2 | 2 |
| document_versions | 2 | 2 | 2 |
| ingestion_jobs | 1 | 1 | 1 |
| ingestion_events | 0 | 0 | 1 |

No seeded row was lost. The control document remained `COMPLETED` with `total_chunks=1`. The target document changed only by the intended recovery transition `PROCESSING -> QUEUED`.

### 2.4 Verdict

`PASS`

Limitation recorded: `docker stop` is a **graceful SIGTERM** stop (container exited 0), so this drill proves API tolerance of PostgreSQL connection loss and lease-based job recovery; it does not exercise PostgreSQL WAL crash recovery after SIGKILL.

---

## 3. Drill 2 — MinIO kill/restart

```powershell
docker images --filter "reference=minio/minio" --format "{{.Repository}}:{{.Tag}}"
# (no output)
```

`minio/minio` is **not present locally**. Per instruction, no pull was attempted and no MinIO container was created.

**`DRILL_2 = DEFERRED — NOT RUN (no local image)`**

Not exercised: `S3StorageProvider` upload -> container stop -> storage error surfacing -> restart -> object persistence/download. This remains open evidence for the S3/MinIO failure path.

---

## 4. Drill 3 — Dependency partition/outage (`docker pause`)

Performed while the temporary API and PostgreSQL were both running.

| Step | Expected | Actual |
|---|---|---|
| `docker pause m11-m05-drill-pg` | exit 0 | exit 0 |
| `GET /ready` | 503, no crash | `503` at ~5.36s client-observed |
| `GET /api/v1/public/assistants/nonexistent-public-id` | 503/5xx, sanitized | `500` at ~3.35s; body exactly `Internal Server Error` (21 bytes, `text/plain`), no traceback, no URL/credential |
| `GET /health` | 200 | `200` |
| App process | alive | alive |
| `docker unpause` + `GET /ready` | 200, data intact | `200`; row counts still 1/1/1/2/2/1 |

Sanitized error evidence:

```http
HTTP/1.1 500 Internal Server Error
content-length: 21
content-type: text/plain; charset=utf-8

Internal Server Error
```

This simulates a dependency partition for a **host-run API** (the API process is not in the same Docker network namespace; `docker pause` freezes the PostgreSQL process, so connections fail/time out). It is not a full container-to-container network partition (no iptables/tc/toxiproxy) and does not test DNS or routing failures.

### Verdict

`PASS`

Minor observations: the DB-dependent read endpoint surfaced a generic `500` rather than a dependency-specific `503`, and `/ready` took longer than its internal 3s bound at the client (~5.36s), while still returning `503`. Both were sanitized and crash-free; not fixed.

---

## 5. Drill 4 — Multi-version Alembic downgrade/upgrade on PostgreSQL

Fresh database `m11_drill_mig` in the same disposable container. No other database was targeted.

### 5.1 Commands and exit codes

```powershell
docker exec ... psql -U m11_drill -d postgres -c "CREATE DATABASE m11_drill_mig;"
# exit 0

$env:DATABASE_URL      = "postgresql+asyncpg://m11_drill:<DRILL_PG_PASSWORD>@127.0.0.1:55434/m11_drill_mig"
$env:DATABASE_SYNC_URL = "postgresql://m11_drill:<DRILL_PG_PASSWORD>@127.0.0.1:55434/m11_drill_mig"

alembic upgrade head                                       # exit 0 -> 0010
alembic current                                            # 0010_m10_remediation_schema_alignment (head)
alembic downgrade 0008_assistant_publishing_and_api_keys    # exit 0 -> 0008
alembic current                                            # 0008_assistant_publishing_and_api_keys
alembic upgrade head                                       # exit 0 -> 0010
alembic current                                            # 0010_m10_remediation_schema_alignment (head)
```

### 5.2 Seeds (0010 state)

| Object | Count / value |
|---|---|
| `tenants` / `users` / `assistants` / `assistant_publications` | 1 each |
| `api_keys` (surviving 0008 table) | 1 |
| `public_chat_sessions` (surviving 0008 table) | 1 |
| `tenant_quotas` (surviving table) | 1 |
| `invitations` (0010-only table) | 1 |
| `tenant_quotas.daily_request_limit` | column absent at 0010 (dropped by 0010) |
| Nine 0010 tables | all present |

### 5.3 Expected vs actual

| Check | Expected after `downgrade 0008` | Actual |
|---|---|---|
| `alembic current` | `0008_assistant_publishing_and_api_keys` | matched |
| Nine 0010 tables | dropped | all `MISSING` (`provider_connections`, `embedding_configs`, `vector_store_configs`, `resource_permissions`, `usage_records`, `assistant_prompts`, `invitations`, `assistant_memberships`, `message_attachments`) |
| `daily_request_limit` | restored, default 1000, `NOT NULL` | present, default `1000`, `is_nullable=NO`, existing quota row value `1000` |
| Surviving rows | intact | `api_keys=1`, `public_chat_sessions=1`, `tenant_quotas=1`, `tenants=1`, `users=1`, `assistants=1`, `assistant_publications=1` |
| 0009-added columns | removed at 0008 | `api_keys.assistant_id` and `public_chat_sessions.conversation_id` absent |
| 0010-only data (`invitations`) | lost (table dropped) | table gone; data lost as expected |

| Check | Expected after `upgrade head` | Actual |
|---|---|---|
| `alembic current` | `0010_m10_remediation_schema_alignment` | matched |
| Nine 0010 tables | recreated | all present |
| Surviving rows | intact | all seven surviving objects still 1 |
| `invitations` | table exists, data gone | table exists, `invitations=0` |
| `daily_request_limit` | absent again (0010 parity) | column count `0` |

### 5.4 Verdict

`PASS`

Documented data loss: rows in 0010-only tables (`invitations`) are dropped by the 0010 downgrade and are **not** restored by re-upgrade; this is expected for the forward migration and must be treated as destructive when downgrading a real database.

---

## 6. Defects / observations (documented, not fixed)

| ID | Severity | Observation |
|---|---|---|
| D1 | Minor | During DB outage, `GET /api/v1/public/assistants/{id}` returns generic `500 Internal Server Error` instead of a dependency-specific `503`. Body is sanitized (no traceback, no connection string). |
| D2 | Minor | `/ready` client-observed latency was ~5.36s with PostgreSQL paused, exceeding the internal `asyncio.timeout(3)` budget, though it still returned `503`. |
| D3 | Informational | `docker stop` is graceful (Postgres exit 0). SIGKILL/crash-recovery durability was not exercised; a hard-kill variant remains future work. |
| D4 | Informational | Historical `backend/app/commands/drill_postgres_recovery.py` is stale versus the current schema: it inserts `users.is_active` (current model uses `status`) and omits `tenants.settings` (NOT NULL, no server default). It also hard-codes the old `m05_*` databases on port 55432. It was not executed. |
| D5 | Minor | The in-process ingestion dispatcher logs a full stack trace for each failed claim while PostgreSQL is down. It does not crash the process and exposes no credentials, but the repeated traceback is noisy. |

No production code, schema, tests, prompts, or historical reports were changed.

---

## 7. Cleanup confirmation

| Action | Result |
|---|---|
| Temporary API processes stopped | both background uvicorn sessions stopped |
| Drill container removed (`docker rm -f m11-m05-drill-pg`) | exit 0 |
| Anonymous volume created by the `pgvector` image (`docker run` created `7f2e35...`) removed | exit 0 |
| Backend temp storage directory removed | confirmed absent |
| `docker ps -a` | only pre-existing `meta-graph-redis` and `meta-graph-neo4j`, both still `Up` |
| `docker volume ls` | only the three pre-existing `meta-graph-codebase-navigator_*` volumes |
| `docker network ls` | unchanged (defaults + `meta-graph-codebase-navigator_default`) |
| Listeners on 55434 / 8016 | none |
| Images | no pull, no delete (`pgvector/pgvector:pg16` and pre-existing python images retained) |
| Git | no mutations; only this new document added under `docs/m11/` |

---

## 8. Status note

Historical `docs/m10/M10_FINAL_RELIABILITY_AUDIT.md` is unchanged (`M05_PHYSICAL_RECOVERY_DRILLS = DEFERRED — NOT RUN`, `M05_STATUS = CONDITIONAL_PASS`).

The M05 historical status changes **only if all four drills pass** (with at most two not run). Drill 2 was not run because no local `minio/minio` image exists; therefore the four-drill set is not complete and the historical M05 status must not be upgraded. Current physical-recovery evidence is:

```text
DRILL_1_POSTGRES_KILL_RESTART = PASS
DRILL_2_MINIO_KILL_RESTART    = DEFERRED — NOT RUN (no local image)
DRILL_3_DEPENDENCY_PARTITION  = PASS
DRILL_4_ALEMBIC_DOWNGRADE     = PASS
M05_PHYSICAL_RECOVERY_DRILLS  = PARTIAL (3/4 executed, 3/3 executed passed)
```
