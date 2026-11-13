# M13.3 Stage 2 - Render Blueprint Corrections Review

**Repository:** `E:\MM Office\Multi-Tanant-CaaS`
**Date:** 2026-11-13
**Scope:** Apply the two outstanding `render.yaml` corrections and gate development-only schema creation, then verify the blueprint and targeted tests.
**Mode:** Worktree edits only to `render.yaml`, `backend/app/core/config.py`, `backend/app/main.py`, one new test, and this document. No staging, commit, push, install, external call, `.env` edit, or deployment was performed.

## 1. Final change set

| File | Change |
|---|---|
| `render.yaml` | Added `exec` before Uvicorn in `dockerCommand`; changed `CORS_ORIGIN_REGEX` from `""` to `"^$"`. No other line changed. |
| `backend/app/core/config.py` | Added `should_initialize_schema(app_settings)` returning `app_settings.ENVIRONMENT == "development"`. |
| `backend/app/main.py` | Imported the helper and wrapped `Base.metadata.create_all` in `if should_initialize_schema(settings):`. Role seeding, recovery, dispatcher startup/shutdown, and `/health`/`/ready` are unchanged. |
| `backend/tests/test_m13_3_startup_schema_guard.py` | New file with three tests: development True, staging False, production False. |
| `docs/m13/M13_3_RENDER_BLUEPRINT_REVIEW.md` | This review. |

Relative to the pre-edit worktree, a reverse-edit comparison proved exactly two changed lines in `render.yaml` (line 27 and line 85), five added lines in `config.py`, and the import plus three-line gate in `main.py`. The broader M13.2 topology rewrite of `render.yaml` relative to HEAD was already present and was not modified further.

## 2. Final render.yaml excerpts

### 2.1 Backend service

```yaml
  - type: web
    name: mmaip-backend
    runtime: docker
    region: oregon
    plan: free
    dockerfilePath: infrastructure/docker/backend.Dockerfile
    dockerContext: backend
    dockerCommand: '/bin/sh -c "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1"'
    healthCheckPath: /health
    autoDeploy: false
```

The command is a YAML single-quoted scalar, so `$PORT` survives YAML parsing and is expanded by the container shell at runtime. `/bin/sh -c` receives one double-quoted shell string; `exec` replaces that shell with Uvicorn.

### 2.2 Backend CORS

```yaml
      # CORS & deployed origins (exact HTTPS origins, set per deployment)
      - key: FRONTEND_URL
        sync: false
      - key: BACKEND_URL
        sync: false
      # Explicitly empty: disables the broad Vercel preview regex code default.
      - key: CORS_ORIGIN_REGEX
        value: "^$"
```

The adjacent comment was intentionally left untouched under the two-correction constraint. Its stated intent still holds: `^$` overrides the broad Vercel preview regex default and matches no non-empty origin.

### 2.3 Backend environment flags (relevant)

```yaml
      - key: ENVIRONMENT
        value: staging
      - key: DEBUG
        value: "false"
      - key: ALLOW_PUBLIC_REGISTRATION
        value: "false"
      - key: PYTHON_VERSION
        value: "3.12.3"
      ...
      - key: INGESTION_INLINE_DISPATCHER_ENABLED
        value: "true"
      - key: INGESTION_DISPATCHER_POLL_SECONDS
        value: "3600"
      - key: INGESTION_LEASE_SECONDS
        value: "3600"
      - key: INGESTION_MAX_CONCURRENCY
        value: "1"
```

`ENABLE_API_DOCS`, `PUBLIC_PUBLISHING_ENABLED`, `DEVELOPER_API_ENABLED`, and `CUSTOM_PROVIDER_ENDPOINTS_ENABLED` are absent from the blueprint and use their default-off behavior. API docs are derived off in staging by `api_docs_enabled`.

### 2.4 Frontend service

```yaml
  - type: web
    name: mmaip-frontend
    runtime: node
    region: oregon
    plan: free
    rootDir: frontend
    buildCommand: "npm ci && npm run build"
    startCommand: "npm run start -- -p $PORT"
    healthCheckPath: /login
    autoDeploy: false
    envVars:
      - key: NODE_VERSION
        value: "22.22.0"
      - key: NEXT_PUBLIC_API_BASE_URL
        sync: false
```

### 2.5 Topology

PyYAML parsed the final file as a mapping with `services` only: two web services (`mmaip-backend`, `mmaip-frontend`) and no `databases` block. Database and object storage remain external (Neon Free PostgreSQL 16 and Backblaze B2 Free). Both Render services use `plan: free`.

## 3. Exact changes and rationale

### 3.1 `render.yaml:27` - `exec` before Uvicorn

Before:

```yaml
    dockerCommand: '/bin/sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1"'
```

After:

```yaml
    dockerCommand: '/bin/sh -c "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1"'
```

Without `exec`, `/bin/sh` remains PID 1 and Uvicorn is a child. With `exec`, Uvicorn replaces the shell and receives Render's `SIGTERM` directly, so the FastAPI lifespan shutdown path runs: dispatcher stop, up to 30 seconds of in-flight drain, cancellation on timeout, and engine disposal.

### 3.2 `render.yaml:85` - fail-closed CORS regex

Before:

```yaml
      - key: CORS_ORIGIN_REGEX
        value: ""
```

After:

```yaml
      - key: CORS_ORIGIN_REGEX
        value: "^$"
```

`build_cors_policy` treats an empty string as no regex (`"" or None`). `"^$"` is explicit and non-empty, compiles successfully, and matches only the empty string. A browser never sends an empty `Origin` value, so no real origin is admitted by the regex. Exact origins still come only from `FRONTEND_URL` and `ALLOWED_ORIGINS`.

### 3.3 `backend/app/core/config.py` - development-only schema helper

```python
def should_initialize_schema(app_settings: Settings) -> bool:
    """Return whether startup should create missing tables (development only)."""
    return app_settings.ENVIRONMENT == "development"
```

Placed next to the other environment-derived policy helpers. The comparison is exact, as specified; it does not normalize case or whitespace.

### 3.4 `backend/app/main.py` - gated `create_all`

```python
        if should_initialize_schema(settings):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
```

The rest of the startup `try` block is unchanged: system-role seeding, ingestion recovery, and lease recovery still run in every environment, and the dispatcher still starts for every environment when enabled.

### 3.5 New test

`backend/tests/test_m13_3_startup_schema_guard.py` builds settings with explicit kwargs and `_env_file=None` to avoid developer-local `.env` influence:

```python
def _settings(**overrides) -> Settings:
    """Build settings without reading a developer-local .env file."""
    return Settings(_env_file=None, **overrides)


def test_schema_initialization_enabled_in_development():
    assert should_initialize_schema(_settings(ENVIRONMENT="development")) is True


def test_schema_initialization_disabled_in_staging():
    assert should_initialize_schema(_settings(ENVIRONMENT="staging")) is False


def test_schema_initialization_disabled_in_production():
    assert should_initialize_schema(_settings(ENVIRONMENT="production")) is False
```

## 4. Validation evidence

### 4.1 YAML and command parsing

Executed once from `backend/` with the project virtual environment and PyYAML 6.0.3:

| Check | Result |
|---|---|
| `yaml.safe_load("render.yaml")` | Parsed successfully |
| Services count | 2 |
| Service names | `mmaip-backend`, `mmaip-frontend` |
| `databases` key present | `False` |
| `exec uvicorn app.main:app` present | `True` |
| `$PORT` present in `dockerCommand` | `True` |
| `--workers 1` present | `True` |
| `shlex.split(dockerCommand)` | `['/bin/sh', '-c', 'alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1']` |
| Wrapper intact | `/bin/sh`, `-c`, single shell string |

The `shlex` result has exactly three arguments, so the YAML quoting survives into a correct `/bin/sh -c` invocation.

### 4.2 CORS checks

`re.compile("^$")` was matched against plausible origin values:

| Candidate origin | Match |
|---|---|
| `https://evil.example.com` | `False` |
| `https://mmaip-frontend.vercel.app` | `False` |
| `http://localhost:3000` | `False` |
| `null` | `False` |
| `""` (empty string, not a valid browser `Origin`) | `True` |

I also called the unchanged `build_cors_policy` with staging settings:

```python
Settings(
    _env_file=None,
    ENVIRONMENT="staging",
    FRONTEND_URL="https://mmaip-frontend.example.com",
    CORS_ORIGIN_REGEX="^$",
)
```

Result: `origins = ['https://mmaip-frontend.example.com']`, `origin_regex = '^$'`. No wildcard is present. No CORS code was changed.

### 4.3 Tests, compilation, and lint

Command:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/test_m13_3_startup_schema_guard.py tests/test_m13_2_config_defaults.py -q --tb=short
```

Exact result line:

```text
8 passed in 0.23s
```

`python -m compileall -q app tests/test_m13_3_startup_schema_guard.py` exited `0`. `ruff check` on `app/core/config.py`, `app/main.py`, and the new test reported `All checks passed!` (exit `0`).

### 4.4 Blueprint digest

`render.yaml` final SHA-256:

```text
ca4379e9b1034942fa6463d9e4c06c386cea81e7646f6a57b29701b2e0fd641b
```

Size: 6,501 bytes. Digest covers the worktree file with LF line endings.

## 5. Startup and migration analysis

### 5.1 Migration failure blocks the new container

The shell evaluates `alembic upgrade head && exec uvicorn ...`. Online Alembic (`upgrade head` without `--sql`) uses `settings.DATABASE_URL` (the asyncpg URL) in `backend/alembic/env.py:73`; offline mode uses `DATABASE_SYNC_URL` at line 23. If the migration fails - unreachable Neon, TLS misconfiguration, or a failing revision - `alembic` exits non-zero, `&&` short-circuits, Uvicorn never starts, the container exits, and Render fails the deploy/restart. The schema failure is therefore visible as a failed deploy instead of a running app with a stale schema. Render keeps the last healthy instance serving during a failed deploy.

### 5.2 `exec` and signal handling

`exec` is supported by the Debian `/bin/sh` in `python:3.12-slim`. Uvicorn becomes PID 1, so Render's `SIGTERM` is delivered to the server process rather than to a parent shell. Uvicorn triggers the FastAPI lifespan shutdown, which stops the inline dispatcher, waits up to 30 seconds for an in-flight job, cancels on timeout, and disposes the engine. Without `exec`, the signal path depends on shell forwarding and graceful shutdown is less reliable.

### 5.3 Why `create_all` is now development-only

Before this change, every environment ran `Base.metadata.create_all` during lifespan. In staging/production that lets ORM metadata create missing tables without an Alembic version stamp, can produce a schema that diverges from the migration history, and can mask a failed migration. Alembic in `dockerCommand` already creates the schema before Uvicorn starts, so staging/production must treat Alembic as the only DDL owner. Development keeps `create_all` for fast SQLite/local startup.

Behavior matrix:

| Startup action | Development | Staging / production |
|---|---|---|
| `Base.metadata.create_all` | Yes | No |
| System-role seeding | Yes | Yes |
| Ingestion recovery and lease recovery | Yes | Yes |
| Inline dispatcher (when enabled) | Yes | Yes |
| Schema owner | `create_all` plus migrations | Alembic only |

Seeding and recovery are intentionally not gated: they are idempotent data operations that need the schema to exist, and they must run for a freshly migrated staging database. Their existing error handling is preserved, so a seeding or recovery failure logs a warning and does not prevent the dispatcher from starting.

### 5.4 Health endpoint and health-check timing

`/health` is a liveness probe only: it returns `{"status": "healthy", ...}` and never touches the database. That is the path Render uses (`healthCheckPath: /health`), so platform health checks do not wake Neon. `/ready` performs a real database round-trip and returns 503 on failure; it remains available for deliberate readiness checks but is not the platform probe.

### 5.5 Single worker

`--workers 1` matches the in-process ingestion dispatcher and the process-wide ingestion semaphore, and fits the 512 MB Free instance. Multiple workers would each run lifespan initialization and the dispatcher; job claims are atomic, but there is no reason to pay the duplicate recovery/dispatch overhead in this topology.

### 5.6 Free-tier topology

Both services are `plan: free`, and the blueprint has no `databases` block. Migrations run inline because `preDeployCommand` is paid-only. There is no Render Postgres, Redis, or other paid add-on; Neon and Backblaze B2 are external free-tier services.

## 6. Remaining limitations

1. **Dashboard environment overrides.** Render environment variables set in the Dashboard take precedence over blueprint values. `sync: false` values must be entered before the first deploy, and generated secrets are stored after generation. A dashboard override of `CORS_ORIGIN_REGEX` or `FRONTEND_URL` can change the reviewed policy; confirm the Dashboard matches this file. In staging, `FRONTEND_URL` must be the exact HTTPS frontend origin: the code default is `http://localhost:3000`, which `build_cors_policy` rejects in non-development environments with `RuntimeError`.
2. **`dockerCommand` quoting needs first-deploy verification.** Local parsing proves the YAML scalar and `shlex` structure, but only Render can confirm how it hands `dockerCommand` to the container. On the first deploy, check the logs for successful Alembic output, a Uvicorn bind on `0.0.0.0:$PORT`, and absence of literal `$PORT` text.
3. **Health-check timing.** Migrations complete before Uvicorn starts, so Render's health check cannot pass until `alembic upgrade head` finishes. A slow Neon cold start or a long first migration can exceed the deploy's startup/health grace window and fail the deploy even though the command is correct. `/health` is liveness-only, so it cannot detect a database outage after startup; use `/ready` for deliberate checks and remember each call wakes Neon.
4. **`PYTHON_VERSION` is a no-op under Docker.** The Docker runtime ignores Render's native Python runtime setting. `infrastructure/docker/backend.Dockerfile` uses `python:3.12-slim`, which selects the interpreter. The variable is retained only for provenance.
5. **Worktree-only changes.** This stage forbids git mutations. The corrected blueprint, helper, gate, and test are uncommitted worktree content; a deploy or review based on HEAD will not include them until they are committed. All pre-existing untracked documentation was preserved.
6. **Single instance on Free.** The service has no horizontal redundancy, and Free instances spin down when idle. Cold starts include container boot, migrations, and Uvicorn startup, so first-request latency after idle will be higher than a warm service.

## 7. Conclusion

The two blocking blueprint corrections are applied exactly: `exec` precedes Uvicorn in the single-quoted `/bin/sh -c` command, and `CORS_ORIGIN_REGEX` is the fail-closed `^$`. The YAML parses as two free web services with no databases block; the command parses into the expected three-argument `shlex` form; the CORS policy admits only the exact configured frontend origin and no regex-matched origin. Startup no longer creates schema in staging or production, while development keeps `create_all`; seeding, recovery, and dispatcher behavior are unchanged. Targeted tests, compilation, and lint pass. Staging approval still depends on committing these changes and completing the first-deploy checks listed above.