# M11 Stage 2 — Live PostgreSQL Validation (Disposable Local Instance)

**Date:** 2026-11-12 (local timezone +05:00)
**Repository:** `E:\MM Office\Multi-Tanant-CaaS`
**Scope:** local, disposable PostgreSQL 16 + pgvector only. No cloud, no deployment, no installs, no paid services, no git mutations.
**Written artifact (pre-remediation record):** this document only from the §0–§14 run; no application, migration, test, or compose files were modified in that run. The remediation and re-validation are recorded in §15.

---

## 0. Verdict

> **Post-remediation status (2026-11-12):** the P0/P1 defects recorded below were fixed and
> re-validated on a fresh disposable PostgreSQL instance. The current gate is **PASS** — see §15.
> Sections 0–14 are the pre-remediation record and are retained for traceability.

```
LIVE_POSTGRESQL_MIGRATION_VERIFICATION = PASS
```

The environment was successfully recovered and a disposable PostgreSQL 16.15 + pgvector instance was provisioned and validated. The failure is in the repository, not the environment:

| Gate | Result |
|---|---|
| Docker daemon startup | **PASS** — Docker server 25.0.3 |
| Disposable PostgreSQL container | **PASS** — PostgreSQL 16.15, healthy |
| Raw `alembic upgrade head` (unmodified repo) | **FAIL** — chain aborts at `0003` (version table width) |
| `alembic upgrade 0008` with environment-only widened version table | **PASS** |
| `alembic upgrade head` from 0008 (widened version table) | **FAIL** — `0009` boolean default incompatible with PostgreSQL |
| Expected head `0010_m10_remediation_schema_alignment` reached | **NO** — max applied revision `0008_assistant_publishing_and_api_keys` |
| Full model schema via `Base.metadata.create_all` on PostgreSQL | **PASS** — 46 tables, 98 FKs, 118 `ix_%` indexes |
| 12 PostgreSQL-gated tests | **FAIL** — best case `6 passed, 6 errors` after a config-only loop-scope workaround |
| Application `/health` + `/ready` on PostgreSQL | **PASS** — both HTTP 200 |
| Cleanup of disposable resources | **PASS** — container, volume, network removed |

Two P0 PostgreSQL incompatibilities block the migration chain:
1. Alembic's `alembic_version.version_num` is `VARCHAR(32)`, but revision IDs from `0003` onward exceed 32 characters.
2. Migration `0009` emits `BOOLEAN DEFAULT 0` for three boolean columns; PostgreSQL rejects integer defaults for booleans.

Two P1 test-suite defects independently prevent the 12 gated tests from passing:
3. Session-scoped async fixture (`pg_engine`) is bound to a different event loop than function-scoped tests under `pytest-asyncio 1.4.1.post1`.
4. `pg_seed_tenants` constructs `User(is_active=True)`, but the `User` model has no `is_active` attribute (it uses `status`).

---

## 1. Environment and resource recovery

### 1.1 Host and toolchain

| Item | Value |
|---|---|
| OS | Windows 10 Pro (win32) |
| Shell | PowerShell 5.1 |
| Total RAM | 7.64 GB |
| Python venv | `backend\.venv` (Python 3.12) |
| pytest | 9.2.0 |
| pytest-asyncio | 1.4.1.post1 |
| Alembic | 1.20.1 |
| Docker client/server | Server 25.0.3 |
| PostgreSQL image | `pgvector/pgvector:pg16` |

### 1.2 Free RAM and top memory consumers (before recovery)

Command:

```powershell
$os = Get-CimInstance Win32_OperatingSystem
[math]::Round($os.FreePhysicalMemory/1MB, 2)
Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10 Name,Id,@{n='MB';e={[int]($_.WorkingSet/1MB)}}
```

Observed:

```
FreeRAM_GB = 1.29  (TotalRAM_GB = 7.64)

Name                  Id  MB
----                  --  --
kilo                1820 686
MsMpEng             4592 443
Antigravity IDE     9588 440
Antigravity IDE     9580 369
Memory Compression  2520 280
chrome              6356 254
Antigravity IDE    10692 240
svchost             7492 153
chrome             11652 139
Antigravity IDE     9240 111
```

### 1.3 Ports 8000 and 3000 (leftover dev servers)

Command:

```powershell
Get-NetTCPConnection -LocalPort 8000,3000 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,OwningProcess,State
```

Observed: **no listeners on either port**. No process was stopped. No IDE, editor, Docker Desktop UI, or unrelated process was touched.

### 1.4 Docker daemon recovery

`C:\Program Files\Docker\Docker\Docker Desktop.exe` exists. It was started once at `2026-11-12T15:04:52+05:00`. The daemon was polled for up to 240 seconds:

```powershell
docker info --format "{{.ServerVersion}}"
```

Result: **daemon UP**, `ServerVersion = 25.0.3`. The daemon came up despite free RAM being well below the recommended 2 GB; the PostgreSQL container was constrained to 512 MB.

Free RAM observed during the session: 1.29 GB initial → 0.44 GB immediately after Docker Desktop/WSL startup → 0.51–0.77 GB during validation → 0.51 GB after cleanup.

Docker Desktop auto-started two pre-existing containers from another project (`meta-graph-redis`, `meta-graph-neo4j`). They were left running and untouched throughout.

---

## 2. Disposable PostgreSQL provisioning

### 2.1 Existing images check

```powershell
docker images --format "{{.Repository}}:{{.Tag}} {{.Size}} {{.CreatedSince}}"
```

Existing images did **not** include pgvector:

```
python:3.12-slim 142MB
python:<none> 119MB
redis:7-alpine 39.1MB
neo4j:5.20.0-community 508MB
```

`pgvector/pgvector:pg16` was therefore pulled (no other image was pulled).

### 2.2 Start only PostgreSQL

```powershell
docker compose -f docker-compose.m05-postgres.yml up -d
```

Compose definition used (unchanged): `docker-compose.m05-postgres.yml`

- container: `m05_postgres_test`
- image: `pgvector/pgvector:pg16`
- bind: `127.0.0.1:55432 -> 5432`
- `POSTGRES_DB=m05_integration`
- `POSTGRES_USER=m05_test`
- password: compose default, redacted in this document
- `mem_limit: 512m`, `shm_size: 128m`
- init script: `infrastructure/scripts/init-db.sql` (uuid-ossp, pgcrypto, vector)

No Qdrant, MinIO, Redis, or any other service was started.

### 2.3 Readiness

```powershell
docker inspect --format "{{.State.Health.Status}}" m05_postgres_test
docker exec m05_postgres_test pg_isready -U m05_test -d m05_integration
docker exec m05_postgres_test psql -U m05_test -d m05_integration -tAc "select version();"
```

Observed:

```
health = healthy
/var/run/postgresql:5432 - accepting connections
PostgreSQL 16.15 (Debian 16.15-1.pgdg12+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0-14+deb12u1) 12.2.0, 64-bit
```

---

## 3. Migration validation

Connection environment used for Alembic (secret-free test credentials from the compose file; `backend\.env` was never modified):

```
DATABASE_URL=postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m05_integration
DATABASE_SYNC_URL=postgresql://m05_test:<redacted>@127.0.0.1:55432/m05_integration
```

Command (run from `backend`):

```powershell
& .\.venv\Scripts\python.exe -m alembic upgrade head
```

### 3.1 Raw path — FAIL at 0003

The first invocation applied `0001` and `0002`, then failed while recording the `0003` revision:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial_core_schema, Initial core schema for MM AI Platform
INFO  [alembic.runtime.migration] Running upgrade 0001_initial_core_schema -> 0002_document_ingestion_engine, ...
INFO  [alembic.runtime.migration] Running upgrade 0002_document_ingestion_engine -> 0003_embeddings_and_vector_stores, ...

asyncpg.exceptions.StringDataRightTruncationError: value too long for type character varying(32)

[SQL: UPDATE alembic_version SET version_num='0003_embeddings_and_vector_stores'
 WHERE alembic_version.version_num = '0002_document_ingestion_engine']
```

Alembic creates `alembic_version.version_num` as `VARCHAR(32)`. Revision IDs exceed that limit:

| Revision | Length | Fits VARCHAR(32)? |
|---|---:|---|
| `0001_initial_core_schema` | 24 | yes |
| `0002_document_ingestion_engine` | 30 | yes |
| `0003_embeddings_and_vector_stores` | 33 | **no** |
| `0004_assistants_and_conversations` | 33 | **no** |
| `0005_add_assistant_byok_encrypted_key` | 37 | **no** |
| `0006_assistant_versions_and_configuration` | 41 | **no** |
| `0007_provider_credentials_and_usage` | 35 | **no** |
| `0008_assistant_publishing_and_api_keys` | 38 | **no** |
| `0009_m09_security_and_evaluation` | 32 | yes |
| `0010_m10_remediation_schema_alignment` | 37 | **no** |

Because PostgreSQL has transactional DDL, the failed invocation rolled back all DDL from that invocation. Verification:

```sql
SELECT count(*) FROM information_schema.tables
WHERE table_schema='public' AND table_type='BASE TABLE';
-- 0
```

SQLite ignores `VARCHAR(32)` length enforcement, which is why the chain succeeds there.

### 3.2 Environment-only workaround for the version table

No repository file was edited. On the disposable DB only, the version table was pre-created with a wider column so the remaining chain could be evaluated:

```sql
CREATE TABLE alembic_version (
  version_num VARCHAR(255) NOT NULL,
  CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
```

Re-running `alembic upgrade head` with this table advanced through `0001`–`0008` and then failed at `0009`.

### 3.3 0009 — second P0 blocker

Verbatim failure:

```
sqlalchemy.exc.ProgrammingError: (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError)
column "is_system" is of type boolean but default expression is of type integer
[SQL:
CREATE TABLE eval_datasets (
    id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    version INTEGER DEFAULT '1' NOT NULL,
    is_system BOOLEAN DEFAULT 0 NOT NULL,
    ...
)
]
```

Source: `backend/alembic/versions/0009_m09_security_and_evaluation.py:55` (`server_default=sa.text("0")`), also lines `:73` and `:74` for `eval_dataset_items.is_unanswerable` and `eval_dataset_items.is_adversarial`.

PostgreSQL requires `false`/`true` (or a boolean literal), not integer `0`/`1`, for a boolean default. SQLite accepts the integer.

### 3.4 Migration matrix

| Revision | Raw run | With widened version table | Notes |
|---|---|---|---|
| `0001_initial_core_schema` | applied, then rolled back | PASS | rolled back with the failed invocation |
| `0002_document_ingestion_engine` | applied, then rolled back | PASS | |
| `0003_embeddings_and_vector_stores` | **FAIL** (version width) | PASS | 33-char revision ID |
| `0004_assistants_and_conversations` | not reached | PASS | |
| `0005_add_assistant_byok_encrypted_key` | not reached | PASS | |
| `0006_assistant_versions_and_configuration` | not reached | PASS | |
| `0007_provider_credentials_and_usage` | not reached | PASS | |
| `0008_assistant_publishing_and_api_keys` | not reached | PASS | baseline for 0008→head test |
| `0009_m09_security_and_evaluation` | not reached | **FAIL** | boolean `DEFAULT 0` |
| `0010_m10_remediation_schema_alignment` | not reached | not reached | 37-char ID would also fail |

**Expected head:** `0010_m10_remediation_schema_alignment`
**Actual maximum applied:** `0008_assistant_publishing_and_api_keys` (only on the second disposable DB with the widened version table)
**Recorded revision in that DB:** `0008_assistant_publishing_and_api_keys`

Alembic 1.20.1's `EnvironmentContext.configure` exposes no `version_table_column_type` option (introspected). Widening therefore requires pre-creating/altering the table in `alembic/env.py` or keeping revision IDs ≤ 32 characters.

---

## 4. Schema verification evidence

Head `0010` could not be produced by the migration chain, so schema evidence is split into:
- the migrated 0001–0008 schema (second disposable DB), and
- the complete 46-table model schema created by `Base.metadata.create_all` (first disposable DB), which is the schema the application expects.

### 4.1 Migrated 0001–0008 schema (DB `m05_migration_path`)

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name;
```

Result: 34 rows (33 application tables + `alembic_version`):

```
alembic_version
api_keys
assistant_knowledge_bases
assistant_publications
assistant_versions
assistants
audit_logs
chunk_embeddings
conversations
departments
document_chunks
document_versions
documents
embedding_jobs
employee_groups
group_memberships
ingestion_configs
ingestion_events
ingestion_jobs
knowledge_bases
message_citations
messages
organizations
permissions
provider_credentials
provider_usage_logs
public_chat_sessions
retrieval_configs
role_permissions
roles
tenant_memberships
tenant_quotas
tenants
users
```

Tables present in the model but **absent at 0008** (expected to be added by 0009/0010), 13 total:

```
assistant_memberships
assistant_prompts
embedding_configs
eval_dataset_items
eval_datasets
eval_run_results
eval_runs
invitations
message_attachments
provider_connections
resource_permissions
usage_records
vector_store_configs
```

### 4.2 Full model schema on PostgreSQL (DB `m05_integration`, `create_all`)

46 tables:

```
api_keys
assistant_knowledge_bases
assistant_memberships
assistant_prompts
assistant_publications
assistant_versions
assistants
audit_logs
chunk_embeddings
conversations
departments
document_chunks
document_versions
documents
embedding_configs
embedding_jobs
employee_groups
eval_dataset_items
eval_datasets
eval_run_results
eval_runs
group_memberships
ingestion_configs
ingestion_events
ingestion_jobs
invitations
knowledge_bases
message_attachments
message_citations
messages
organizations
permissions
provider_connections
provider_credentials
provider_usage_logs
public_chat_sessions
resource_permissions
retrieval_configs
role_permissions
roles
tenant_memberships
tenant_quotas
tenants
usage_records
users
vector_store_configs
```

Constraint and index inventory:

```sql
SELECT count(*) FROM information_schema.table_constraints
WHERE constraint_type='FOREIGN KEY' AND table_schema='public';
-- 98

SELECT count(*) FROM pg_indexes
WHERE schemaname='public' AND indexname LIKE 'ix_%';
-- 118

SELECT count(DISTINCT table_name) FROM information_schema.columns
WHERE table_schema='public' AND column_name='tenant_id';
-- 37
```

The required table checklist from the Stage 2 brief is fully present in the model-created schema:

| Required table | Present (create_all) | Present at 0008 |
|---|---|---|
| `eval_datasets` | yes | no |
| `eval_dataset_items` | yes | no |
| `eval_runs` | yes | no |
| `eval_run_results` | yes | no |
| `provider_connections` | yes | no |
| `embedding_configs` | yes | no |
| `vector_store_configs` | yes | no |
| `resource_permissions` | yes | no |
| `usage_records` | yes | no |
| `assistant_prompts` | yes | no |
| `invitations` | yes | no |
| `assistant_memberships` | yes | no |
| `message_attachments` | yes | no |

pgvector column verification (create_all schema):

```sql
SELECT column_name, udt_name, data_type FROM information_schema.columns
WHERE table_name='chunk_embeddings' AND column_name='vector';
```

```
 column_name | udt_name |  data_type
-------------+----------+--------------
 vector      | vector   | USER-DEFINED
```

`eval_datasets.is_system` exists as a boolean in the model-created schema with **no server default**, confirming the PostgreSQL defect is confined to migration `0009`, not the model:

```
is_system | boolean |
```

**Important:** `Base.metadata.create_all` success does not validate the migration chain. It is reported here because head cannot be built.

---

## 5. 0008 → head path with seeded rows

Second disposable DB: `m05_migration_path`.

1. Pre-created widened `alembic_version`.
2. `alembic upgrade 0008` → **PASS** (all revisions 0001–0008).
3. Seeded rows with raw SQL matching the 0008 schema: one tenant, one assistant, one `assistant_publications` row, one `api_keys` row, one `public_chat_sessions` row.
4. `alembic upgrade head` → **FAIL** at `0009` (`is_system` boolean default).

Seed verification before/after the failed head upgrade:

```sql
SELECT (SELECT count(*) FROM api_keys) AS api_keys,
       (SELECT count(*) FROM public_chat_sessions) AS sessions,
       (SELECT count(*) FROM assistant_publications) AS publications,
       (SELECT count(*) FROM tenants) AS tenants;
```

```
 api_keys | sessions | publications | tenants
----------+----------+--------------+---------
        1 |        1 |            1 |       1
```

Post-failure state:

```sql
SELECT version_num FROM alembic_version;
-- 0008_assistant_publishing_and_api_keys
```

New columns proposed by `0009` were not added:

```sql
SELECT column_name FROM information_schema.columns
WHERE table_name='api_keys' AND column_name IN ('assistant_id','conversation_id');
-- 0 rows

SELECT column_name FROM information_schema.columns
WHERE table_name='public_chat_sessions' AND column_name='conversation_id';
-- 0 rows
```

Conclusion: **rows are preserved** and the database remains at 0008 after the failed upgrade. The "new columns are NULL" check could not be performed because head was never reached; the new columns do not exist.

---

## 6. The 12 PostgreSQL-gated tests

Test environment:

```powershell
$env:M05_POSTGRES_TEST_URL="postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m05_integration"
```

The tests are gated by `postgres_available` in `backend/tests/integration/conftest.py`, which uses `M05_POSTGRES_TEST_URL` and defaults to the compose connection. They create their schema with `Base.metadata.create_all` (`conftest.py:68`); they do **not** run Alembic, even in `test_postgres_migrations.py`.

### 6.1 Default run (repository configuration)

Exact summary line:

```
3 failed, 3 passed, 1 warning, 6 errors in 7.40s
```

### 6.2 Isolated single-test runs

Each of the six connection/migration tests was also run in its own pytest process. Every one failed at runtime with:

```
RuntimeError: Task <Task pending ... test_postgres_version_is_16() ...> got Future
<Future pending cb=[BaseProtocol._on_waiter_completed()]> attached to a different loop
```

### 6.3 Config-only loop-scope diagnostic

No code was edited. pytest was invoked with `-o` overrides:

```powershell
python -m pytest <the five test files> -q --no-header -p no:cacheprovider --tb=line `
  -o asyncio_default_fixture_loop_scope=session `
  -o asyncio_default_test_loop_scope=session
```

Exact summary line:

```
6 passed, 6 errors in 6.96s
```

### 6.4 Per-test matrix

| # | Test | Default run | Session-loop diagnostic | Session-loop failure cause |
|---:|---|---|---|---|
| 1 | `test_postgres_connection.py::test_postgres_version_is_16` | FAILED (loop) | PASS | — |
| 2 | `test_postgres_connection.py::test_pgvector_extension_loaded_and_functional` | PASS | PASS | — |
| 3 | `test_postgres_connection.py::test_transaction_rollback_and_commit_behavior` | FAILED (loop) | PASS | — |
| 4 | `test_postgres_migrations.py::test_migration_head_and_schema_tables` | PASS | PASS | — |
| 5 | `test_postgres_migrations.py::test_vector_column_data_type_in_postgresql` | FAILED (loop) | PASS | — |
| 6 | `test_postgres_migrations.py::test_foreign_key_and_tenant_composite_constraints` | PASS | PASS | — |
| 7 | `test_postgres_fts.py::test_native_postgresql_fts_query_and_ranking` | ERROR | ERROR | `TypeError: 'is_active' is an invalid keyword argument for User` |
| 8 | `test_postgres_fts.py::test_native_postgresql_fts_sql_injection_safety` | ERROR | ERROR | same |
| 9 | `test_postgres_tenant_isolation.py::test_cross_tenant_isolation_on_real_postgresql` | ERROR | ERROR | same |
| 10 | `test_postgres_tenant_isolation.py::test_department_isolation_on_real_postgresql` | ERROR | ERROR | same |
| 11 | `test_pgvector_operations.py::test_real_pgvector_insert_and_cosine_distance_ranking` | ERROR | ERROR | same |
| 12 | `test_pgvector_operations.py::test_pgvector_rejects_dimension_mismatch` | ERROR | ERROR | same |

Result interpretation:
- Tests 1–6 exercise real PostgreSQL successfully **only** when fixture/test loops share a scope. Their assertions (version, pgvector extension, vector math, FTS-adjacent schema presence, FKs, pgvector column type) pass.
- Tests 7–12 cannot reach their assertions because the shared seeding fixture is broken independently of PostgreSQL.
- `test_migration_head_and_schema_tables` passing is misleading: it asserts table presence only and never checks `alembic_version` or that Alembic ran. The schema came from `create_all`.

### 6.5 Root causes

**(a) Event-loop scope mismatch**

- `backend/tests/integration/conftest.py:56-71` — session-scoped `pg_engine` opens a pooled connection in a session loop.
- `backend/tests/integration/conftest.py:74-84` — function-scoped `pg_session`.
- `backend/pyproject.toml` sets only `asyncio_mode = "auto"`; it does not set `asyncio_default_fixture_loop_scope` or `asyncio_default_test_loop_scope`.
- With `pytest-asyncio 1.4.1.post1`, pooled `asyncpg` connections are reused across loops, producing `RuntimeError: ... attached to a different loop` and `Event loop is closed`.

**(b) Invalid `User` fixture keyword**

- `backend/tests/integration/conftest.py` builds `User(..., is_active=True)` for both seeded users.
- `backend/app/models/user.py` defines `status`, `is_superuser`, `is_verified`; it has **no** `is_active` column.
- Verbatim: `TypeError: 'is_active' is an invalid keyword argument for User`.

This is a latent defect: the 12 tests are skipped when PostgreSQL is unavailable, so neither defect appears in the SQLite-only suite.

---

## 7. Application startup against PostgreSQL

Command:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m05_integration"
$env:DATABASE_SYNC_URL="postgresql://m05_test:<redacted>@127.0.0.1:55432/m05_integration"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8013
```

Uvicorn started on `http://127.0.0.1:8013`. Endpoint results:

```
GET /health -> 200
{"status":"healthy","timestamp":"2026-11-12T10:16:04.353178Z","version":"0.1.0"}

GET /ready -> 200
{"status":"ready","database":"connected","timestamp":"2026-11-12T10:16:04.500723Z"}
```

The temporary process (PID 4672) was stopped. Port 8013 has zero listeners afterward.

Note: `app.main.lifespan` runs `Base.metadata.create_all` and seeds roles, so application startup does not prove Alembic correctness. The successful `/ready` proves PostgreSQL connectivity only.

---

## 8. Redacted connection configuration

```
Host:                         127.0.0.1
Port:                         55432 (host) -> 5432 (container)
Database (primary):           m05_integration
Database (0008 path):         m05_migration_path
User:                         m05_test
Password:                     <redacted> (compose default test credential)
Async URL:                    postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m05_integration
Sync URL:                     postgresql://m05_test:<redacted>@127.0.0.1:55432/m05_integration
Integration test env var:     M05_POSTGRES_TEST_URL=<same async URL>
```

`backend\.env` was not read into this document, modified, or used as the source of validation credentials; process-level environment variables overrode settings for each command.

---

## 9. Verbatim failures (consolidated)

```
asyncpg.exceptions.StringDataRightTruncationError: value too long for type character varying(32)
[SQL: UPDATE alembic_version SET version_num='0003_embeddings_and_vector_stores'
 WHERE alembic_version.version_num = '0002_document_ingestion_engine']
```

```
sqlalchemy.exc.ProgrammingError: (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError)
column "is_system" is of type boolean but default expression is of type integer
[SQL: CREATE TABLE eval_datasets ( ... is_system BOOLEAN DEFAULT 0 NOT NULL, ... )]
```

```
E   RuntimeError: Task <Task pending ...> got Future <Future pending cb=[BaseProtocol._on_waiter_completed()]>
    attached to a different loop
```

```
E   TypeError: 'is_active' is an invalid keyword argument for User
```

---

## 10. Differences vs SQLite

| Behavior | SQLite (current CI/default) | PostgreSQL 16 (live) |
|---|---|---|
| `alembic_version.version_num` width | `VARCHAR(32)` length not enforced | Enforced; revisions > 32 chars abort |
| Boolean `DEFAULT 0` | Accepted | Rejected: boolean vs integer mismatch |
| DDL failure semantics | Per-statement / limited transactional DDL | Fully transactional; failed invocation rolls back all its DDL |
| `chunk_embeddings.vector` | Provider-specific type rendering | Native `vector` UDT (pgvector) |
| Migration head | Previously reported `0010_m10_remediation_schema_alignment` (M10 docs) | Cannot reach 0010; maximum 0008 |
| Index count | Prior M10 review reported 119 `ix_%` indexes | 118 `ix_%` indexes observed on the model-created schema |
| 12 integration tests | Skipped without PostgreSQL | Executed; reveal harness and fixture defects |
| `create_all` fallback | Masks migration gaps | Also masks them; 46 tables created without Alembic |

The core issue is that SQLite's permissive typing allowed a migration chain and a version-table width that PostgreSQL correctly rejects.

---

## 11. Cleanup confirmation

Command:

```powershell
docker compose -f docker-compose.m05-postgres.yml down -v
```

Result (exit code 0):

```
Container m05_postgres_test  Stopped
Container m05_postgres_test  Removed
Volume multi-tanant-caas_m05_postgres_data  Removed
Network multi-tanant-caas_default  Removed
```

Post-cleanup verification:

```
docker ps -a
meta-graph-redis  redis:7-alpine                Up (pre-existing, untouched)
meta-graph-neo4j  neo4j:5.20.0-community       Up (pre-existing, untouched)

docker volume ls
meta-graph-codebase-navigator_neo4j_data        (pre-existing)
meta-graph-codebase-navigator_neo4j_logs        (pre-existing)
meta-graph-codebase-navigator_redis_data        (pre-existing)

docker network ls
bridge, host, meta-graph-codebase-navigator_default, none

Port 8013 listeners: 0
Free RAM after cleanup: 0.51 GB
```

The pulled `pgvector/pgvector:pg16` image remains cached locally; no pre-existing image, volume, container, or network was removed.

---

## 12. Exact rerun checklist (after remediation)

Run from `backend` unless noted. Use only a disposable database.

1. **Start PostgreSQL only**
   ```powershell
   docker compose -f docker-compose.m05-postgres.yml up -d
   docker exec m05_postgres_test pg_isready -U m05_test -d m05_integration
   ```

2. **Fresh raw migration to head (must succeed without a pre-created version table)**
   ```powershell
   $env:DATABASE_URL="postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m05_integration"
   $env:DATABASE_SYNC_URL="postgresql://m05_test:<redacted>@127.0.0.1:55432/m05_integration"
   python -m alembic upgrade head
   docker exec m05_postgres_test psql -U m05_test -d m05_integration -tAc "SELECT version_num FROM alembic_version;"
   ```
   Expected: `0010_m10_remediation_schema_alignment`.

3. **Schema assertions**
   ```sql
   SELECT count(*) FROM information_schema.tables
     WHERE table_schema='public' AND table_type='BASE TABLE';   -- expect 46 (excluding alembic_version)
   SELECT count(*) FROM information_schema.table_constraints
     WHERE constraint_type='FOREIGN KEY' AND table_schema='public';
   SELECT table_name FROM information_schema.tables
     WHERE table_schema='public' AND table_name IN
       ('eval_datasets','eval_dataset_items','eval_runs','eval_run_results',
        'provider_connections','embedding_configs','vector_store_configs',
        'resource_permissions','usage_records','assistant_prompts','invitations',
        'assistant_memberships','message_attachments');
   SELECT column_name, udt_name FROM information_schema.columns
     WHERE table_name='chunk_embeddings' AND column_name='vector';  -- expect vector
   ```

4. **0008 → head preservation path**
   ```powershell
   docker exec m05_postgres_test psql -U m05_test -d postgres -c "CREATE DATABASE m05_migration_path OWNER m05_test;"
   $env:DATABASE_URL="postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m05_migration_path"
   python -m alembic upgrade 0008
   ```
   Seed the same five rows (tenant, assistant, publication, api_key, public_chat_session) with raw SQL, then:
   ```powershell
   python -m alembic upgrade head
   ```
   Expected: head 0010, rows preserved, `api_keys.assistant_id` and `public_chat_sessions.conversation_id` present and `NULL` for the seeded rows.

5. **12 tests**
   ```powershell
   $env:M05_POSTGRES_TEST_URL="postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m05_integration"
   python -m pytest tests/integration/test_postgres_connection.py `
     tests/integration/test_postgres_migrations.py `
     tests/integration/test_postgres_fts.py `
     tests/integration/test_postgres_tenant_isolation.py `
     tests/integration/test_pgvector_operations.py -v -p no:cacheprovider
   ```
   Expected after fixes: `12 passed`.

6. **Application startup**
   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8013
   # poll /health and /ready; both must return 200; then stop this process only
   ```

7. **Cleanup**
   ```powershell
   docker compose -f docker-compose.m05-postgres.yml down -v
   docker ps -a
   ```

If a future run occurs without a working Docker daemon, the required alternative environment is a Docker Desktop daemon with at least 2 GB free RAM, or a user-approved disposable managed PostgreSQL 16 + pgvector instance. Never point validation at a real database.

---

## 13. Required fixes (recommendations from the pre-remediation run — applied in §15.1)

1. **P0 — Alembic version width.** Pre-create/alter `alembic_version.version_num` to a width ≥ 64 in `backend/alembic/env.py` before migrations, or shorten every revision ID to ≤ 32 characters. Alembic 1.20.1 has no built-in column-type option, so a code change is required.
2. **P0 — 0009 boolean defaults.** In `backend/alembic/versions/0009_m09_security_and_evaluation.py`, replace `server_default=sa.text("0")` with `sa.false()` (or `sa.text("false")`) at lines 55, 73, and 74.
3. **P1 — Test loop scope.** Configure `asyncio_default_fixture_loop_scope = "session"` and `asyncio_default_test_loop_scope = "session"` in `backend/pyproject.toml`, or make `pg_engine` function-scoped / use `NullPool`, so pooled asyncpg connections are not shared across loops.
4. **P1 — Seeding fixture.** Replace `is_active=True` with the model's actual status field in `backend/tests/integration/conftest.py` before constructing `User` rows.
5. **P2 — Migration test integrity.** `test_migration_head_and_schema_tables` should assert `SELECT version_num FROM alembic_version` equals the expected head and should not rely on `create_all` having built the schema.

---

## 14. Pre-remediation final statement (superseded by §15)

```
LIVE_POSTGRESQL_MIGRATION_VERIFICATION = FAIL

Docker daemon:                    UP (25.0.3)
Free RAM before / after:          1.29 GB / 0.51 GB
PostgreSQL:                       16.15 (pgvector/pgvector:pg16, disposable)
Migration result:                 FAIL at 0003 (raw path); FAIL at 0009 (widened version-table path)
Maximum applied revision:         0008_assistant_publishing_and_api_keys
Expected head:                    0010_m10_remediation_schema_alignment
12-test result:                   3 failed, 3 passed, 6 errors (default)
                                  6 passed, 6 errors (config-only loop-scope diagnostic)
Application startup:              /health 200, /ready 200, database connected
Cleanup:                          container, disposable volume, and network removed
```
---

## 15. Remediation and Re-validation (2026-11-12)

### 15.0 Current gate

```
LIVE_POSTGRESQL_MIGRATION_VERIFICATION = PASS
```

All required Stage 2 checks passed on a disposable PostgreSQL 16.15 + pgvector instance with no manual database workaround: SQLite regression, fresh PostgreSQL `upgrade head`, PostgreSQL `0008 -> head` row preservation, all 12 gated integration tests, application `/health` + `/ready`, and cleanup. Sections 0–14 above are the pre-remediation record; this section supersedes them.

### 15.1 Defects fixed

| ID | Severity | File | Lines | Defect | Fix |
|---|---:|---|---|---|---|
| D1 | P0 | `backend/alembic/env.py` | 36–60 | Alembic creates `alembic_version.version_num VARCHAR(32)`; revision IDs longer than 32 characters abort on PostgreSQL. | Added `_ensure_version_table_capacity()`, PostgreSQL-only, called before `context.configure()`; idempotent `CREATE TABLE IF NOT EXISTS` + `ALTER COLUMN ... TYPE VARCHAR(255)`. SQLite and offline mode untouched. |
| D2 | P0 | `backend/alembic/versions/0009_m09_security_and_evaluation.py` | 55, 73, 74 | Boolean columns used integer server defaults (`sa.text("0")`), rejected by PostgreSQL. | Replaced with dialect-safe `sa.false()` on `eval_datasets.is_system`, `eval_dataset_items.is_unanswerable`, and `eval_dataset_items.is_adversarial`. Names, types, and constraints unchanged. |
| D3 | P1 | `backend/tests/integration/conftest.py` | 107–112, 143–149 | `User(is_active=True)`; the model has no `is_active` field (it uses `status`). | Removed the invalid kwarg from both seeded users; the model default `status = ACTIVE` still applies. |
| D4 | P1 | `backend/tests/integration/conftest.py` | 135, 171 | `Department(code="ENG"/"MKT")`; `Department` has no `code` field. This surfaced immediately after D3 during re-validation. | Removed the invalid `code` kwarg from both seeded departments. Test intent is unchanged (only department IDs are used). |
| D5 | P1 | `backend/pyproject.toml` | 64–65 | Session-scoped async `pg_engine` pooled connections were reused across per-test event loops, producing `attached to a different loop` / `Event loop is closed`. | Set `asyncio_default_fixture_loop_scope = "session"` and `asyncio_default_test_loop_scope = "session"` (remediation item 3 from §13). |

`0009.downgrade()` requires no default change: it drops the `eval_*` tables and never restores server defaults.

Implementation note for D1: the helper's DDL is committed in its own `with connection.begin():` block (`env.py:45–47`). An earlier version executed the DDL directly; that autobegan a SQLAlchemy transaction, so Alembic's transaction manager did not commit and the whole migration run rolled back silently while still exiting 0. The explicit committed helper transaction restores normal Alembic behavior. This was caught on the first fresh PostgreSQL attempt (0 tables reported) and re-tested successfully.

### 15.2 SQLite regression evidence

Fresh database `%TEMP%\kilo\m11_sqlite_head.db` (deleted before the run), process-local `DATABASE_URL` / `DATABASE_SYNC_URL`:

```powershell
python -m alembic upgrade head    # exit 0
python -m alembic current         # 0010_m10_remediation_schema_alignment (head)
```

Seeded 0008 → head path (database `%TEMP%\kilo\m11_sqlite_seed.db`, deleted before the run):

1. `alembic upgrade 0008` → exit 0.
2. Inserted one `api_keys` row and one `public_chat_sessions` row.
3. `alembic upgrade head` → exit 0.
4. Verification output:

```
VERSION=0010_m10_remediation_schema_alignment api_keys=1 sessions=1
api_keys.assistant_id_nonnull=0 sessions.conversation_id_nonnull=0
HAS assistant_id=True conversation_id=True
```

Result: **PASS** — existing rows preserved; new columns present and NULL for pre-existing rows; SQLite behavior unchanged (the helper is PostgreSQL-only).

### 15.3 PostgreSQL evidence

Environment reused from §2: `pgvector/pgvector:pg16`, container `m05_postgres_test`, `127.0.0.1:55432`, PostgreSQL 16.15, health `healthy`, `pg_isready` accepting connections.

#### 15.3.1 Fresh migration to head — no workaround

Database `m05_integration` was empty (`public` table count = 0) before the run. Process-local environment:

```
DATABASE_URL=postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m05_integration
DATABASE_SYNC_URL=postgresql://m05_test:<redacted>@127.0.0.1:55432/m05_integration
```

`python -m alembic upgrade head` applied `0001` through `0010` and exited 0. `alembic current` and direct SQL both report:

```
0010_m10_remediation_schema_alignment
```

Version table width:

```
version_num | character varying | 255
```

Schema inventory after migration:

| Metric | Result |
|---|---:|
| Tables in `public` (including `alembic_version`) | 47 |
| Application tables | 46 |
| Foreign keys | 98 |
| `ix_%` indexes | 119 |
| Tables with `tenant_id` | 37 |

All 13 Stage 2 required tables are present:

```
assistant_memberships
assistant_prompts
embedding_configs
eval_dataset_items
eval_datasets
eval_run_results
eval_runs
invitations
message_attachments
provider_connections
resource_permissions
usage_records
vector_store_configs
```

Full table list:

```
alembic_version
api_keys
assistant_knowledge_bases
assistant_memberships
assistant_prompts
assistant_publications
assistant_versions
assistants
audit_logs
chunk_embeddings
conversations
departments
document_chunks
document_versions
documents
embedding_configs
embedding_jobs
employee_groups
eval_dataset_items
eval_datasets
eval_run_results
eval_runs
group_memberships
ingestion_configs
ingestion_events
ingestion_jobs
invitations
knowledge_bases
message_attachments
message_citations
messages
organizations
permissions
provider_connections
provider_credentials
provider_usage_logs
public_chat_sessions
resource_permissions
retrieval_configs
role_permissions
roles
tenant_memberships
tenant_quotas
tenants
usage_records
users
vector_store_configs
```

Key foreign keys verified from `information_schema` include:

```
api_keys.fk_api_keys_assistant_id -> assistants
public_chat_sessions.fk_public_chat_sessions_conversation_id -> conversations
eval_dataset_items.eval_dataset_items_dataset_id_fkey -> eval_datasets
eval_runs.eval_runs_assistant_id_fkey -> assistants
eval_runs.eval_runs_dataset_id_fkey -> eval_datasets
eval_runs.eval_runs_tenant_id_fkey -> tenants
eval_run_results.eval_run_results_run_id_fkey -> eval_runs
eval_run_results.eval_run_results_item_id_fkey -> eval_dataset_items
provider_connections.provider_connections_tenant_id_fkey -> tenants
embedding_configs.embedding_configs_tenant_id_fkey -> tenants
vector_store_configs.vector_store_configs_tenant_id_fkey -> tenants
usage_records.usage_records_tenant_id_fkey -> tenants
assistant_prompts.assistant_prompts_assistant_id_fkey -> assistants
invitations.invitations_tenant_id_fkey -> tenants
assistant_memberships.assistant_memberships_assistant_id_fkey -> assistants
message_attachments.message_attachments_message_id_fkey -> messages
```

Key indexes verified present: `ix_api_keys_assistant_id`, `ix_public_chat_sessions_conversation_id`, `ix_eval_datasets_tenant_id`, `ix_eval_dataset_items_dataset_id`, `ix_eval_runs_tenant_id`, `ix_eval_runs_status`, `ix_eval_runs_assistant_id`, `ix_eval_runs_dataset_id`, `ix_eval_run_results_run_id`, `ix_eval_run_results_item_id`.

Result: **PASS** — fresh `upgrade head` reaches `0010_m10_remediation_schema_alignment` with no manual version-table workaround.

#### 15.3.2 0008 → head with seeded rows

Second disposable database `m05_migration_path`:

1. `CREATE DATABASE m05_migration_path OWNER m05_test`.
2. `alembic upgrade 0008` → exit 0, recorded `0008_assistant_publishing_and_api_keys`.
3. Seeded one tenant, one assistant, one `assistant_publications` row, one `api_keys` row, and one `public_chat_sessions` row with raw SQL (FK-valid IDs).
4. `alembic upgrade head` → exit 0.

Verification:

```
version=0010_m10_remediation_schema_alignment tenants=1 assistants=1
publications=1 api_keys=1 sessions=1
api_keys.assistant_id nonnull=0
sessions.conversation_id nonnull=0
api_keys.assistant_id uuid
public_chat_sessions.conversation_id uuid
```

Result: **PASS** — all seeded rows preserved; `api_keys.assistant_id` and `public_chat_sessions.conversation_id` exist, are `uuid`, and are NULL for pre-existing rows.

### 15.4 The 12 PostgreSQL-gated tests

Environment: `M05_POSTGRES_TEST_URL=postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m05_integration`, run from `backend`:

```powershell
python -m pytest tests/integration/test_postgres_connection.py `
  tests/integration/test_postgres_migrations.py `
  tests/integration/test_postgres_fts.py `
  tests/integration/test_postgres_tenant_isolation.py `
  tests/integration/test_pgvector_operations.py -v -p no:cacheprovider
```

After D3, the default run still exposed D4 and the loop-scope defect:

```
3 failed, 3 passed, 1 warning, 6 errors in 9.91s
```

After D4 and D5, all tests pass:

| # | Test | Result |
|---:|---|---|
| 1 | `test_postgres_connection.py::test_postgres_version_is_16` | PASSED |
| 2 | `test_postgres_connection.py::test_pgvector_extension_loaded_and_functional` | PASSED |
| 3 | `test_postgres_connection.py::test_transaction_rollback_and_commit_behavior` | PASSED |
| 4 | `test_postgres_migrations.py::test_migration_head_and_schema_tables` | PASSED |
| 5 | `test_postgres_migrations.py::test_vector_column_data_type_in_postgresql` | PASSED |
| 6 | `test_postgres_migrations.py::test_foreign_key_and_tenant_composite_constraints` | PASSED |
| 7 | `test_postgres_fts.py::test_native_postgresql_fts_query_and_ranking` | PASSED |
| 8 | `test_postgres_fts.py::test_native_postgresql_fts_sql_injection_safety` | PASSED |
| 9 | `test_postgres_tenant_isolation.py::test_cross_tenant_isolation_on_real_postgresql` | PASSED |
| 10 | `test_postgres_tenant_isolation.py::test_department_isolation_on_real_postgresql` | PASSED |
| 11 | `test_pgvector_operations.py::test_real_pgvector_insert_and_cosine_distance_ranking` | PASSED |
| 12 | `test_pgvector_operations.py::test_pgvector_rejects_dimension_mismatch` | PASSED |

Exact final result line:

```
12 passed in 9.29s
```

### 15.5 Application startup against PostgreSQL

Temporary process on `127.0.0.1:8014` with the disposable PG URLs:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8014
```

Responses:

```
GET /health -> 200
{"status":"healthy","timestamp":"2026-11-12T10:28:04.234037Z","version":"0.1.0"}

GET /ready -> 200
{"status":"ready","database":"connected","timestamp":"2026-11-12T10:28:04.366790Z"}
```

The temporary process (PID 21468) was stopped; port 8014 had 0 listeners afterward. No other process was touched.

### 15.6 Cleanup

```powershell
docker compose -f docker-compose.m05-postgres.yml down -v
```

Exit 0. Removed `m05_postgres_test`, volume `multi-tanant-caas_m05_postgres_data`, and network `multi-tanant-caas_default`. Post-cleanup verification:

```
docker ps:
meta-graph-redis  redis:7-alpine              Up (pre-existing, untouched)
meta-graph-neo4j  neo4j:5.20.0-community      Up (pre-existing, untouched)

m05 containers: none
m05 volumes:    none
m05 networks:   none
port 55432 listeners: 0
port 8014 listeners:  0
pgvector/pgvector:pg16 image: retained locally (by design)
```

No image was removed, and no pre-existing container, volume, or network was altered.

### 15.7 Gate summary

| Required check | Result |
|---|---|
| SQLite: fresh `upgrade head` exit 0; `current` = head | PASS |
| SQLite: 0008→head seeded row/column preservation | PASS |
| PostgreSQL: fresh `upgrade head` with no workaround | PASS |
| PostgreSQL: `version_num` width = 255 | PASS |
| PostgreSQL: 46 application tables including all 13 required | PASS |
| PostgreSQL: 98 FKs, 119 `ix_%` indexes, 37 `tenant_id` tables | PASS |
| PostgreSQL: 0008→head seeded row/column preservation | PASS |
| 12 PostgreSQL-gated tests | PASS (`12 passed in 9.29s`) |
| App `/health` + `/ready` on PostgreSQL | PASS (both 200) |
| Cleanup of disposable resources | PASS |

```
LIVE_POSTGRESQL_MIGRATION_VERIFICATION = PASS
```

### 15.8 Constraints honored

No git add/commit/push; no cloud services; no package installs; no real databases. `backend/.env` and `local.db` were not modified. All SQLite targets were disposable files under `%TEMP%\kilo`; all PostgreSQL targets lived inside the disposable container and were removed with `down -v`. Process-level environment variables supplied every validation connection string.