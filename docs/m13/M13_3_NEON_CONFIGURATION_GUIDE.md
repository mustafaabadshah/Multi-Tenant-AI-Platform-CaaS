# M13.3 Stage 3 - Neon PostgreSQL Configuration Guide

| Field | Value |
|---|---|
| Milestone | M13.3 Stage 3 - Neon connection, pool, pgvector, and operator configuration |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Baseline | `main` @ `9c27e1b8d3e6aeec00dcf6ddb84cd849b9a607e8`; worktree has modified `render.yaml`, `backend/app/core/config.py`, and `.env.example` |
| Date | 2026-11-13 |
| Mode | **READ-ONLY.** No Neon or Render account, database connection, migration, install, secret, deployment, or Git mutation was performed. |
| Live validation | `LIVE_NEON_VALIDATION = NOT RUN` |
| Scope | Explain the two database URL forms, the asyncpg/libpq split, pool and timeout behavior, the pgvector startup dependency, Neon scale-to-zero, and the operator sequence. Any recommendation is a proposal and was not applied. |
| Inputs | `backend/app/core/config.py`, `backend/app/database/session.py`, `backend/alembic/env.py`, `backend/alembic.ini`, `backend/alembic/versions/0003_embeddings_and_vector_stores.py`, `.env.example`, `render.yaml`, `docs/m13/M13_DATABASE_AND_STORAGE_SETUP.md`, `docs/m13/M13_DEPLOYMENT_CONFIGURATION.md`, `docs/m13/M13_2_RUNTIME_LIMITS.md`, `docs/m13/M13_3_RENDER_BLUEPRINT_REVIEW.md` |
| Evidence convention | `path:line` is repository source. Prior local measurements are marked as inherited evidence, not re-run here. |

> This guide is a configuration gate, not a deployment result. Do not paste a real password, connection string, or key into this document, a chat, a ticket, a screenshot, or a commit. Every operator action below is marked **NOT EXECUTED**.

---

## 1. Current code facts

| Area | Evidence | Fact |
|---|---|---|
| Async URL default | `backend/app/core/config.py:43` | `DATABASE_URL` defaults to a local development URL: `postgresql+asyncpg://<user>:<password>@localhost:5432/mmaip_dev`. |
| Sync URL default | `backend/app/core/config.py:44` | `DATABASE_SYNC_URL` defaults to a local development URL: `postgresql://<user>:<password>@localhost:5432/mmaip_dev`. |
| Async URL normalization | `backend/app/core/config.py:46-54` | `postgres://` and plain `postgresql://` are rewritten to `postgresql+asyncpg://`. The validator does **not** rewrite or remove query parameters. |
| Sync URL normalization | `backend/app/core/config.py:56-61` | Only `postgres://` is rewritten to `postgresql://`. |
| Pool settings | `backend/app/core/config.py:63-66` | `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10`, `DB_POOL_TIMEOUT=30`, `DB_POOL_RECYCLE=1800`. |
| Engine construction | `backend/app/database/session.py:10-26` | `pool_pre_ping=True`; non-SQLite engines add the pool settings and `connect_args={"timeout": 3}`. |
| Readiness probe | `backend/app/database/session.py:52-60` | `SELECT 1` inside `asyncio.timeout(3)`. |
| Online Alembic target | `backend/alembic/env.py:70-87` | Online migrations use `settings.DATABASE_URL` (async URL) unless `sqlalchemy.url` is set. `alembic.ini` sets no URL. |
| Offline Alembic target | `backend/alembic/env.py:22-33` | Offline (`--sql`) migrations use `settings.DATABASE_SYNC_URL`. |
| Alembic config | `backend/alembic.ini:3-6` | `script_location = alembic`; no `sqlalchemy.url`. |
| pgvector extension | `backend/alembic/versions/0003_embeddings_and_vector_stores.py:23-30` | PostgreSQL migration runs `CREATE EXTENSION IF NOT EXISTS vector`. |
| Migration chain | `backend/alembic/versions/0001...0010` | Single linear chain; current head is `0010_m10_remediation_schema_alignment`. |
| Startup migration | `render.yaml:27` | `/bin/sh -c "alembic upgrade head && exec uvicorn ... --workers 1"`. A migration failure short-circuits Uvicorn. |
| Platform health | `render.yaml:28`; `backend/app/main.py:143-150` | Render checks `/health`, which never touches the database. |
| Public readiness | `backend/app/main.py:152-176` | `/ready` is public, performs a real database round trip, and returns a generic 503 on failure. |
| Schema owner in staging | `backend/app/core/config.py:154-156`; `backend/app/main.py:33-35` | `create_all` runs only in development. Staging/production schema is owned by Alembic. |

The two URLs are not interchangeable. The application driver is asyncpg; libpq tooling and offline Alembic use the sync URL. Online Alembic is the exception: it consumes the async URL.

The reviewed M13.3 blueprint state is assumed: `exec` precedes Uvicorn in `dockerCommand`, `CORS_ORIGIN_REGEX` is `^$`, and the Neon variables are `sync: false`. This guide does not modify any of them.

---

## 2. Connection URL forms

### 2.1 The two supported forms

Use the **direct** Neon host for the first staging cut. The pooled host is a later experiment, not the default.

**Application / online Alembic (asyncpg):**

```text
postgresql+asyncpg://USER:PASSWORD@DIRECT-HOST:5432/DB?ssl=require
```

**Sync URL / offline Alembic (libpq):**

```text
postgresql://USER:PASSWORD@DIRECT-HOST:5432/DB?sslmode=require
```

Concrete staging shapes, with no real values:

```text
DATABASE_URL=postgresql+asyncpg://mmaip_user:<db-password>@<neon-direct-host>:5432/mmaip_staging?ssl=require
DATABASE_SYNC_URL=postgresql://mmaip_user:<db-password>@<neon-direct-host>:5432/mmaip_staging?sslmode=require
```

Rules:

1. The async URL must use `postgresql+asyncpg://` and `ssl=require`.
2. The sync URL must use `postgresql://` and `sslmode=require`.
3. Percent-encode any password character that is special in a URL (`@`, `:`, `/`, `?`, `#`, `%`, and spaces). Do not work around a parsing problem by weakening TLS.
4. Never put either URL in `render.yaml`, this document, or Git. Use the secret manager and the Render Dashboard.
5. `DATABASE_SYNC_URL` does **not** control an online `alembic upgrade head`. Online Alembic reads `DATABASE_URL` (`backend/alembic/env.py:70-76`).

> **Documentation inconsistency found:** `.env.example:68` describes `DATABASE_SYNC_URL` as "Sync DB URL for Alembic migrations if needed". That is only true for offline (`--sql`) mode. Online migrations use the async `DATABASE_URL`. The M13 database runbook states the correct behavior, but the template comment is misleading for an operator who sets only the sync URL.

### 2.2 Why `sslmode` and `channel_binding` break asyncpg

A Neon connection string copied from the console commonly looks like:

```text
postgresql://USER:PASSWORD@HOST/DB?sslmode=require&channel_binding=require
```

That is a libpq URL, not an asyncpg URL in this stack.

The failure path is exact:

1. SQLAlchemy's asyncpg dialect copies every URL query parameter into DBAPI connect keyword arguments: `opts.update(url.query)` at `backend/.venv/Lib/site-packages/sqlalchemy/dialects/postgresql/asyncpg.py:1181`.
2. The dialect then calls `asyncpg.connect(**opts)`.
3. The pinned asyncpg `connect()` signature accepts `ssl=`, but has no `sslmode=`, `channel_binding=`, or `connect_timeout=` keyword (`backend/.venv/Lib/site-packages/asyncpg/connection.py:2116-2135`).
4. The call fails before any network connection, for example: `TypeError: connect() got an unexpected keyword argument 'sslmode'`.

The nuance that causes confusion: asyncpg's own **DSN parser** understands `sslmode`, `sslrootcert`, and related libpq fields when they are inside a DSN string (`asyncpg/connection.py:2151-2155`). SQLAlchemy does not pass the URL to asyncpg as a DSN; it passes parsed components and query parameters as keyword arguments. `sslmode` therefore never reaches the DSN parser.

| Parameter in a SQLAlchemy async URL | Result | Action |
|---|---|---|
| `ssl=require` | Accepted as the asyncpg `ssl` keyword; asyncpg parses the string mode (`asyncpg/connect_utils.py:686-708`). | Use this for the first cut. |
| `sslmode=require` | Passed as an unsupported keyword; `TypeError` before connecting. | Remove it. |
| `channel_binding=require` | Passed as an unsupported keyword; `TypeError` before connecting. | Remove it. |
| `connect_timeout=...` | Passed as an unsupported keyword; `TypeError` before connecting. | Remove it; use the code-level engine timeout instead. |
| `sslrootcert=...` | Passed as an unsupported keyword; `TypeError` before connecting. | Do not append it to the async URL. See Section 2.4. |
| `application_name=...` | Not an asyncpg connect keyword; passed as a keyword and rejected unless handled through `server_settings`. | Do not add arbitrary query parameters. |

The config validator does not save an operator from this: it rewrites the scheme but leaves the query string untouched (`backend/app/core/config.py:46-54`). A URL that looks accepted at configuration time can still fail at the first connection.

### 2.3 Direct host versus `-pooler`

| | Direct host | Pooled host |
|---|---|---|
| Host shape | Does not contain `-pooler`. | Contains `-pooler` (Neon's PgBouncer endpoint). |
| Pooling | PostgreSQL session pooling inside the app's SQLAlchemy pool. | Neon transaction pooling in front of PostgreSQL. |
| Prepared statements | Compatible. | Transaction pooling can invalidate cached prepared statements between transactions. |
| Alembic | Required for the first cut. | Do not use for Alembic. |
| Recommendation | **Use for both runtime and Alembic initially.** | Optional later runtime experiment only. |

Why prepared statements matter:

- SQLAlchemy's asyncpg dialect keeps a prepared-statement cache of **100** entries by default (`sqlalchemy/dialects/postgresql/asyncpg.py:769,960-961`).
- asyncpg also has its own statement cache, default `statement_cache_size=100` (`asyncpg/connection.py:2124`).
- A transaction-pooling proxy can move a later command to a different backend session, so a cached prepared statement may not exist there. Typical errors are `prepared statement "..." does not exist` or protocol errors under concurrency.

If the pooled host is ever tested:

```text
postgresql+asyncpg://USER:PASSWORD@<neon-pooled-host>:5432/DB?ssl=require&prepared_statement_cache_size=0
```

- `prepared_statement_cache_size=0` is a SQLAlchemy DBAPI argument; SQLAlchemy coerces it to `int` (`asyncpg.py:1204`) and disables the dialect-level cache.
- It does **not** disable asyncpg's own cache. Adding `statement_cache_size=0` to the URL is unsafe here because SQLAlchemy passes it as a string and asyncpg expects an integer; the M13 Phase 3 runbook records the resulting `TypeError`.
- Disabling asyncpg's cache requires a code-level `connect_args={"statement_cache_size": 0}`, which is outside this read-only guide.
- Keep Alembic on the direct host even if runtime moves to the pooled host. A migration is a long-lived, stateful session and is the worst candidate for transaction pooling.

For one Render Free instance and one Uvicorn worker, the direct host is simpler, has no pooler compatibility risk, and fits the 15-connection ceiling described in Section 3.

### 2.4 TLS verification caveat

`ssl=require` means "require TLS, but do not verify the server certificate or hostname." With the pinned asyncpg 0.32.0:

- The `require` SSL mode, selected by `ssl=require`, sets `check_hostname=False` and, when no root certificate is found, `verify_mode=CERT_NONE` (`asyncpg/connect_utils.py:699-708,743-744`).
- Traffic is encrypted, but a compromised DNS or route could redirect it to an endpoint with any certificate.
- This is the same practical caveat as libpq `sslmode=require`; it is not "TLS is off."

If certificate verification is required:

```text
postgresql+asyncpg://USER:PASSWORD@DIRECT-HOST:5432/DB?ssl=verify-full
```

With asyncpg 0.32.0, the string `verify-full` sets `check_hostname=True` and requires a root certificate. The lookup is `PGSSLROOTCERT` or `~/.postgresql/root.crt`; if neither is available, asyncpg raises a `ClientConfigurationError` for modes above `require` (`asyncpg/connect_utils.py:700-746`). You cannot fix this by appending `sslrootcert=...` to the SQLAlchemy URL, because that parameter is passed as an unsupported keyword.

Options, in order of preference for staging:

1. **Accept `ssl=require` for the closed synthetic staging envelope.** Record the non-verification caveat. Neon still presents a certificate and the connection is encrypted.
2. **Set `PGSSLROOTCERT`** to a certificate file that exists in the Render container. This requires the file to be baked into the image or otherwise present; Render Free has no persistent disk. Treat the image change as a separate approved change.
3. **Pass a code-level `ssl.SSLContext`** through `connect_args` with the CA loaded. This is a code change, not a URL change, and is outside this guide.

Do not use `ssl=disable`, `sslmode=disable`, or a URL with no TLS parameter as a workaround. The asyncpg default is `prefer`, which negotiates TLS but does not verify it; make the intent explicit with `ssl=require`.

---

## 3. Pool and timeout behavior

### 3.1 Effective values

| Setting | Value | Source | Meaning |
|---|---:|---|---|
| `DB_POOL_SIZE` | 5 | `config.py:63` | Persistent connections kept per process. |
| `DB_MAX_OVERFLOW` | 10 | `config.py:64` | Burst connections above the pool. |
| Maximum per process | 15 | arithmetic | 5 + 10. |
| `DB_POOL_TIMEOUT` | 30 s | `config.py:65` | Time a request waits for a free pooled connection. This is not a connect timeout. |
| `DB_POOL_RECYCLE` | 1800 s | `config.py:66` | Recycle a connection after 30 minutes. |
| `pool_pre_ping` | `True` | `session.py:13` | Ping a checked-out connection; reconnect if it is dead. |
| asyncpg connect timeout | 3 s | `session.py:22` | `connect_args={"timeout": 3}` bounds new connection establishment. |
| `/ready` outer timeout | 3 s | `session.py:55` | Bounds the whole readiness round trip. |

The 15-connection ceiling is per process. One Render instance and one Uvicorn worker is the approved topology, so the deployment should not exceed 15 application connections. Confirm the Neon project's connection limit in the console and reserve headroom for one migration session and an operator `psql` session. Do not scale horizontally during acceptance.

`pool_pre_ping` adds a lightweight round trip on checkout. On Neon this is useful because a suspended compute or an idle network path can leave a pooled TCP connection dead; pre-ping detects it and forces a reconnect. The reconnect is still subject to the 3-second connect timeout.

### 3.2 The 3-second cold-wake risk

Neon Free scales compute to zero after about five minutes of inactivity. The next connection attempt wakes the compute; that wake can take longer than three seconds.

Two different paths matter:

1. **Render container cold start.** Render starts the container, then `dockerCommand` runs `alembic upgrade head` before Uvicorn (`render.yaml:27`). Alembic builds its own engine with `NullPool` and no `connect_args` (`backend/alembic/env.py:78-82`), so it uses asyncpg's default 60-second connect timeout, not the 3-second application timeout. The migration therefore has a better chance of surviving a Neon wake and it warms the database before Uvicorn starts. The cost is that Render's health check cannot pass until the migration finishes.
2. **Application idle while the container is still alive.** The container may remain up while Neon suspends. The first request that needs a new connection can hit the 3-second timeout and fail, even though the container is healthy. `/ready` can return 503 for the same reason because its outer budget is also three seconds.

**Proposal only, not applied:** raise the application engine's `connect_args={"timeout": 3}` to 10-15 seconds in `backend/app/database/session.py:22`. Keep `/ready` bounded; it is a deliberate probe, not the platform liveness check. A longer engine connect timeout gives an idle-but-live container a chance to wake Neon without changing the public readiness budget. If a cold `/ready` 200 is required, align the readiness budget in a separate approved change and accept the extra wake/CU-hour cost. Do not add a keep-alive; Section 5 explains why.

Do not raise `DB_POOL_TIMEOUT` to compensate for a connect timeout. They measure different waits: pool checkout versus connection establishment.

---

## 4. pgvector and migration 0003

### 4.1 What the migration does

`backend/alembic/versions/0003_embeddings_and_vector_stores.py:23-30` runs, on PostgreSQL only:

```sql
CREATE EXTENSION IF NOT EXISTS vector
```

The same migration later creates `chunk_embeddings.vector` using the `pgvector.sqlalchemy.Vector` type (`0003...py:120`). SQLite skips the extension statement and does not use pgvector in the same way.

### 4.2 Privileges: owner role versus application role

The extension is not a schema object the application role can always create. `CREATE EXTENSION` requires the privileges PostgreSQL requires for that extension. Extension trust varies by distribution, and a role that only owns the database can still lack the privilege to install pgvector. The failure can look like:

```text
ERROR: permission denied to create extension "vector"
HINT: Must be superuser to create this extension.
```

Recommended split:

| Role | Use | Privilege |
|---|---|---|
| Neon project owner / default administrative role | Create the database, create the extension, perform controlled operator DDL. | Extension-capable; keep out of the application. |
| `mmaip_user` | Application runtime and online Alembic. | Owns or can use the `mmaip_staging` schema; **not** a superuser. |

If `mmaip_user` is the database owner and the extension creation still fails, run the extension statement once as the project owner role, then verify the application role can use vector columns. Do not grant superuser to `mmaip_user` to work around the error.

Migration 0003's `IF NOT EXISTS` makes a pre-created extension a no-op. Pre-creating it as the owner proves the extension is available and keeps the migration from depending on the application role's extension privilege.

### 4.3 Exact operator SQL

Run these as the project owner against `mmaip_staging` in the Neon SQL Editor, one statement at a time:

```sql
SELECT current_database(), current_user, session_user;
```

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

```sql
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

Expected:

| Query | Expected |
|---|---|
| `current_database()` | `mmaip_staging` |
| `current_user` / `session_user` | The approved owner role, not an unrelated project |
| `CREATE EXTENSION` | Success, or a notice that the extension already exists |
| `pg_extension` row | One row: `extname=vector`, `extversion=<installed version>` |

Record the exact `extversion`. Do not assume a version. pgvector operator classes and behavior can vary by version, and the application's cosine/vector queries depend on the installed extension.

Optional read-only identity checks:

```sql
SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid();
SHOW server_version;
SELECT count(*) AS non_alembic_public_tables
FROM pg_tables
WHERE schemaname = 'public' AND tablename <> 'alembic_version';
```

On a fresh database, `pg_stat_ssl.ssl` should be `t`, `server_version` should be the approved 16.x, and the non-Alembic table count should be `0`. Do not run migrations if the table count is non-zero and unexplained.

### 4.4 Failure behavior blocks startup

The startup command is a shell `&&` chain (`render.yaml:27`):

```text
alembic upgrade head && exec uvicorn ...
```

If migration 0003 fails because the extension cannot be created, or because any later revision fails, the sequence is:

1. Alembic exits non-zero.
2. `&&` short-circuits; `exec uvicorn` is never reached.
3. The container exits.
4. Render fails the deploy or restart.
5. The previous healthy instance, if any, remains in service during a failed deploy.

That is the intended fail-closed behavior: the application never serves with a schema that is missing the vector extension. There is no `create_all` fallback in staging (`config.py:154-156`; `main.py:33-35`), so Alembic is the only schema owner.

If the migration is run externally and fails, do not assume the Render start will repair it. The same `alembic upgrade head` runs at container start and will fail again unless the privilege or extension problem is fixed. Fix the cause; do not stamp a revision manually.

---

## 5. Neon scale-to-zero and health behavior

### 5.1 Free-plan behavior

| Behavior | Value | Implication |
|---|---|---|
| Scale-to-zero | After about 5 minutes idle | The next connection wakes compute; expect latency. |
| Compute allowance | 100 CU-hours/project/month | A 24/7 backend at 0.25 CU is about 180 CU-hours, exhausting the allowance well before month end. |
| Storage | 1 GB/project | Keep synthetic data small. |
| Egress | 5 GB/project | Do not stream large objects through the database. |
| Connection pooling | PgBouncer transaction pooling on the `-pooler` host | Prepared-statement caveat in Section 2.3. |

These are provider allowances recorded in `docs/m13/M13_FREE_TIER_COST_AND_LIMITS.md`; they are not re-measured here.

### 5.2 `/health` versus `/ready`

| Endpoint | Database work | Platform use | Cost |
|---|---|---|---|
| `GET /health` | None (`main.py:143-150`) | Render health check (`render.yaml:28`). | No Neon wake. |
| `GET /ready` | Real `SELECT 1` (`main.py:152-176`; `session.py:52-60`). | Deliberate human or deploy readiness check only. | Wakes Neon and consumes compute. |

`/ready` is public and unauthenticated. It returns a generic 503 on failure and does not leak the DSN, driver, or stack. That masking reduces disclosure, not cost. Any internet client can wake the database by polling it.

Operational rules:

1. Use `/health` for Render and uptime monitoring.
2. Do not poll `/ready` from a monitor, cron job, or in-app loop.
3. Call `/ready` once after a deploy, after warm-up, and after a deliberate database check.
4. Do not add a keep-alive. A keep-alive defeats Neon scale-to-zero and consumes the 100 CU-hour allowance.
5. Keep `INGESTION_DISPATCHER_POLL_SECONDS=3600` (`render.yaml:110-111`); the empty-queue dispatcher must not query every two seconds.
6. Treat a single cold-start `/ready` 503 as a recorded observation, not a product failure. Warm the database and retry once. A persistent 503 is an investigation, not a retry loop.

### 5.3 Cold-start path

A Render Free backend cold start has several serial stages:

1. Container boot.
2. `alembic upgrade head` against Neon (migration check, and a Neon wake if suspended).
3. Uvicorn start and FastAPI lifespan.
4. Role seeding and ingestion/lease recovery (these do database work).
5. Render's first `/health` probe.

The migration stage uses a longer default connect timeout than the application engine, which helps on a cold Neon compute, but it also delays the health check. Do not shorten the health-check grace window without measuring this path. A deployment can fail on a slow first migration even when the command is correct.

---

## 6. Operator configuration steps

> **Status of every step in this section: NOT EXECUTED.** Account creation, database creation, secret entry, and migration are external actions that require explicit approval. No step below was performed by this document.

### 6.1 Create the Neon Free project

1. Sign in to the Neon console after approval.
2. Create project `mmaip-staging`.
3. Select PostgreSQL **16** if offered. Record the offered version if not.
4. Select the region closest to Render `oregon`; record the exact region ID and display name.
5. Select the **Free** plan. Stop if a card, billing profile, paid plan, or identity verification beyond normal sign-up is requested.
6. Record the project ID, region, Postgres version, default branch, and creation date. Do not record the password.

**Stop conditions:** card or billing prompt, wrong region, existing project with the same name that is not the intended staging project, or an unexpected major version.

### 6.2 Create the database and roles

Use the Neon SQL Editor connected to the default database. `CREATE DATABASE` cannot run inside a transaction block; run it alone.

```sql
CREATE ROLE mmaip_user LOGIN PASSWORD '<db-password>';
```

```sql
CREATE DATABASE mmaip_staging OWNER mmaip_user;
```

Then connect to `mmaip_staging` and create the extension as the **project owner** role, not as `mmaip_user` if `mmaip_user` lacks extension privilege:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

```sql
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

Record the role that created the extension and the installed version. Do not grant superuser to `mmaip_user`. If the role/database already exists, do not recreate it; record the existing names and verify ownership.

### 6.3 Copy both Neon URLs

In the Neon **Connect** dialog:

1. Select the branch, database `mmaip_staging`, and role `mmaip_user`.
2. Turn **Pooled connection** off. Copy the direct URL. The host does not contain `-pooler`.
3. Turn **Pooled connection** on. Copy the pooled URL. The host contains `-pooler`.
4. Store both in the secret manager immediately. Record only non-secret labels such as `neon-direct-host` and `neon-pooled-host` if host disclosure is approved.

Do not paste either URL into this document or a chat. The console URL commonly contains `sslmode=require` and may contain `channel_binding=require`; those must be converted for the async URL.

### 6.4 Set Render dashboard overrides

`render.yaml:45-52` marks both database variables `sync: false`. Render will prompt for them and will not overwrite an existing dashboard value. Set both explicitly:

```text
DATABASE_URL=postgresql+asyncpg://mmaip_user:<db-password>@<neon-direct-host>:5432/mmaip_staging?ssl=require
DATABASE_SYNC_URL=postgresql://mmaip_user:<db-password>@<neon-direct-host>:5432/mmaip_staging?sslmode=require
```

Checklist:

- [ ] `DATABASE_URL` uses `postgresql+asyncpg://`.
- [ ] `DATABASE_URL` uses `?ssl=require`.
- [ ] `DATABASE_URL` contains no `sslmode=`, `channel_binding=`, `connect_timeout=`, or `sslrootcert=`.
- [ ] `DATABASE_SYNC_URL` uses `postgresql://` and `?sslmode=require`.
- [ ] Both point at the **direct** host for the first cut.
- [ ] The password is percent-encoded if it contains URL-special characters.
- [ ] No secret appears in a screenshot, ticket, commit, or chat.
- [ ] Dashboard values match the reviewed blueprint intent; a dashboard override of `CORS_ORIGIN_REGEX`, `FRONTEND_URL`, or `BACKEND_URL` can change the reviewed policy, but those are outside this database guide.

If the pooled endpoint is later approved for runtime, change only `DATABASE_URL` to the pooled host and add `&prepared_statement_cache_size=0`; keep `DATABASE_SYNC_URL` and Alembic on the direct host. Do not make that change during the first migration.

### 6.5 Identity confirmation gate (blocking)

Run from `backend`, using the project virtual environment. The command prints no password.

```powershell
Set-Location -LiteralPath "E:\MM Office\Multi-Tanant-CaaS\backend"
& ".venv\Scripts\python.exe" -c "from sqlalchemy.engine.url import make_url; import os; u=make_url(os.environ['DATABASE_URL']); print('driver=' + u.drivername, 'host=' + str(u.host), 'port=' + str(u.port), 'db=' + str(u.database), 'user=' + str(u.username))"
```

Expected shape:

```text
driver=postgresql+asyncpg host=<neon-direct-host> port=5432 db=mmaip_staging user=mmaip_user
```

If the command raises `KeyError`, `DATABASE_URL` is not set in the current shell. Stop and set it explicitly; do not let the process fall back to a developer-local `.env`.

Gate table:

| Gate | Check | Stop condition |
|---|---|---|
| G1 | Parsed host is the new Neon direct host. | Host is production, localhost, pooled, or ambiguous. |
| G2 | Database is `mmaip_staging`. | Any other database name. |
| G3 | User is `mmaip_user`, not the project owner/superuser. | The application would run as the owner role. |
| G4 | `alembic current` shows no unexpected revision. | A revision exists that the team did not expect. |
| G5 | Non-Alembic public table count is `0` on a fresh database. | Unknown tables exist. |
| G6 | Shell `DATABASE_URL` is the direct async URL. | Unset, localhost, pooled, or sync-only. |
| G7 | Neon project ID and region match the approved staging project. | Any mismatch or uncertainty. |
| G8 | Written confirmation that this is not production. | No confirmation. |
| G9 | No other migration is running, including the Render `dockerCommand` migration. | Two migration owners. |

**Never run migrations against production.** Alembic has no environment guard; it migrates whatever `DATABASE_URL` points at.

### 6.6 Run the migration only after the gate

Use single-quoted PowerShell strings so a `$` in a password is not interpolated. Do not print the URL.

```powershell
Set-Location -LiteralPath "E:\MM Office\Multi-Tanant-CaaS\backend"

$env:DATABASE_URL = 'postgresql+asyncpg://mmaip_user:<db-password>@<neon-direct-host>:5432/mmaip_staging?ssl=require'
$env:DATABASE_SYNC_URL = 'postgresql://mmaip_user:<db-password>@<neon-direct-host>:5432/mmaip_staging?sslmode=require'

& ".venv\Scripts\python.exe" -m alembic current
& ".venv\Scripts\python.exe" -m alembic heads
& ".venv\Scripts\python.exe" -m alembic upgrade head
& ".venv\Scripts\python.exe" -m alembic current
```

Expected:

| Command | Expected |
|---|---|
| `alembic current` before upgrade | No revision on a fresh database, or a documented expected baseline. |
| `alembic heads` | Exactly one head: `0010_m10_remediation_schema_alignment`. |
| `alembic upgrade head` | Completes without error. |
| `alembic current` after upgrade | `0010_m10_remediation_schema_alignment (head)`. |

Do not run this command in parallel with the Render `dockerCommand` migration or another operator. One migration owner at a time.

If the migration fails:

1. Do not rerun blindly.
2. Capture the error text with credentials redacted.
3. Query `SELECT version_num FROM alembic_version;` if the table exists.
4. Determine whether the failure occurred before or after a partial DDL commit.
5. Follow the rollback caution in Section 6.9.

### 6.7 Post-migration verification

```sql
SELECT version_num FROM alembic_version;
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
SELECT count(*) AS public_tables FROM pg_tables WHERE schemaname = 'public';
SELECT count(*) AS non_alembic_public_tables
FROM pg_tables
WHERE schemaname = 'public' AND tablename <> 'alembic_version';
```

Expected:

| Check | Expected |
|---|---|
| `alembic_version.version_num` | `0010_m10_remediation_schema_alignment`. |
| `vector` extension | Present; record `extversion`. |
| Public table count | Record the observed count; compare with the release baseline. Do not assert a count without reading the release. |
| Non-Alembic table count | Matches the expected fresh-migration count, not `0` after a successful migration. |
| Application health | `GET /health` returns 200; `GET /ready` returns 200 after warm-up. |

The M13 database runbook records an M12 baseline of 46 application tables, 98 foreign keys, and 119 `ix_%` indexes at the then-current release. Treat those as comparison values, not as a guarantee for the exact revision deployed now.

### 6.8 Render startup behavior after the migration

`render.yaml:27` runs the migration on every container start, including a restart after spin-down. This is intentional:

- It guarantees the schema is at head before Uvicorn starts.
- It makes a migration failure a failed deploy/restart rather than a running app with a stale schema.
- It adds migration-connect latency to every cold start.
- It can wake Neon before Uvicorn, which usually warms the database for the first requests.

Do not add a second migration mechanism (for example `create_all` or a manual `alembic stamp`) as a fallback. Staging has one schema owner: Alembic.

### 6.9 Rollback caution

- Do not run `alembic downgrade` against live staging; the downgrade path is not the release gate and can drop columns or data.
- Preferred rollback: redeploy the previous reviewed commit and, if schema compatibility requires it, restore into a **new** database or Neon branch, verify, then repoint after approval.
- If Neon branching is available, create a branch before the first migration as a rollback point. Branch creation is an external action and requires explicit approval.
- Do not restore over the live database without explicit approval.
- A failed migration leaves a failure state for diagnosis. Do not drop the database to "start over" without approval.

---

## 7. Findings and incompatibilities

| ID | Finding | Evidence | Disposition |
|---|---|---|---|
| N-1 | `sslmode`, `channel_binding`, `connect_timeout`, and `sslrootcert` in the async URL are hard failures before connect. | SQLAlchemy passes URL query as kwargs (`asyncpg.py:1181`); asyncpg has no such connect keywords (`connection.py:2116-2135`). | Use `ssl=require`; strip all libpq-only parameters. `render.yaml:45-48` already states this intent. |
| N-2 | Online Alembic ignores `DATABASE_SYNC_URL`. | `backend/alembic/env.py:70-76`. | Operator must set `DATABASE_URL` for online migrations. `.env.example:68` is misleading; documentation-only inconsistency. |
| N-3 | The 3-second engine connect timeout can fail on a Neon cold wake while the container is alive. | `session.py:22`; `session.py:55`; Neon scale-to-zero after about 5 minutes. | **Proposal only:** 10-15 s engine connect timeout; keep `/ready` bounded; no keep-alive. Not applied. |
| N-4 | `ssl=require` encrypts but does not verify the certificate or hostname. | asyncpg 0.32.0 `connect_utils.py:699-708,743-744`. | Accepted for the closed staging envelope; `ssl=verify-full` needs a root cert available to asyncpg and is not a URL-only change. |
| N-5 | pgvector extension creation can fail for an application role that is not extension-capable. | Migration 0003 line 29; PostgreSQL extension privilege model. | Pre-create as the project owner; do not grant superuser to `mmaip_user`. Failure blocks startup via `&&`. |
| N-6 | The pooled endpoint can break asyncpg prepared statements. | SQLAlchemy default cache 100 (`asyncpg.py:769`); asyncpg default 100 (`connection.py:2124`); Neon transaction pooling. | Direct host for the first cut. Pooled only with `prepared_statement_cache_size=0` and a soak test; asyncpg's own cache needs a code change to disable. |
| N-7 | `pool_pre_ping` reconnect attempts are subject to the same 3-second connect timeout. | `session.py:13,22`. | Covered by N-3; do not treat a pre-ping failure as data corruption. |
| N-8 | `alembic upgrade head` runs on every container start. | `render.yaml:27`. | By design; budget for cold-start migration latency and a failed-deploy path on error. |
| N-9 | `create_all` is development-only, so staging has no schema fallback. | `config.py:154-156`; `main.py:33-35`. | Alembic must succeed; do not add a fallback. |

No blocking code incompatibility was found in the reviewed configuration. The hard failures are configuration-shape failures that the operator can avoid, and the timeout/verification items are documented risks or proposals.

---

## 8. What remains unverified

`LIVE_NEON_VALIDATION = NOT RUN`. None of the following was proven by this guide:

1. A real Neon connection using the direct host and `ssl=require`.
2. A real online Alembic run against Neon, including the pgvector extension privilege path.
3. The exact Neon Free connection limit versus the 15-connection application ceiling.
4. Cold-wake latency and whether the 3-second engine timeout actually fails in the deployed container.
5. Whether `ssl=verify-full` can find a usable root certificate in the Render image.
6. Pooled-endpoint behavior with asyncpg prepared statements.
7. Render `dockerCommand` quoting, migration-before-Uvicorn ordering, and health-check timing in the actual service.
8. `/health` and `/ready` responses from the deployed service.
9. Neon CU-hour consumption under the intended idle/scale-to-zero pattern.
10. Any production or non-synthetic data path. This guide covers staging configuration only.

---

## 9. Conclusion

The reviewed application has two distinct database URL contracts: `DATABASE_URL` is the asyncpg URL used by the runtime and by online Alembic; `DATABASE_SYNC_URL` is the libpq URL used only by offline Alembic. The async URL must use `ssl=require` and must not contain `sslmode`, `channel_binding`, `connect_timeout`, or `sslrootcert`. The direct Neon host is the correct first-cut target for both runtime and migrations. Migration 0003 creates the pgvector extension; if that fails, the `&&` startup chain prevents Uvicorn from starting. The 3-second application connect timeout and the non-verifying `ssl=require` mode are recorded risks; the timeout change is a proposal only and was not applied. All live Neon actions remain unexecuted.
