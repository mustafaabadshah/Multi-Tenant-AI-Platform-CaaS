# M10 Git Integration — Stage 5 Regression Verification Report

**Phase:** M10 Git Integration
**Stage:** 5 — Regression Verification
**Status:** COMPLETE WITH RECORDED FAIL/PARTIAL/DEBT ITEMS
**Verification scope:** Current working tree; verification only (no git mutations, no source edits, no installs)
**Report timestamp (UTC):** 2026-11-12T08:02:27Z
**Evidence window:** 2026-11-12 ~07:51Z – ~08:03Z
**Git HEAD:** `9479847` on branch `main` (working tree contains the uncommitted M09/M10 changes)

---

## 1. Environment

| Item | Value |
|---|---|
| OS | Microsoft Windows NT 10.0.19045.0 (Windows 10 22H2) |
| Shell | Windows PowerShell 5.1.19041.6456 |
| Backend interpreter | Python 3.12.3 (`backend\.venv`) |
| Node / npm | Node v24.14.1 / npm 11.11.0 |
| Frontend framework | Next.js 16.4.5 (Turbopack) |
| Ruff | 0.17.4 |
| Hardware | CPU-only, 8 GB RAM |
| Database used | SQLite (aiosqlite) only — disposable temp files under `C:\Users\MUSTAF~1\AppData\Local\Temp\kilo\` |
| Live services | No PostgreSQL, no Qdrant, no paid LLM calls, no browser automation, no model downloads |

---

## 2. Command Results

| # | Command (exact) | Result (counts / duration / exit) | Verdict |
|---|---|---|---|
| 1 | `cd backend; .\.venv\Scripts\python.exe -m compileall -q app tests` | exit 0; duration 00:00.466; no output | PASS |
| 2 | `cd backend; .\.venv\Scripts\python.exe -m pytest -q -rs --tb=short` | `335 passed, 18 skipped, 4 warnings in 469.06s (0:07:49)`; exit 0; wrapper wall time 00:08:12.740 | PASS |
| 3a | Changed-file set: 37 modified tracked `backend/**.py` from `git status --porcelain=v1` (`^ M`) + 30 untracked `backend/**.py` from `git ls-files --others --exclude-standard` = **67 files**, incl. `backend/tests/test_remediation_encryption_key.py`; then `python -m ruff check <67 files>` | 1 error (F401); exit 1; duration 00:00.223 | FAIL (see §9.1) |
| 3b | `cd backend; .\.venv\Scripts\python.exe -m ruff check .` | 31 errors (25 × F401, 6 × I001); exit 1; duration 00:00.382 | PARTIAL — expected historical debt (see §9.2) |
| 4a | `cd backend; .\.venv\Scripts\python.exe -m alembic heads` | `0010_m10_remediation_schema_alignment (head)`; exit 0 | PASS |
| 4b | `$env:DATABASE_URL="sqlite+aiosqlite:///C:/Users/MUSTAF~1/AppData/Local/Temp/kilo/m10_stage5_fresh.db"` (deleted first); `alembic upgrade head`; `alembic current` | upgrade exit 0; current = `0010_m10_remediation_schema_alignment (head)`; exit 0; combined duration 00:05.940; DB 1,032,192 bytes | PASS |
| 4c | `$env:DATABASE_URL="sqlite+aiosqlite:///C:/Users/MUSTAF~1/AppData/Local/Temp/kilo/m10_stage5_seeded.db"` (deleted first); `alembic upgrade 0008_assistant_publishing_and_api_keys`; seed 2 `api_keys` + 2 `public_chat_sessions` rows; `alembic upgrade head`; verify; `alembic current` | all five exits 0; `RESULT=PASS`; rows preserved; new columns NULL; current = `0010 (head)`; combined duration 00:07.758 | PASS |
| 5 | `cd backend; .\.venv\Scripts\python.exe -m pip check` | `No broken requirements found.`; exit 0 | PASS |
| 6a | `cd frontend; npx tsc --noEmit` | exit 0; duration 00:07.669 | PASS |
| 6b | `cd frontend; $env:NEXT_TELEMETRY_DISABLED=1; npm run build` | exit 0; duration 00:12.980; `Generating static pages using 3 workers (20/20)`; 18 route entries in route table (16 static `○`, 2 partial-prerender `◐`) | PASS |
| 6c | `cd frontend; npm run lint` | exit 1; `122 problems (38 errors, 84 warnings)`; duration 00:19.445 | PARTIAL — pre-existing debt, intentionally not fixed |
| 7 | `cd frontend; .\node_modules\.bin\tsc.cmd --project ..\sdk\typescript\tsconfig.json` | exit 0; duration 00:00.962 | PASS |
| 8 | `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_sdk_python.py -q --tb=short` | `2 passed in 0.05s`; exit 0; wrapper wall time 00:09.098 | PASS |
| 9 | Temp backend: `$env:DATABASE_URL="sqlite+aiosqlite:///C:/Users/MUSTAF~1/AppData/Local/Temp/kilo/m10_stage5_live.db"; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8011` (pid 9424) | `/health` → HTTP 200; `/ready` → HTTP 200; process stopped after probe; port 8011 not listening afterwards | PASS |
| 10 | Write `docs/m10/M10_GIT_STAGE_5_REGRESSION_REPORT.md` | This document | PASS |

No git mutations were performed. No source file was edited. The only file created inside the repository is this report; the migration DBs and seed/verify helper live under the OS temp directory.

---

## 3. Backend Test Totals and Skip Inventory

Final pytest summary line, verbatim:

```
335 passed, 18 skipped, 4 warnings in 469.06s (0:07:49)
```

Exit code 0. Wrapper-measured wall time **00:08:12.740** (includes interpreter start and output capture).

Warnings (4, non-failing):

- 1 × `StarletteDeprecationWarning`: `Using 'httpx' with 'starlette.testclient' is deprecated; install 'httpx2' instead.`
- 3 × `UserWarning` from `qdrant_client/async_qdrant_remote.py:236`: `Failed to obtain server version. Unable to check client-server compatibility.`
  (raised in `tests/test_assistants_and_rag.py::test_assistant_crud_lifecycle`, `tests/test_m10_stage1_security_verification.py::test_quota_concurrency_in_flight_reservation`, `tests/test_m10_stage3_knowledge_and_retrieval.py::test_13_lexical_retrieval_scoring_and_ranking`)

### 3.1 PostgreSQL-gated skips — 12

Every one of these reports the identical reason:
```
Live PostgreSQL 16 instance is NOT reachable at postgresql+asyncpg://m05_test:m05_test_password_secure_local@127.0.0.1:55432/m05_integration. To execute: start the isolated M05 container with `docker compose -f docker-compose.m05-postgres.yml up -d`.
```

| # | Reported location | Test |
|---|---|---|
| 1 | `tests/integration/test_pgvector_operations.py:13` | `test_real_pgvector_insert_and_cosine_distance_ranking` |
| 2 | `tests/integration/test_pgvector_operations.py:103` | `test_pgvector_rejects_dimension_mismatch` |
| 3 | `tests/integration/test_postgres_connection.py:8` | `test_postgres_version_is_16` |
| 4 | `tests/integration/test_postgres_connection.py:22` | `test_pgvector_extension_loaded_and_functional` |
| 5 | `tests/integration/test_postgres_connection.py:43` | `test_transaction_rollback_and_commit_behavior` |
| 6 | `tests/integration/test_postgres_fts.py:13` | `test_native_postgresql_fts_query_and_ranking` |
| 7 | `tests/integration/test_postgres_fts.py:76` | `test_native_postgresql_fts_sql_injection_safety` |
| 8 | `tests/integration/test_postgres_migrations.py:8` | `test_migration_head_and_schema_tables` |
| 9 | `tests/integration/test_postgres_migrations.py:47` | `test_vector_column_data_type_in_postgresql` |
| 10 | `tests/integration/test_postgres_migrations.py:63` | `test_foreign_key_and_tenant_composite_constraints` |
| 11 | `tests/integration/test_postgres_tenant_isolation.py:14` | `test_cross_tenant_isolation_on_real_postgresql` |
| 12 | `tests/integration/test_postgres_tenant_isolation.py:71` | `test_department_isolation_on_real_postgresql` |

### 3.2 Qdrant-gated skips — 5

Reason (identical for all five):
```
Live Qdrant vector database is NOT reachable at http://127.0.0.1:6333. To execute: start the isolated M05 Qdrant container with `docker compose -f docker-compose.m05-qdrant.yml up -d`.
```

| # | Reported location | Test |
|---|---|---|
| 1 | `tests/integration/test_qdrant_live_integration.py:62` | `test_qdrant_service_connectivity_and_health` |
| 2 | `tests/integration/test_qdrant_live_integration.py:72` | `test_qdrant_collection_creation_and_dimension_isolation` |
| 3 | `tests/integration/test_qdrant_live_integration.py:105` | `test_qdrant_upsert_and_filtered_search` |
| 4 | `tests/integration/test_qdrant_live_integration.py:150` | `test_qdrant_cross_tenant_payload_isolation` |
| 5 | `tests/integration/test_qdrant_live_integration.py:179` | `test_qdrant_scoped_deletion` |

### 3.3 RAM-gated skip — 1

Reason, verbatim:
`Live PostgreSQL container testing skipped: Host available RAM < 2048 MB threshold. Marked as NOT RUN per Phase 7 safety directive.`

| # | Reported location | Test |
|---|---|---|
| 1 | `tests/test_m05_database_recovery.py:401` | `test_live_postgres_container_safety_check` |

### 3.4 Skip confirmation

`12 (PostgreSQL) + 5 (Qdrant) + 1 (RAM-gated) = 18` — **matches the executed suite exactly; no deviation.**

---

## 4. Frontend, SDK, and Dependency Results

### 4.1 Frontend

- `npx tsc --noEmit` → **exit 0**, 00:07.669.
- `npm run build` (`NEXT_TELEMETRY_DISABLED=1`) → **exit 0**, 00:12.980, `20/20` static pages generated; 18 route entries listed:
  `/`, `/_not-found`, `/dashboard`, `/dashboard/assistants`, `/dashboard/audit`, `/dashboard/conversations`, `/dashboard/departments`, `/dashboard/employees`, `/dashboard/groups`, `/dashboard/knowledge`, `/dashboard/observability`, `/dashboard/providers`, `/dashboard/settings`, `/dashboard/workspace`, `/embed/[publicId]` (partial prerender), `/login`, `/p/[publicId]` (partial prerender), `/register`.
- `npm run lint` → **exit 1**, `122 problems (38 errors, 84 warnings)`. Dominant rules: `@typescript-eslint/no-explicit-any` (errors), `@typescript-eslint/no-unused-vars` and `react-hooks/exhaustive-deps` (warnings), plus 2 `react-hooks/purity` errors for `Date.now()` in `app/dashboard/assistants/page.tsx:261` and `:270`. Not fixed (pre-existing debt; fixing is outside this stage's scope).

### 4.2 SDKs

- TypeScript SDK: `.\node_modules\.bin\tsc.cmd --project ..\sdk\typescript\tsconfig.json` → **exit 0**, 00:00.962.
- Python SDK: `pytest tests/test_sdk_python.py -q --tb=short` → **`2 passed in 0.05s`**, exit 0.

### 4.3 Dependencies

- `python -m pip check` output, verbatim: `No broken requirements found.` (exit 0)
- `backend/pyproject.toml` declares: `aioboto3>=12.4.0` (line 38) and `fastembed>=0.3.0` (line 39). Confirmed present.

---

## 5. Migrations

| Check | Result |
|---|---|
| `alembic heads` | Single head: `0010_m10_remediation_schema_alignment (head)` — PASS |
| Fresh base → head (temp SQLite `m10_stage5_fresh.db`) | All 10 revisions applied `0001 … 0010`; exit 0; duration 00:05.940; `alembic current` = `0010_m10_remediation_schema_alignment (head)` — PASS |
| Upgrade `0008_assistant_publishing_and_api_keys` → head with seeded rows (temp SQLite `m10_stage5_seeded.db`) | Seeded 2 `api_keys` + 2 `public_chat_sessions` rows at 0008; upgraded through `0009` and `0010`; exit 0 each; duration 00:07.758 — PASS |

Seeded-row preservation evidence (post-upgrade query output):

```
API_KEY_ROWS=[('0d873997405048f991a7b3dc9821bddd', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1', None), ('e70a223eb54f4effa531c911c08ef8f9', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2', None)]
SESSION_ROWS=[('0b4728ab7f33416d914099036afc826a', 'stage5-session-token-1-36c31dbe49f845128c571e7032e578a1', None), ('d8f8e8195e5044c6854e15385eb04a68', 'stage5-session-token-2-d46829f7021b41e88369fa2d96b23aea', None)]
CHECKS={"api_key_rows_preserved": true, "api_keys_new_column_assistant_id_is_null": true, "session_rows_preserved": true, "sessions_new_column_conversation_id_is_null": true}
RESULT=PASS
```

- Row identities (`id`, `key_hash`, `session_token`) preserved across 0008 → 0009 → 0010.
- New columns `api_keys.assistant_id` (added by 0009) and `public_chat_sessions.conversation_id` (added by 0009) are NULL for the pre-existing rows.

Live-service migration verification flags:

- `LIVE_POSTGRESQL_MIGRATION_VERIFICATION = NOT RUN` (no PostgreSQL instance available; no container started).
- `LIVE_QDRANT_VERIFICATION = NOT RUN` (no Qdrant instance available; no container started).

---

## 6. Live Current-Code Health

Temporary uvicorn instance started from current source on `127.0.0.1:8011` with a disposable SQLite DB (`m10_stage5_live.db`). No interaction with any existing `:8000` or `:3000` process.

| Probe | HTTP status | Body |
|---|---|---|
| `GET /health` | **200** | `{"status":"healthy","timestamp":"2026-11-12T08:02:16.443404Z","version":"0.1.0"}` |
| `GET /ready` | **200** | `{"status":"ready","database":"connected","timestamp":"2026-11-12T08:02:16.508095Z"}` |

Only the started process (background id `bgp_1cec734040015aklMPe6M3Yc44`, pid 9424) was stopped. Afterwards `Get-NetTCPConnection -LocalPort 8011 -State Listen` returned nothing (`PORT_8011_STILL_LISTENING=False`). Evidence: `/health` and `/ready` both 200/200 against the current working tree.

---

## 7. Test Classification (5 buckets)

| Bucket | Count | Detail |
|---|---|---|
| **Passing** | **335** | Full backend suite, exit 0. Includes security, tenant-isolation, migration-adjacent, remediation, SDK, evaluation, observability, and UX tests executed against SQLite. |
| **Failing** | **0** | No failures in the full suite. No failures in `test_sdk_python.py`. |
| **Skipped** | **18** | 12 PostgreSQL-gated + 5 Qdrant-gated + 1 RAM-gated (see §3). |
| **Not run due to missing services** | **17** | The 12 live-PostgreSQL tests and 5 live-Qdrant tests above were not executed because those services are absent. These are the same tests counted in the Skipped bucket — this bucket is a reason classification, not an additional count. |
| **Deferred physical drills** | **4** | M05 physical recovery drills — deferred, not executed, and **not part of the pytest skip count**. See §8. |

`LIVE_POSTGRESQL_MIGRATION_VERIFICATION = NOT RUN`
`LIVE_QDRANT_VERIFICATION = NOT RUN`
`M05_PHYSICAL_RECOVERY_DRILLS = DEFERRED — NOT RUN`

---

## 8. Explicit Separation from M05 Physical Drills

The **18 environment-gated pytest skips are NOT the four M05 physical recovery drills.** The 18 skips are automated tests blocked by absent live services (12 PostgreSQL, 5 Qdrant) plus 1 RAM-threshold guard (`test_live_postgres_container_safety_check`). They are reported by pytest and counted in the suite totals.

The four M05 physical recovery drills are separate operational exercises, documented as: (1) Docker container kill/restart, (2) MinIO kill/restart, (3) network partition, (4) multi-version PostgreSQL downgrade. They require live infrastructure and deliberate destructive action. They were **not attempted** in this stage and are **not represented anywhere in the 18 pytest skips**; the 18 skips are pytest service-availability gates, not drill executions.

Note: earlier M10 stage documents (`M10_STAGE_4_TEST_RESULTS.md`, `M10_STAGE_5_TEST_RESULTS.md`) described the 18 skips as the deferred drills. The executed skip inventory above (12 PostgreSQL + 5 Qdrant + 1 RAM-gated) shows that description conflated two separate items.

`M05_PHYSICAL_RECOVERY_DRILLS = DEFERRED — NOT RUN`

---

## 9. Lint and Format Debt Statements

### 9.1 Backend Ruff — changed-files gate: 1 residual violation (FAIL)

`ruff check` over the 67 changed/added backend Python files → **1 error, exit 1**:

```
app\assistant_runtime\context.py:4:55: F401 `app.assistant_runtime.markdown_normalizer.normalize_markdown` imported but unused
Found 1 error.
[*] 1 fixable with `--fix`.
```

`app/assistant_runtime/context.py` is a **modified tracked file**, not a file newly added by this milestone, so the Stage 5 narrow `ruff check --fix` allowance (added-by-this-milestone files only) does **not** apply. The violation was therefore recorded and left untouched. No `--fix` was run on any file.

### 9.2 Backend Ruff — global residual: 31 errors (PARTIAL, expected historical debt)

`ruff check .` → **31 errors, exit 1** — 25 × `F401` (unused import), 6 × `I001` (unsorted imports). Distribution:

| File | Violations |
|---|---|
| `app/services/ingestion/url_ingestion.py` | 11 |
| `tests/test_m07_knowledge_and_providers.py` | 9 |
| `alembic/versions/0004_assistants_and_conversations.py` | 1 |
| `alembic/versions/0006_assistant_versions_and_configuration.py` | 1 |
| `alembic/versions/0007_provider_credentials_and_usage.py` | 1 |
| `alembic/versions/0008_assistant_publishing_and_api_keys.py` | 1 |
| `app/api/v1/providers.py` | 2 |
| `app/api/v1/publishing.py` | 2 |
| `app/models/assistant.py` | 1 |
| `app/templates/schema.py` | 1 |
| `app/assistant_runtime/context.py` (modified by this milestone) | 1 |

30 of the 31 are in untouched historical files; the remaining 1 is the `context.py` violation in §9.1.

### 9.3 Formatting

- `ruff format --check` was **NOT RUN**.
- `ruff format` was **NOT RUN** and **NOT applied**. No automatic reformatting occurred.

### 9.4 Frontend ESLint debt

`npm run lint` reports **122 problems (38 errors, 84 warnings)**. This is pre-existing lint debt (mostly `no-explicit-any`, unused imports/variables, `exhaustive-deps`, and two `react-hooks/purity` errors in `app/dashboard/assistants/page.tsx`). No lint fixes or reformatting were applied in this stage.

---

## 10. Limitations

- **SQLite-only verification.** All migration and live-health checks ran against disposable SQLite databases. PostgreSQL-specific DDL paths in `0010` (native `ALTER TABLE ... DROP COLUMN`) were not exercised.
- **No live PostgreSQL.** 12 PostgreSQL integration tests skipped; `LIVE_POSTGRESQL_MIGRATION_VERIFICATION = NOT RUN`.
- **No live Qdrant.** 5 Qdrant integration tests skipped; `LIVE_QDRANT_VERIFICATION = NOT RUN`.
- **No visual/browser verification.** No browser automation was used; frontend correctness is limited to TypeScript compilation, production build success, and ESLint output.
- **No paid/LLM network calls, no installs, no model downloads.**
- **RAM guard active.** The one RAM-gated live-PostgreSQL container test remained skipped (`Host available RAM < 2048 MB threshold`).
- **Lint debt not remediated.** Backend ruff residuals (31) and frontend ESLint problems (122) remain; only the changed-files ruff gate was assessed (1 violation, left in place per the narrow-fix constraint).
- **No commit/push/deploy.** This stage produced this report only; the working tree was not mutated.

---

## 11. Fail / Partial / Not-Run Summary

| Item | Status |
|---|---|
| Backend compile | PASS |
| Backend full suite (335 passed / 18 skipped / 0 failed) | PASS |
| Ruff changed-files gate (originally 1 × F401 in `app/assistant_runtime/context.py`) | **PASS (after correction)** — historical: FAIL with 1 × F401; fixed via explicit `__all__` (deliberate re-export); see §12 |
| Ruff global (31 errors in historical/untouched files + 1 changed-file violation) | PARTIAL — expected historical debt |
| Alembic single head | PASS |
| Fresh base → head on SQLite | PASS |
| 0008 → head with seeded rows preserved, new columns NULL | PASS |
| `LIVE_POSTGRESQL_MIGRATION_VERIFICATION` | **NOT RUN** |
| `LIVE_QDRANT_VERIFICATION` | **NOT RUN** |
| `pip check` | PASS |
| `aioboto3` / `fastembed` declared | PASS |
| Frontend `tsc --noEmit` | PASS |
| Frontend production build (20/20 pages) | PASS |
| Frontend ESLint (122 problems: 38 errors / 84 warnings) | PARTIAL — pre-existing debt |
| TypeScript SDK compile | PASS |
| Python SDK tests (2 passed) | PASS |
| Live `/health` + `/ready` on temp `:8011` | PASS (200/200) |
| `M05_PHYSICAL_RECOVERY_DRILLS` | **DEFERRED — NOT RUN** |
| `ruff format --check` / `ruff format` | **NOT RUN / NOT APPLIED** |

---

## 12. Post-verification correction

- The single `F401` reported by the Stage 5 changed-file ruff gate (`app/assistant_runtime/context.py:4:55`, `normalize_markdown` imported but unused) was a **deliberate re-export**: `app/assistant_runtime/runtime.py` imports `normalize_markdown` from `app.assistant_runtime.context`.
- Fixed with an explicit module `__all__` listing the public API (`estimate_tokens`, `sanitize_untrusted_content`, `build_rag_context`, `normalize_markdown`), placed after the imports. No `noqa` directive was used and no other change was made.
- Ruff re-check, `cd backend; .\.venv\Scripts\python.exe -m ruff check app/assistant_runtime/context.py` → `All checks passed!` (exit 0).
- Re-run of the Stage 5 changed-file gate (same list: 37 modified tracked `backend/**.py` + 30 untracked `backend/**.py` = 67 files) → `All checks passed!` (exit 0, 0 errors). The historical FAIL recorded in §9.1 and §11 is retained as the pre-correction record.
- Targeted regression: `pytest tests/test_markdown_normalizer.py tests/test_m05_prompt_injection.py tests/test_m05_provider_reliability.py tests/test_m10_stage2_assistant_lifecycle.py -q --tb=short` → `63 passed in 126.46s (0:02:06)`, exit 0.
- The Stage 5 full-suite result (`335 passed, 18 skipped, 4 warnings in 469.06s`) remains valid: the change is an import-only marker (`__all__`) with no runtime behavior change.