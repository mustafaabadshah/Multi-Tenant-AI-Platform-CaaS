# M13.3 Stage 9 - Fresh Validation Results

| Field | Value |
|---|---|
| Milestone | M13.3 - deployment configuration validation (Stage 9) |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Branch | `main` |
| HEAD | `9c27e1b8d3e6aeec00dcf6ddb84cd849b9a607e8` (`9c27e1b`) |
| Date | 2026-11-13 |
| Environment | Windows PowerShell 5.1, backend venv (Python 3.12), Node 24, Docker Desktop |
| Scope | Local and controlled-local validation only. No git mutations, no installs, no external services, no browser, no source edits except this document |
| Verdict | `PASS` for the executed local/controlled scope. Live B2/Neon/Render/Qdrant and manual UI remain `NOT RUN` (see Limitations) |

---

## 1. Pre-check

| Check | Command | Result | Status |
|---|---|---|---|
| Branch | `git branch --show-current` | `main` | PASS |
| HEAD | `git rev-parse HEAD` | `9c27e1b8d3e6aeec00dcf6ddb84cd849b9a607e8` | PASS |
| Working tree count | `git status --porcelain=v2` | 74 entries: 36 tracked modifications (`1 .M`), 0 added/deleted/renamed/unmerged (`2`/`u` = 0), 38 untracked entries; 64 individual untracked files via `git ls-files --others` | INFO |
| Staged diff | `git diff --cached` | Empty | PASS |
| Whitespace | `git diff --check` | Exit 0; no output (CRLF conversion warnings only) | PASS |
| render.yaml SHA-256 | `Get-FileHash -Algorithm SHA256 render.yaml` | `ca4379e9b1034942fa6463d9e4c06c386cea81e7646f6a57b29701b2e0fd641b` | PASS - exact expected hash |
| Blueprint diff: `exec` | `git diff -- render.yaml` | `dockerCommand` contains `... && exec uvicorn app.main:app ...` | PASS |
| Blueprint diff: CORS | Parsed `render.yaml` | `CORS_ORIGIN_REGEX` value is `"^$"`; broad Vercel preview regex disabled | PASS |
| Schema gate | `backend/app/core/config.py:154-156`; `backend/app/main.py:33-35` | `should_initialize_schema()` returns `ENVIRONMENT == "development"`; `Base.metadata.create_all` is inside that gate | PASS |
| Blueprint topology | PyYAML parse | 2 services (`mmaip-backend`, `mmaip-frontend`); no `databases:` block | PASS |

Notes:

- The 36 tracked modifications and 64 untracked files observed at pre-check are the proposed M13.2/M13.3 commit set, not Stage 9 changes. Three sibling-authored docs (`M13_3_B2_CONFIGURATION_AND_VALIDATION.md`, `M13_3_NEON_CONFIGURATION_GUIDE.md`, `M13_3_PRIVATE_STAGING_OPERATOR_RUNBOOK.md`) appeared during validation and are preserved untouched; at completion there are 68 individual untracked files (64 pre-check + 3 sibling docs + this document). This task created only this document.
- `git diff --name-only 9c27e1b...` returns empty because `HEAD == 9c27e1b` (three-dot diff resolves to an empty range). The working-tree comparison `git diff --name-only 9c27e1b -- "backend/*.py"` (32 files) plus untracked backend Python (10 files) was used for Ruff, totaling 42 files.
- The first staging Uvicorn attempt was rejected by CORS hardening because the inherited `FRONTEND_URL` was `http://localhost:3000` under `ENVIRONMENT=staging`. It was retried with HTTPS example origins. This is expected production-like enforcement, not a defect.

---

## 2. Command results

| # | Command | Exit | Result | Duration | Fresh / inherited |
|---|---|---|---|---|---|
| 1 | `cd backend; .\.venv\Scripts\python.exe -m compileall -q app tests` | 0 | No output; all modules compile | 0.9 s (timed rerun) | Fresh |
| 2 | `pytest -q -rs --tb=short` (full backend) | 0 | `568 passed, 18 skipped, 4 warnings in 1063.50s (0:17:43)` | 1063.50 s pytest; 1076.4 s wall | Fresh |
| 3a | `docker run pgvector/pgvector:pg16` on `127.0.0.1:55432` | 0 | Ready; PostgreSQL 16.15; extensions `uuid-ossp`, `pgcrypto`, `vector` loaded | Container ready in a few seconds | Fresh |
| 3b | `alembic upgrade head` on fresh DB | 0 | `0001` -> `0010_m10_remediation_schema_alignment`; `alembic current` = `0010 ... (head)` | 5.9 s | Fresh |
| 3c | `pytest tests/integration -q -rs --tb=short -m postgres_integration` | 0 | `12 passed, 5 deselected in 7.38s` | 7.38 s pytest; 17.7 s wall | Fresh |
| 3d | Temp Uvicorn `127.0.0.1:8023` + `/health`, `/ready` | 0 | `/health` 200 `{"status":"healthy",...}`; `/ready` 200 `{"status":"ready","database":"connected",...}` | n/a (startup + 2 probes) | Fresh |
| 4 | M13.2/M13.3 focused 8-file suite | 0 | `161 passed, 1 warning in 75.65s (0:01:15)` | 75.65 s pytest; 85.1 s wall | Fresh |
| 5a | `pip check` | 0 | `No broken requirements found.` | 2.0 s (timed rerun) | Fresh |
| 5b | `ruff check <42 changed/new backend files>` | 0 | `All checks passed!` | 0.2 s | Fresh |
| 5c | `ruff check .` (backend, global) | 1 | 28 findings in 9 files (historical debt) | 0.3 s | Inherited |
| 6a | `cd frontend; npx tsc --noEmit` | 0 | 0 errors | 9.5 s | Fresh |
| 6b | `NEXT_TELEMETRY_DISABLED=1; npm run build` | 0 | Next.js 16.4.5; compiled successfully; 20/20 static pages; 18 route entries | 16.0 s | Fresh |
| 6c | `npm run lint` | 1 | 122 problems: 38 errors, 84 warnings (identical to M13.2 baseline) | 22.4 s | Inherited |
| 7a | TypeScript SDK `tsc -p sdk/typescript/tsconfig.json --noEmit` | 0 | 0 errors (frontend-local TypeScript 5.9.3; no install) | 1.0 s | Fresh |
| 7b | `pytest tests/test_sdk_python.py -q --tb=short` | 0 | `2 passed in 0.09s` | 0.09 s pytest; 24.1 s wall | Fresh |
| 8 | PyYAML/shlex/env/secret/artifact validation script | 0 | All assertions pass; 103 pattern hits (0 real secrets) | 0.67 s | Fresh |

---

## 3. Backend regression

Exact summary:

```text
568 passed, 18 skipped, 4 warnings in 1063.50s (0:17:43)
```

Skip inventory (actual, 18 total):

| Dependency | Count | Tests |
|---|---|---|
| Live PostgreSQL 16 | 12 | `test_pgvector_operations.py` 2, `test_postgres_connection.py` 3, `test_postgres_fts.py` 2, `test_postgres_migrations.py` 3, `test_postgres_tenant_isolation.py` 2 |
| Live Qdrant | 5 | `test_qdrant_live_integration.py` 5 |
| Host RAM | 1 | `test_m05_database_recovery.py:401` (host available RAM below 2048 MB threshold) |

No failures. The 18 skips are the documented environmental gates and are identical in composition to M13.2. The full-suite pass count increased from 565 (M13.2) to 568 because the three `test_m13_3_startup_schema_guard.py` tests were added.

Warnings (4): one Starlette/httpx TestClient deprecation and three Qdrant client compatibility warnings. No test emitted a failure or error.

---

## 4. Live local PostgreSQL

- Image: `pgvector/pgvector:pg16` (local image, no pull).
- Container: disposable `m133-validation-pg`, bound only to `127.0.0.1:55432`.
- Server: PostgreSQL 16.15; database `m05_integration`; user `m05_test`.
- Fresh database: extensions created from `infrastructure/scripts/init-db.sql`; no prior schema.
- Migration: `alembic upgrade head` exit 0, chain `0001` through `0010`; `alembic current` = `0010_m10_remediation_schema_alignment (head)`.
- PG-gated tests exact line: `12 passed, 5 deselected in 7.38s`.
- Runtime: staging mode, `INGESTION_INLINE_DISPATCHER_ENABLED=false`, HTTPS example origins.
  - `GET /health` -> 200 `{"status":"healthy","timestamp":"2026-11-13T08:37:31.288065Z","version":"0.1.0"}`
  - `GET /ready` -> 200 `{"status":"ready","database":"connected","timestamp":"2026-11-13T08:37:31.404876Z"}`
- Cleanup: temporary Uvicorn stopped; container `m133-validation-pg` removed (`docker rm -f`, exit 0); port 55432 closed.
- `docker ps` after cleanup shows only the pre-existing unrelated containers: `meta-graph-redis` and `meta-graph-neo4j`. No validation container remains.

This validates the local PostgreSQL path only. It is not Neon validation.

---

## 5. M13.2/M13.3 focused suite

Exact line:

```text
161 passed, 1 warning in 75.65s (0:01:15)
```

Files executed:

`test_m13_2_public_access_and_developer.py`, `test_m13_2_provider_endpoint_security.py`, `test_m13_2_storage_error_semantics.py`, `test_m13_2_ingestion_limits.py`, `test_m13_2_api_docs_and_ops.py`, `test_m13_2_frontend_source_guards.py`, `test_m13_2_config_defaults.py`, `test_m13_3_startup_schema_guard.py`.

The 1 warning is the existing Starlette/httpx TestClient deprecation. No failures.

---

## 6. Frontend

| Check | Exit | Result |
|---|---|---|
| `npx tsc --noEmit` | 0 | 0 TypeScript errors |
| `npm run build` | 0 | Next.js 16.4.5 (Turbopack); compiled successfully; TypeScript finished; 20/20 static pages generated |
| `npm run lint` | 1 | `122 problems (38 errors, 84 warnings)` |

Build route table: 18 route entries = 16 static routes plus 2 partial-prerender dynamic routes.

Static routes (16): `/`, `/_not-found`, `/dashboard`, `/dashboard/assistants`, `/dashboard/audit`, `/dashboard/conversations`, `/dashboard/departments`, `/dashboard/employees`, `/dashboard/groups`, `/dashboard/knowledge`, `/dashboard/observability`, `/dashboard/providers`, `/dashboard/settings`, `/dashboard/workspace`, `/login`, `/register`.

Partial-prerender routes (2): `/embed/[publicId]`, `/p/[publicId]`.

Lint classification: 122 findings (38 errors, 84 warnings) exactly matches the M13.2 recorded baseline (`M13_2_FINAL_READINESS_REPORT.md:41`, `M13_2_IMPLEMENTATION_REPORT.md:453`, `M13_2_RESIDUAL_RISKS.md:215`). The dominant findings are `@typescript-eslint/no-explicit-any` errors and unused-import warnings. No lint-fix work was performed, per constraints. The two modified frontend files (`app/login/page.tsx`, `lib/api.ts`) do not introduce new lint categories; the `lib/api.ts` `any` findings are part of the inherited baseline.

---

## 7. SDKs

| SDK | Command | Exit | Result |
|---|---|---|---|
| TypeScript | `tsc -p sdk/typescript/tsconfig.json --noEmit` using `frontend/node_modules/typescript` 5.9.3 | 0 | 0 errors |
| Python | `pytest tests/test_sdk_python.py -q --tb=short` | 0 | `2 passed in 0.09s` |

Environment note: `sdk/typescript` has no local `node_modules` and no TypeScript devDependency, so `npx tsc --noEmit` in that directory exits 1 with the npm "This is not the tsc command you are looking for" guard. Per the no-install constraint, the already-installed frontend TypeScript compiler was used against the SDK tsconfig, which passed with exit 0. This is an SDK packaging gap (no pinned compiler), not a type error.

---

## 8. Quality gates

- `pip check`: exit 0, `No broken requirements found.`
- Ruff, 42 changed/new backend Python files: exit 0, `All checks passed!`
- Ruff, global `ruff check .` from `backend`: exit 1, 28 findings in 9 files (all inherited):
  - `app/services/ingestion/url_ingestion.py` 11
  - `tests/test_m07_knowledge_and_providers.py` 9
  - `app/api/v1/publishing.py` 2
  - 6 single findings: `alembic/versions/0004`, `0006`, `0007`, `0008`, `app/models/assistant.py`, `app/templates/schema.py`
  - Rules: 6 x `I001` (import sorting), 22 x `F401` (unused imports)
- No formatting was run, per constraints.

The changed/new file set is clean; the global count matches the M13.2 historical baseline of 28 findings.

---

## 9. Configuration validation

### render.yaml

| Assertion | Result |
|---|---|
| Services | 2: `mmaip-backend`, `mmaip-frontend` |
| `databases:` block | Absent |
| `CORS_ORIGIN_REGEX` | `"^$"` (asserted) |
| `dockerCommand` shlex split | `["/bin/sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1"]` |
| Contains `exec` | Yes |
| Contains `$PORT` | Yes |
| Workers | `--workers 1` present |

### `.env.example` vs `render.yaml` environment names

Counts: 59 keys in `.env.example`; 44 keys across both Render services. Differences are reported, not treated as failures.

Render-only (11): `AWS_REQUEST_CHECKSUM_CALCULATION`, `AWS_RESPONSE_CHECKSUM_VALIDATION`, `NEXT_PUBLIC_API_BASE_URL`, `NODE_VERSION`, `PREVIOUS_SECRET_KEYS`, `PYTHON_VERSION`, `S3_ACCESS_KEY_ID`, `S3_BUCKET_NAME`, `S3_ENDPOINT_URL`, `S3_REGION_NAME`, `S3_SECRET_ACCESS_KEY`.

- Classification: platform runtime pins (`PYTHON_VERSION`, `NODE_VERSION`), frontend build-time public value (`NEXT_PUBLIC_API_BASE_URL`), B2/S3 secrets and endpoint settings, checksum compatibility toggles, and a security rotation variable. These are intentionally deployment-side and not in the local template.

`.env.example`-only (26): `ALLOWED_ORIGINS`, `ALLOW_DEV_LAN_ORIGINS`, `CUSTOM_PROVIDER_ENDPOINTS_ENABLED`, `DEVELOPER_API_ENABLED`, `EMBEDDING_TIMEOUT_SECONDS`, `ENABLE_API_DOCS`, `INDEXING_CONCURRENCY`, `LLM_DEFAULT_MODEL`, `MAX_EXTRACTED_TEXT_SIZE_BYTES`, `MAX_FILES_PER_REQUEST`, `MAX_FILE_SIZE_BYTES`, `OCR_ENABLED_DEFAULT`, `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_ENABLED`, `PUBLIC_PUBLISHING_ENABLED`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`, `QDRANT_URL`, `RATE_LIMIT_DEVELOPER_PER_MINUTE`, `RATE_LIMIT_INVITE_ACCEPT_PER_HOUR`, `RATE_LIMIT_LOGIN_PER_MINUTE`, `RATE_LIMIT_PUBLIC_MESSAGE_PER_MINUTE`, `RATE_LIMIT_REGISTER_PER_HOUR`, `RATE_LIMIT_UPLOAD_PER_HOUR`, `REDIS_URL`, `STORAGE_PATH`.

- Classification: local-development storage/cache/vector settings, documented feature-gate defaults, and rate-limit knobs that are not overridden for the Render envelope; code defaults apply. No required deployment key is missing from `render.yaml`.

Intentional value differences (names present in both): `.env.example` uses local storage and `sentence-transformers` embeddings, while `render.yaml` selects `s3` and `local`/`local-feature-projection`; `.env.example` documents the broad Vercel regex while `render.yaml` sets `^$`. These are deliberate local-vs-staging differences.

### Secret scan

Patterns scanned over added working-tree diff lines plus 67 untracked text files: `sk-[A-Za-z0-9]{20,}`, `gAAAAA`, `BEGIN .*PRIVATE KEY`, PostgreSQL URL with embedded credentials, and `password=` (case-insensitive). No values were printed.

| Pattern | Hits | Classification |
|---|---|---|
| `sk-` | 0 | - |
| `gAAAAA` | 17 | Placeholder/test documentation |
| `BEGIN ... PRIVATE KEY` | 8 | Placeholder/test documentation |
| PostgreSQL URL with credentials | 61 | Placeholder/test documentation (mostly historical `docs/m10`, `docs/m11`) |
| `password=` | 17 | 16 placeholder/test; 1 false positive |

Totals: 103 hits, 102 placeholder/test, 1 false positive, 0 real secrets.

The single non-placeholder hit is `backend/app/llm/endpoint_validation.py:131` (`password = parsed.password`), a local variable assignment used to reject embedded URL credentials. It contains no secret value.

### Commit-set artifacts

- `.env` and `backend/.env` are untracked and ignored by `.gitignore:44`; neither is in the proposed commit set.
- Local SQLite files exist under `backend/data/`, `backend/local.db`, `backend/test.db`, and `data/`, but all are ignored by `.gitignore:51`/`:53`; tracked DB files = 0 and untracked-in-commit-set DB files = 0.
- The only artifact-regex match in `git status` is `.env.example`, which is the tracked template and not a secret.
- No private keys or credential files are present in the proposed commit set.

---

## 10. Inherited status and limitations

| Item | Status | Evidence |
|---|---|---|
| Live Backblaze B2 | `NOT RUN` | No external calls; no B2 credentials used |
| Live Neon PostgreSQL | `NOT RUN` | Local disposable PG 16 used instead |
| Render deployment | `NOT RUN` | No external calls |
| Live Qdrant | `NOT RUN` | 5 Qdrant integration tests skipped |
| OmniRoute / paid LLM providers | `NOT RUN` | No provider calls |
| Manual UI acceptance | `PENDING` | No browser; build/typecheck only |
| M05 disaster-recovery drills | Inherited `CONDITIONAL_PASS` | Three drills pass; MinIO validation deferred (`M13_2_RESIDUAL_RISKS.md:227`). The RAM-gated live drill was skipped here (host RAM below 2048 MB) and was not re-run |
| Frontend lint debt | Inherited | 122 findings (38 errors, 84 warnings), identical to M13.2 |
| Global Ruff debt | Inherited | 28 findings, identical to M13.2 |
| Concurrent sibling documents | INFO | 3 sibling M13.3 docs appeared during validation; not authored or modified by this task |
| TypeScript SDK compiler pin | Environment gap | No local compiler in `sdk/typescript`; validated with frontend TypeScript 5.9.3, no install performed |

No new functional failures were observed. The only non-zero exits in this stage are the two inherited quality-debt gates (`npm run lint`, global `ruff check .`) and the TS SDK directory's missing local compiler (resolved without installs).

---

## 11. Return summary

```text
BACKEND:  568 passed, 18 skipped, 4 warnings in 1063.50s (0:17:43)
PG:       12 passed, 5 deselected in 7.38s; alembic 0010; /health 200; /ready 200
FOCUSED:  161 passed, 1 warning in 75.65s (0:01:15)
FRONTEND: build exit 0; 18 routes (16 static + 2 partial-prerender), 20/20 pages
LINT:     122 problems (38 errors, 84 warnings) - inherited, exit 1
RUFF:     42 changed/new files pass; global 28 findings (9 files) - inherited
RENDER:   SHA-256 ca4379e9b1034942fa6463d9e4c06c386cea81e7646f6a57b29701b2e0fd641b - MATCH
SECRETS:  0 real hits (103 pattern hits: 102 placeholder/test, 1 false positive)
FAIL:     none new
```