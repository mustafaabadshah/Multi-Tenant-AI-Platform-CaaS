# M11 Continuation Regression Evidence

## PART 1 — Backend Verification

### Environment

| Item | Value |
|---|---|
| Timestamp (start) | 2026-11-12T18:31:20+05:00 |
| Timestamp (end) | 2026-11-12T18:38:32+05:00 |
| Host OS | Windows (win32), PowerShell 5.1 |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Git HEAD | `fdb12463a8308d86015cba8d82546faf0f546c8b` (`docs(m10): record final integration audit and release evidence`, 2026-11-12 14:08:24 +0500) |
| Working tree | Dirty: 57 porcelain entries (M11 continuation changes under test; no git mutations performed) |
| Python | 3.12.3 (`backend\.venv\Scripts\python.exe`) |
| pytest | 9.2.0 |
| Ruff | 0.17.4 |
| Database scope | SQLite only for this part; disposable temp DBs under `C:\Users\MUSTAF~1\AppData\Local\Temp\kilo\` |
| Full-suite log | `%TEMP%\kilo\m11_full_pytest.log` (captured by Tee-Object) |

No source edits, installs, cloud calls, or git mutations were performed.

### Command Results

| # | Command | Exit | Result |
|---|---|---|---|
| 1a | `.\.venv\Scripts\python.exe -m compileall -q app tests` | 0 | No output (success) |
| 1b | `.\.venv\Scripts\python.exe -c "from app.main import app; print('import OK')"` | 0 | `import OK` |
| 2 | `.\.venv\Scripts\python.exe -m pytest -q -rs --tb=short` | 0 | **407 passed, 18 skipped, 4 warnings in 283.23s (0:04:43)** |
| 3 | Targeted M11 security suite (8 files, see below) | 0 | **75 passed in 44.25s** |
| 4a | Fresh `alembic upgrade head` (SQLite) | 0 | Chain 0001 → 0010 applied |
| 4b | `alembic current` | 0 | `0010_m10_remediation_schema_alignment (head)` |
| 4c | `alembic heads` | 0 | `0010_m10_remediation_schema_alignment (head)` (single head) |
| 4d | Seeded 0008 → head preservation | 0 | **PASS** |
| 5 | `.\.venv\Scripts\python.exe -m pip check` | 0 | `No broken requirements found.` |
| 6a | `ruff check` on 36 changed/untracked backend Python files | 0 | `All checks passed!` |
| 6b | `ruff check .` (global) | 1 | `Found 30 errors.` (`[*] 30 fixable with --fix.`) — historical debt, not fixed |

### Full Backend Suite Totals

Final summary line (verbatim):

```
407 passed, 18 skipped, 4 warnings in 283.23s (0:04:43)
```

Exit code: 0. No failures, no errors. Total collected: 425 (407 passed + 18 skipped).

Warnings (4):
- 1 × `StarletteDeprecationWarning`: `fastapi\testclient.py:1` — using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
- 3 × `UserWarning` from `qdrant_client\async_qdrant_remote.py:236`: failed to obtain server version; unable to check client-server compatibility.

### Skip Inventory (18 total: 12 PostgreSQL-gated + 5 Qdrant-gated + 1 RAM-gated)

Classification confirms the expected total of 18.

#### PostgreSQL-gated — 12

Reason (all 12, verbatim):
```
Live PostgreSQL 16 instance is NOT reachable at postgresql+asyncpg://m05_test:m05_test_password_secure_local@127.0.0.1:55432/m05_integration. To execute: start the isolated M05 container with `docker compose -f docker-compose.m05-postgres.yml up -d`.
```

| # | Test node ID | Origin line |
|---|---|---|
| 1 | `tests/integration/test_pgvector_operations.py::test_real_pgvector_insert_and_cosine_distance_ranking` | 13 |
| 2 | `tests/integration/test_pgvector_operations.py::test_pgvector_rejects_dimension_mismatch` | 103 |
| 3 | `tests/integration/test_postgres_connection.py::test_postgres_version_is_16` | 8 |
| 4 | `tests/integration/test_postgres_connection.py::test_pgvector_extension_loaded_and_functional` | 22 |
| 5 | `tests/integration/test_postgres_connection.py::test_transaction_rollback_and_commit_behavior` | 43 |
| 6 | `tests/integration/test_postgres_fts.py::test_native_postgresql_fts_query_and_ranking` | 13 |
| 7 | `tests/integration/test_postgres_fts.py::test_native_postgresql_fts_sql_injection_safety` | 76 |
| 8 | `tests/integration/test_postgres_migrations.py::test_migration_head_and_schema_tables` | 8 |
| 9 | `tests/integration/test_postgres_migrations.py::test_vector_column_data_type_in_postgresql` | 47 |
| 10 | `tests/integration/test_postgres_migrations.py::test_foreign_key_and_tenant_composite_constraints` | 63 |
| 11 | `tests/integration/test_postgres_tenant_isolation.py::test_cross_tenant_isolation_on_real_postgresql` | 14 |
| 12 | `tests/integration/test_postgres_tenant_isolation.py::test_department_isolation_on_real_postgresql` | 71 |

#### Qdrant-gated — 5

Reason (all 5, verbatim):
```
Live Qdrant vector database is NOT reachable at http://127.0.0.1:6333. To execute: start the isolated M05 Qdrant container with `docker compose -f docker-compose.m05-qdrant.yml up -d`.
```

| # | Test node ID | Origin line |
|---|---|---|
| 13 | `tests/integration/test_qdrant_live_integration.py::test_qdrant_service_connectivity_and_health` | 62 |
| 14 | `tests/integration/test_qdrant_live_integration.py::test_qdrant_collection_creation_and_dimension_isolation` | 72 |
| 15 | `tests/integration/test_qdrant_live_integration.py::test_qdrant_upsert_and_filtered_search` | 105 |
| 16 | `tests/integration/test_qdrant_live_integration.py::test_qdrant_cross_tenant_payload_isolation` | 150 |
| 17 | `tests/integration/test_qdrant_live_integration.py::test_qdrant_scoped_deletion` | 179 |

#### RAM-gated — 1

Reason (verbatim): `Live PostgreSQL container testing skipped: Host available RAM < 2048 MB threshold. Marked as NOT RUN per Phase 7 safety directive.`

| # | Test node ID | Origin line |
|---|---|---|
| 18 | `tests/test_m05_database_recovery.py::test_live_postgres_container_safety_check` | 401 |

Note: the remaining 11 tests in `tests/test_m05_database_recovery.py` passed during the skip-inventory confirmation run (11 passed, 18 skipped in 10.85s).

### Targeted Security / Remediation Confirmation

Command:

```
.\.venv\Scripts\python.exe -m pytest tests/test_m11_registration_policy.py tests/test_m11_invitation_acceptance.py tests/test_m11_public_metadata.py tests/test_m11_embed_allowlist.py tests/test_m11_rate_limiting.py tests/test_m11_job_reliability.py tests/test_m11_storage_consistency.py tests/test_remediation_encryption_key.py -q --tb=short
```

Exact result line:

```
75 passed in 44.25s
```

Exit code: 0. No failures or skips in this targeted set.

### Migration Evidence (Disposable SQLite Only)

Fresh database: `C:/Users/MUSTAF~1/AppData/Local/Temp/kilo/m11_reg_fresh.db` (deleted before run; `DATABASE_URL` overridden via environment for each alembic invocation).

- `alembic upgrade head`: exit 0; applied 0001 → 0002 → 0003 → 0004 → 0005 → 0006 → 0007 → 0008 → 0009 → 0010.
- `alembic current`: `0010_m10_remediation_schema_alignment (head)`.
- `alembic heads`: single head `0010_m10_remediation_schema_alignment`.
- Note: Alembic logs `Will assume non-transactional DDL` for SQLite; expected for this dialect.

Seeded 0008 → head preservation test (second disposable DB `m11_reg_preserve.db`):

1. Deleted DB, `alembic upgrade 0008_assistant_publishing_and_api_keys`: exit 0.
2. Inserted one `api_keys` row (`name=preserved-key`, `key_prefix=mmk_abc`, 64-char hash, `scopes=["assistant:read"]`) and one `public_chat_sessions` row (`session_token=sess-token-preserved`, `user_agent=pytest-agent`).
3. `alembic upgrade head`: exit 0 (0008 → 0009 → 0010).
4. Verified `alembic_version = 0010_m10_remediation_schema_alignment`; both rows preserved with original values; newly added nullable columns `api_keys.assistant_id` and `public_chat_sessions.conversation_id` are `NULL`.

Result: **PASS** (`PRESERVATION_RESULT PASS`).

### Dependency Check

`pip check` exact output:

```
No broken requirements found.
```

Exit code: 0. Lockfiles present in `backend\`:

| File | Size (bytes) |
|---|---|
| `requirements.lock` | 260957 |
| `requirements-dev.lock` | 285240 |

### Ruff

Changed/new backend Python files vs `fdb12463a8308d86015cba8d82546faf0f546c8b` (24 modified tracked + 12 untracked = 36 files):

- `alembic/env.py`
- `alembic/versions/0009_m09_security_and_evaluation.py`
- `app/api/v1/auth.py`
- `app/api/v1/developer.py`
- `app/api/v1/documents.py`
- `app/api/v1/ingestion.py`
- `app/api/v1/knowledge.py`
- `app/api/v1/members.py`
- `app/api/v1/public_chat.py`
- `app/core/config.py`
- `app/main.py`
- `app/schemas/auth.py`
- `app/schemas/member.py`
- `app/services/ingestion/recovery.py`
- `app/services/ingestion/service.py`
- `app/services/ingestion/worker.py`
- `app/services/publishing_service.py`
- `app/storage/base.py`
- `app/storage/local.py`
- `app/storage/s3.py`
- `tests/integration/conftest.py`
- `tests/test_background_recovery.py`
- `tests/test_m10_stage1_security_verification.py`
- `tests/test_m10_stage3_knowledge_and_retrieval.py`
- `app/commands/reconcile_storage.py` (untracked)
- `app/core/rate_limit.py` (untracked)
- `app/services/ingestion/job_queue.py` (untracked)
- `app/services/invitation_service.py` (untracked)
- `app/services/storage_reconciliation.py` (untracked)
- `tests/test_m11_embed_allowlist.py` (untracked)
- `tests/test_m11_invitation_acceptance.py` (untracked)
- `tests/test_m11_job_reliability.py` (untracked)
- `tests/test_m11_public_metadata.py` (untracked)
- `tests/test_m11_rate_limiting.py` (untracked)
- `tests/test_m11_registration_policy.py` (untracked)
- `tests/test_m11_storage_consistency.py` (untracked)

Targeted result: `All checks passed!` (exit 0).

Global `ruff check .`: **30 errors** (exit 1), all reported as fixable. Historical debt only; not modified. Files with counts:

| File | Errors |
|---|---|
| `app/services/ingestion/url_ingestion.py` | 11 |
| `tests/test_m07_knowledge_and_providers.py` | 9 |
| `app/api/v1/providers.py` | 2 |
| `app/api/v1/publishing.py` | 2 |
| `alembic/versions/0004_assistants_and_conversations.py` | 1 |
| `alembic/versions/0006_assistant_versions_and_configuration.py` | 1 |
| `alembic/versions/0007_provider_credentials_and_usage.py` | 1 |
| `alembic/versions/0008_assistant_publishing_and_api_keys.py` | 1 |
| `app/models/assistant.py` | 1 |
| `app/templates/schema.py` | 1 |

Rules involved: I001 (import sorting) and F401 (unused imports). `ruff format` was not run.

### Failures

None in this part. No failed tests, no errors, no broken requirements. The only non-zero exit was global `ruff check .` (30 pre-existing lint findings, expected and intentionally not fixed).

### Limitations

- This part validates the backend on the SQLite unit/integration scope only. It does not exercise live PostgreSQL 16 or live Qdrant behavior; those 17 tests plus the RAM-gated safety check remain NOT RUN pending PART 2 with the isolated containers and sufficient host RAM.
- Migration verification used disposable SQLite databases; PostgreSQL-specific DDL/constraint behavior (pgvector, composite FKs) is covered by the skipped PostgreSQL-gated tests and remains pending PART 2.
- Global Ruff findings are reported as historical debt without remediation in this task; changed/new files are clean.
- Frontend, staging, and live security validation are out of scope for PART 1.

---

## PART 2 — Live PostgreSQL, App Health, Frontend, and SDK Verification

### Environment

| Item | Value |
|---|---|
| Timestamp (start) | 2026-11-12T18:42:55+05:00 (container start) |
| Timestamp (end) | 2026-11-12T18:49:45+05:00 (final cleanup check) |
| Host OS | Windows (win32), PowerShell 5.1 |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Git HEAD | `fdb12463a8308d86015cba8d82546faf0f546c8b` (`docs(m10): record final integration audit and release evidence`, 2026-11-12 14:08:24 +0500) |
| Working tree | 57 porcelain entries before this append; no git mutations performed |
| Python / pytest | 3.12.3 / 9.2.0 |
| Node / npm | v24.14.1 / 11.11.0 |
| Next.js | 16.4.5 (Turbopack) |
| Docker | 25.0.3 (build 4debf41) |
| PostgreSQL container | `m11_p2_pg_55432` from `pgvector/pgvector:pg16` (image `sha256:31c6867f8fd38f4b75885aeb954d43cd4c2be714659d72b0dc4ae55bdcd9e967`), `127.0.0.1:55432`, no volume, `--rm`, `--memory 512m` |
| PostgreSQL server | 16.15 (Debian 16.15-1.pgdg12+2, x86_64) |
| Free host RAM at start | 1001 MB (below the 2048 MB runner threshold; see Notes) |

No source or test edits, installs, cloud calls, or git mutations were performed.

### Command Results

| # | Command | Exit | Result |
|---|---|---|---|
| P2-1 | `docker ps` (preflight) | 0 | Only pre-existing `meta-graph-redis` and `meta-graph-neo4j`; ports 55432/8018 free |
| P2-2 | `docker run -d --rm --name m11_p2_pg_55432 -p 127.0.0.1:55432:5432 ... pgvector/pgvector:pg16` | 0 | Container `8b4a1e525a45`; no volume; fresh DB `m05_integration` |
| P2-3 | `pg_isready` + `SELECT version()` | 0 | `PostgreSQL 16.15 ... x86_64-pc-linux-gnu` |
| P2-4 | `alembic upgrade head` with PG `DATABASE_URL` / `DATABASE_SYNC_URL` | 0 | Applied 0001 → 0010; head `0010_m10_remediation_schema_alignment` |
| P2-5 | `alembic current` / `alembic heads` | 0 / 0 | `0010_m10_remediation_schema_alignment (head)` (both) |
| P2-6 | 12 PostgreSQL-gated tests (5 files) with `M05_POSTGRES_TEST_URL` | 0 | **12 passed in 6.21s** |
| P2-7 | temp `uvicorn app.main:app --host 127.0.0.1 --port 8018` with PG URLs | n/a (started) | `Application startup complete`; inline dispatcher started |
| P2-8 | `GET /health` | 200 | Exact body below |
| P2-9 | `GET /ready` | 200 | Exact body below |
| P2-10 | unauth `GET /api/v1/embedding-providers` | 401 | Exact response below |
| P2-11 | stop temp uvicorn (tracked PID 16740; server PID 12248) | n/a (stopped) | Process stopped; port 8018 closed |
| P2-12 | `docker stop m11_p2_pg_55432` | 0 | Container auto-removed (`--rm`); port 55432 closed |
| P2-13 | `npx tsc --noEmit` (frontend) | 0 | No output |
| P2-14 | `npm run build` (frontend, telemetry disabled) | 0 | Compiled; TypeScript finished; **20/20** static pages |
| P2-15 | `npm run lint` (frontend) | 1 | **122 problems (38 errors, 84 warnings)** — pre-existing debt |
| P2-16 | TypeScript SDK `tsc.cmd --project ..\sdk\typescript\tsconfig.json` | 0 | No output |
| P2-17 | Python SDK `pytest tests/test_sdk_python.py -q --tb=short` | 0 | **2 passed in 0.07s** |

### Live PostgreSQL Gate

Preflight: `docker ps` showed only the two unrelated, pre-existing containers (`meta-graph-redis`, `meta-graph-neo4j`). No port 55432 or 8018 listener existed. The disposable container was started with no mounted volume, so the database was empty.

Alembic command (run from `backend\`):

```
$env:DATABASE_URL="postgresql+asyncpg://m05_test:m05_test_password_secure_local@127.0.0.1:55432/m05_integration"
$env:DATABASE_SYNC_URL="postgresql://m05_test:m05_test_password_secure_local@127.0.0.1:55432/m05_integration"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Exit code: 0. Applied revisions in order: `0001_initial_core_schema` → `0002_document_ingestion_engine` → `0003_embeddings_and_vector_stores` → `0004_assistants_and_conversations` → `0005_add_assistant_byok_encrypted_key` → `0006_assistant_versions_and_configuration` → `0007_provider_credentials_and_usage` → `0008_assistant_publishing_and_api_keys` → `0009_m09_security_and_evaluation` → `0010_m10_remediation_schema_alignment`.

```
Context impl PostgresqlImpl.
Will assume transactional DDL.
...
0010_m10_remediation_schema_alignment (head)   # alembic current
0010_m10_remediation_schema_alignment (head)   # alembic heads
```

Direct DB check: `SELECT version_num FROM alembic_version;` → `0010_m10_remediation_schema_alignment` (exit 0).

Test command (run from `backend\`):

```
$env:M05_POSTGRES_TEST_URL="postgresql+asyncpg://m05_test:m05_test_password_secure_local@127.0.0.1:55432/m05_integration"
.\.venv\Scripts\python.exe -m pytest tests/integration/test_postgres_connection.py tests/integration/test_postgres_migrations.py tests/integration/test_pgvector_operations.py tests/integration/test_postgres_fts.py tests/integration/test_postgres_tenant_isolation.py -v --tb=short
```

All 12 node IDs and results:

| # | Test node ID | Result |
|---|---|---|
| 1 | `tests/integration/test_postgres_connection.py::test_postgres_version_is_16` | PASSED |
| 2 | `tests/integration/test_postgres_connection.py::test_pgvector_extension_loaded_and_functional` | PASSED |
| 3 | `tests/integration/test_postgres_connection.py::test_transaction_rollback_and_commit_behavior` | PASSED |
| 4 | `tests/integration/test_postgres_migrations.py::test_migration_head_and_schema_tables` | PASSED |
| 5 | `tests/integration/test_postgres_migrations.py::test_vector_column_data_type_in_postgresql` | PASSED |
| 6 | `tests/integration/test_postgres_migrations.py::test_foreign_key_and_tenant_composite_constraints` | PASSED |
| 7 | `tests/integration/test_pgvector_operations.py::test_real_pgvector_insert_and_cosine_distance_ranking` | PASSED |
| 8 | `tests/integration/test_pgvector_operations.py::test_pgvector_rejects_dimension_mismatch` | PASSED |
| 9 | `tests/integration/test_postgres_fts.py::test_native_postgresql_fts_query_and_ranking` | PASSED |
| 10 | `tests/integration/test_postgres_fts.py::test_native_postgresql_fts_sql_injection_safety` | PASSED |
| 11 | `tests/integration/test_postgres_tenant_isolation.py::test_cross_tenant_isolation_on_real_postgresql` | PASSED |
| 12 | `tests/integration/test_postgres_tenant_isolation.py::test_department_isolation_on_real_postgresql` | PASSED |

Exact final summary line (verbatim):

```
============================= 12 passed in 6.21s ==============================
```

### Application Health on Live PostgreSQL

The temp app was started from `backend\` on `127.0.0.1:8018` with the same PG `DATABASE_URL` / `DATABASE_SYNC_URL`. Startup completed and the live `/ready` check confirmed database connectivity. The app log recorded `[Lifespan] Inline ingestion dispatcher started (poll=2s, concurrency=1, lease=3600s)` and no `[Startup Warning]` line.

`GET /health` — HTTP 200:

```json
{"status":"healthy","timestamp":"2026-11-12T13:47:39.989376Z","version":"0.1.0"}
```

`GET /ready` — HTTP 200:

```json
{"status":"ready","database":"connected","timestamp":"2026-11-12T13:47:40.073734Z"}
```

### Security Smoke (Unauthenticated)

`GET /api/v1/embedding-providers` without credentials against the live-PG app:

```
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
content-length: 42
content-type: application/json

{"detail":"Authentication token required"}
```

No provider configuration or outbound provider call was made.

### Frontend

| Check | Command | Exit | Observed |
|---|---|---|---|
| Typecheck | `npx tsc --noEmit` | 0 | No diagnostics |
| Build | `$env:NEXT_TELEMETRY_DISABLED=1; npm run build` | 0 | `✓ Compiled successfully in 2.6s`; `Finished TypeScript in 5.1s`; `✓ Generating static pages using 3 workers (20/20) in 2.2s` |
| Lint | `npm run lint` | 1 | `✖ 122 problems (38 errors, 84 warnings)` |

Build route manifest contains 18 distinct paths: `/`, `/_not-found`, `/dashboard`, 11 `/dashboard/*` pages (`assistants`, `audit`, `conversations`, `departments`, `employees`, `groups`, `knowledge`, `observability`, `providers`, `settings`, `workspace`), `/embed/[publicId]`, `/login`, `/p/[publicId]`, `/register`. The console prints 20 rows because `/embed/[publicId]` and `/p/[publicId]` each get an additional `◐` Partial Prerender child line. Static page generation itself reported 20/20.

Lint debt (not fixed): 38 errors and 84 warnings. Errors are dominated by `@typescript-eslint/no-explicit-any` plus two `react-hooks/purity` errors at `app/dashboard/assistants/page.tsx:261` and `:270` (`Date.now()` during render). Warnings are dominated by unused imports/vars and `react-hooks/exhaustive-deps`. This matches the expected pre-existing debt of approximately 122 problems.

### SDK Verification

TypeScript SDK (run from `frontend\`):

```
.\node_modules\.bin\tsc.cmd --project ..\sdk\typescript\tsconfig.json
```

Exit code: 0. No output.

Python SDK (run from `backend\`):

```
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_python.py -q --tb=short
```

Exact result:

```
2 passed in 0.07s
```

Exit code: 0.

### Cleanup Confirmation

- Temp uvicorn background process (tracked PID 16740; uvicorn logged server PID 12248) was stopped via the process manager; port 8018 no longer listening.
- `docker stop m11_p2_pg_55432` exit 0; container created with `--rm`, so it was removed automatically. `docker ps -a` after cleanup lists only the pre-existing `meta-graph-redis` and `meta-graph-neo4j`; no `m11_p2_pg_55432` entry.
- Port 55432 no longer listening.
- `pgvector/pgvector:pg16` image left in place (`IMAGE_PRESENT=True`); no other container was touched.

### Summary — PART 1 + PART 2

| Area | Part 1 | Part 2 | Status |
|---|---|---|---|
| Backend full suite | **407 passed, 18 skipped, 4 warnings in 283.23s**, exit 0 | Not re-run (same HEAD/tree) | PASS (Part 1 evidence) |
| PostgreSQL-gated integration | 12 skipped (NOT RUN) | **12 passed in 6.21s**, exit 0 | PASS |
| PostgreSQL Alembic migration | SQLite chain 0001 → 0010 | Live PG chain 0001 → 0010; head `0010_m10_remediation_schema_alignment` | PASS |
| App health on live PostgreSQL | Not run | `/health` 200, `/ready` 200 (`database=connected`) | PASS |
| Frontend TypeScript | Not run | `tsc --noEmit` exit 0 | PASS |
| Frontend production build | Not run | Build exit 0; static pages 20/20 | PASS |
| Frontend lint | Not run | Exit 1; 122 problems (38 errors, 84 warnings) | KNOWN DEBT (unchanged) |
| TypeScript SDK | Not run | `tsc` exit 0 | PASS |
| Python SDK | Not run | **2 passed in 0.07s**, exit 0 | PASS |
| Unauthenticated embedding-provider access | Not run | HTTP 401 `Authentication token required` | PASS |
| Qdrant live integration (5 tests) | 5 skipped | NOT RUN | NOT RUN |
| S3/R2 live storage | Not run | NOT RUN | NOT RUN |
| MinIO backup/restore drill | Not run | NOT RUN | NOT RUN |
| Manual UI acceptance | Not run | NOT RUN | NOT RUN |

Combined arithmetic: 407 Part 1 passes + 12 live PostgreSQL passes = 419 passing tests; of the original 18 skips, 12 are now closed and 6 remain (5 Qdrant-gated + 1 RAM-gated). Zero failures in either part.

### NOT RUN (Explicit)

- Qdrant live integration tests (5) — no Qdrant container was started in Part 2.
- S3/R2 live object-storage verification — not exercised.
- MinIO backup/restore drill — not exercised.
- Manual UI acceptance — not exercised.
- `tests/test_m05_database_recovery.py::test_live_postgres_container_safety_check` — not run; it is the RAM-gated safety check, not one of the 12 PG tests. Free RAM at Part 2 start was 1001 MB (< 2048 MB), and the runner script was not invoked.
- The backend full suite was not re-run in Part 2; the Part 1 result above is the observed full-suite baseline.

### Notes and Observations

- Host free physical RAM was 1001 MB at Part 2 start, below the 2048 MB threshold enforced by `infrastructure\scripts\run-live-integration-tests.ps1`. To execute the gate without touching unrelated containers, the 12 tests were run directly with `M05_POSTGRES_TEST_URL` against one disposable, 512 MB-bounded container, which was stopped immediately after the app checks. This is a recorded deviation from the runner script, not an unreported override.
- The app's lifespan ran `Base.metadata.create_all`, system-role seeding, and job recovery against the disposable PG database. These operations are idempotent after migration 0010 and did not fail; startup warning output was absent.
- Alembic's stderr logging caused PowerShell to emit a `NativeCommandError` record during the `upgrade head` pipeline; the process exit code was 0 and all ten revisions applied.
- The only non-zero exit in Part 2 is `npm run lint` (exit 1), which is the expected pre-existing frontend debt. No source, test, or configuration files were modified; this document section is the only authored change from Part 2 (Next.js build output and pytest cache are generated artifacts).

### Failures

None in backend, live PostgreSQL, app health, frontend typecheck/build, or either SDK. The single non-zero exit is `npm run lint` with 122 pre-existing problems, intentionally left unfixed.