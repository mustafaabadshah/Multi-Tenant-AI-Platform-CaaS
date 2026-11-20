# M11 Stage 2 - PostgreSQL Remediation Review and Re-validation

| Field | Value |
|---|---|
| Milestone | M11 continuation - production hardening |
| Stage | 2 - PostgreSQL remediation review and independent re-validation |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Branch | `main` |
| HEAD | `fdb12463a8308d86015cba8d82546faf0f546c8b` |
| Review window (UTC) | 2026-11-12T10:51Z to 2026-11-12T11:04Z |
| Shell | Windows PowerShell 5.1 |
| Backend venv | `backend\.venv\Scripts\python.exe` (Python 3.12.3) |
| Docker server | 25.0.3; disposable `pgvector/pgvector:pg16` |
| Mode | Review + disposable re-validation. No Git mutation, no install, no cloud, no real database. |
| Repository writes | This file only. |

```text
REVIEW_VERDICT = PASS
LIVE_POSTGRESQL_MIGRATION_VERIFICATION = PASS
```

> This report is an independent re-execution. It does not rely on the prior claims in
> `docs/m11/M11_STAGE_2_POSTGRESQL_VALIDATION.md`; that historical document is referenced
> and preserved unchanged in Section 9.

---

## 1. Scope and disposable resources

The review verified the four uncommitted remediation files from the working tree, then
re-ran the SQLite and PostgreSQL gates with disposable targets only.

| Resource | Value |
|---|---|
| Docker image | `pgvector/pgvector:pg16` (`31c6867f8fd3`), retained |
| PostgreSQL container | `m05_postgres_test` from `docker-compose.m05-postgres.yml` |
| Compose project | `multi-tanant-caas` |
| PostgreSQL server | 16.15 (Debian 16.15-1.pgdg12+2) |
| Bind address | `127.0.0.1:55432` |
| SQLite files | `C:\Users\MUSTAF~1\AppData\Local\Temp\kilo\m11s2\*.db` |
| PostgreSQL databases created | `m11_s2_fresh`, `m11_s2_upgrade`, `m11_s2_tests`, `m11_s2_legacy` |
| PostgreSQL integration target | `m05_integration` (the database name hardcoded by the test suite) |

Unrelated containers `meta-graph-redis` and `meta-graph-neo4j` were running before this
stage and were never touched.

Constraints honored:

- No `git add`, `commit`, `push`, `fetch`, `pull`, `branch`, `stash`, `reset`, `checkout`,
  `restore`, `clean`, or `rm`.
- No package installation.
- No cloud service, real database, or production credential.
- No source edit. Only this report was added.
- At most one PostgreSQL container existed at any time; it was stopped and removed at the
  end (Section 8).

---

## 2. Actual diff review

### 2.1 Command and diff stat

Command run from the repository root:

```powershell
git diff -- backend/alembic/env.py backend/alembic/versions/0009_m09_security_and_evaluation.py backend/tests/integration/conftest.py backend/pyproject.toml
```

All four files are tracked and all four show a working-tree diff. Exact stat:

```text
 backend/alembic/env.py                             | 24 ++++++++++++++++++++++
 .../versions/0009_m09_security_and_evaluation.py   |  6 +++---
 backend/pyproject.toml                             |  2 ++
 backend/tests/integration/conftest.py              |  4 ----
 4 files changed, 29 insertions(+), 7 deletions(-)
```

`git diff --check` exit code `0`. The only output was Git's line-ending notice
(`LF will be replaced by CRLF`), which is not a content change.

| File | Hunk | Current working-tree lines | Expected change | Verdict |
|---|---|---|---|---|
| `backend/alembic/env.py` | `@@ -33,0 +36,22 @@ def run_migrations_offline` | 36-55 helper; 59-60 call | PostgreSQL version-table widening helper before `context.configure` | PRESENT, CORRECT |
| `backend/alembic/versions/0009_m09_security_and_evaluation.py` | `@@ -55 +55 @@` | 55 | `is_system` default `sa.text("0")` -> `sa.false()` | PRESENT, CORRECT |
| `backend/alembic/versions/0009_m09_security_and_evaluation.py` | `@@ -73,2 +73,2 @@` | 73-74 | `is_unanswerable`, `is_adversarial` -> `sa.false()` | PRESENT, CORRECT |
| `backend/tests/integration/conftest.py` | `@@ -112 +111,0 @@`, `@@ -140 +138,0 @@`, `@@ -150 +147,0 @@`, `@@ -178 +174,0 @@` | after 111, 138, 147, 174 | Remove invalid `is_active` / `code` kwargs | PRESENT, CORRECT |
| `backend/pyproject.toml` | `@@ -63,0 +64,2 @@ asyncio_mode = "auto"` | 64-65 | Session-scoped asyncio loop defaults | PRESENT, CORRECT |

### 2.2 `backend/alembic/env.py` - version-table capacity helper

The helper is at lines 36-55 and the call site is at lines 59-60:

```python
36: def _ensure_version_table_capacity(connection: Connection) -> None:
37:     """Widen alembic_version.version_num on PostgreSQL.
...
43:     if connection.dialect.name != "postgresql":
44:         return
45:     # Commit this DDL immediately so Alembic's own migration transaction still owns
46:     # (and commits) the migration work instead of inheriting an implicit transaction.
47:     with connection.begin():
48:         connection.exec_driver_sql(
49:             "CREATE TABLE IF NOT EXISTS alembic_version ("
50:             "version_num VARCHAR(255) NOT NULL, "
51:             "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
52:         )
53:         connection.exec_driver_sql(
54:             "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
55:         )
...
58: def do_run_migrations(connection: Connection) -> None:
59:     # Must run before context.configure so Alembic finds a sufficiently wide version table.
60:     _ensure_version_table_capacity(connection)
61:     context.configure(
62:         connection=connection,
63:         target_metadata=target_metadata,
64:         render_as_batch=True,
65:     )
66:     with context.begin_transaction():
67:         context.run_migrations()
```

`Connection` is imported at `backend/alembic/env.py:5`, so the annotation resolves.
The helper is called before `context.configure` and before
`context.begin_transaction()` / `context.run_migrations()`.

The offline path (`backend/alembic/env.py:22-33`) is untouched: it does not call the
helper and still uses `run_migrations_offline()`.

### 2.3 `0009_m09_security_and_evaluation.py` - boolean defaults

Exact current lines:

```python
55:         sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
...
73:         sa.Column("is_unanswerable", sa.Boolean(), nullable=False, server_default=sa.false()),
74:         sa.Column("is_adversarial", sa.Boolean(), nullable=False, server_default=sa.false()),
```

A residual scan for `sa.text("0")` in this file returns `0` matches. Names, types,
nullability, and constraint clauses are otherwise unchanged; the diff is 3 insertions and
3 deletions.

### 2.4 `backend/tests/integration/conftest.py` - invalid seeding kwargs removed

The deletion-only diff removes four invalid keyword arguments:

| Fixture object | Current lines | Removed kwarg |
|---|---|---|
| `user_a = User(...)` | 107-112 | `is_active=True` |
| `dept_a = Department(...)` | 135-139 | `code="ENG"` |
| `user_b = User(...)` | 143-148 | `is_active=True` |
| `dept_b = Department(...)` | 171-175 | `code="MKT"` |

Source confirmation that the kwargs were invalid:

- `backend/app/models/user.py:20-22` defines `status`, `is_superuser`, and `is_verified`;
  there is no `is_active` column on `User`.
- `backend/app/models/department.py:18-19` defines `name` and `description`; there is no
  `code` column on `Department`.

Residual scan of the whole conftest for `is_active` or `code=` returns `0` matches. The
diff has 0 insertions and 4 deletions, so test intent, IDs, and assertions are unchanged.

### 2.5 `backend/pyproject.toml` - asyncio loop scope

Exact current lines:

```toml
63: asyncio_mode = "auto"
64: asyncio_default_fixture_loop_scope = "session"
65: asyncio_default_test_loop_scope = "session"
```

The pytest startup banner from the re-validation run confirms both settings were loaded:

```text
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=session, asyncio_default_test_loop_scope=session
```

### 2.6 No unexpected working-tree change

`git status --porcelain` before and after the re-validation contains the same four modified
tracked files and the same pre-existing untracked documentation set. No fifth source file,
deletion, or staged entry exists. The four diffs are exactly the reported remediation.

---

## 3. `env.py` risk assessment

| Risk area | Assessment | Evidence |
|---|---|---|
| DDL ordering | SAFE | Helper runs at line 60, before `context.configure` (61-65) and `context.run_migrations()` (67). Fresh PostgreSQL reached head with no workaround. |
| Version-row integrity | SAFE | The helper creates/widens an empty version table and commits only that DDL. Alembic then writes revision rows inside its own `context.begin_transaction()`; the fresh run recorded exactly one row at `0010` (37 chars). |
| PostgreSQL-only guard | SAFE | `connection.dialect.name != "postgresql"` returns at lines 43-44. SQLite fresh and 0008->head runs completed with no helper DDL. |
| Idempotence | SAFE | `CREATE TABLE IF NOT EXISTS` plus `ALTER COLUMN ... TYPE VARCHAR(255)`. A second `alembic upgrade head` on the widened legacy database exited 0 with no migration work. |
| Legacy 32 -> 255 widening | SAFE, DIRECTLY TESTED | Simulated database at `0002` with `version_num VARCHAR(32)`; one `alembic upgrade head` widened it to `character varying(255)` and reached `0010` (Section 5.3). |
| Own transaction vs Alembic transaction | SAFE | `with connection.begin()` commits only the helper DDL before Alembic starts its migration transaction. All ten revisions applied and committed; Alembic's version row is consistent with the schema. |
| Offline mode | UNCHANGED | `run_migrations_offline()` (lines 22-33) does not call the helper. The remediation applies to online migrations only; this is a pre-existing limitation, not a regression. |
| SQLite behavior | UNCHANGED | Guard returns before any SQL. SQLite stores the 37-char revision despite its declared `VARCHAR(32)` because SQLite does not enforce length. |
| Pooling | NO CHANGE | `poolclass=pool.NullPool` at line 81 is unchanged; the helper uses the same connection and does not alter pool configuration. |
| Connection handling | SAFE | `connection.begin()` opens and closes its own transaction; `connectable.dispose()` still runs at line 87. No warning or leak was observed. |
| Locking / permissions | LOW | `ALTER TABLE` takes the normal PostgreSQL DDL lock on a one-row table. The migration role already needs DDL privileges; no new privilege class is required. |
| Downgrade | LOW, UNCHANGED | No downgrade function was changed. The helper is direction-agnostic and runs before both upgrade and downgrade; it only ensures the version column can hold the revision ID. Downgrade was not executed because no downgrade behavior changed. |
| Test isolation | LOW, OBSERVED | Global session-scoped asyncio loops change loop lifetime for the whole backend suite. The 12 gated tests pass; the broader unit suite was not part of this gate. The shared seed fixture commits rows by design. |

No introduced defect was found in ordering, pooling, SQLite behavior, or downgrade. The
only behavioral expander is the global pytest loop-scope setting, which is required by the
gated suite and is discussed further in Section 10.

---

## 4. SQLite gate

All SQLite targets were disposable files under `%TEMP%\kilo\m11s2`.

### 4.1 Fresh database

Commands (from `backend`, with process-local environment):

```powershell
$env:DATABASE_URL="sqlite+aiosqlite:///C:/Users/MUSTAF~1/AppData/Local/Temp/kilo/m11s2/sqlite_fresh.db"
$env:DATABASE_SYNC_URL="sqlite:///C:/Users/MUSTAF~1/AppData/Local/Temp/kilo/m11s2/sqlite_fresh.db"
python -m alembic upgrade head
python -m alembic current
```

The database was deleted first. Results:

```text
upgrade head: EXIT=0
0001_initial_core_schema
0002_document_ingestion_engine
0003_embeddings_and_vector_stores
0004_assistants_and_conversations
0005_add_assistant_byok_encrypted_key
0006_assistant_versions_and_configuration
0007_provider_credentials_and_usage
0008_assistant_publishing_and_api_keys
0009_m09_security_and_evaluation
0010_m10_remediation_schema_alignment

alembic current: 0010_m10_remediation_schema_alignment (head)
version row: ('0010_m10_remediation_schema_alignment', 37)
table count: 47
```

Boolean defaults and new columns (read from `pragma_table_info`):

```text
eval_datasets.is_system                 dflt_value = '0'
eval_dataset_items.is_unanswerable      dflt_value = '0'
eval_dataset_items.is_adversarial       dflt_value = '0'
api_keys.assistant_id                   present
public_chat_sessions.conversation_id    present
```

Result: **PASS**.

### 4.2 Seeded 0008 -> head preservation

A second disposable SQLite database was upgraded to `0008`, seeded, then upgraded to head.

Seed contents (raw SQL, FK-valid IDs):

- 1 tenant, 1 assistant, 1 assistant publication (supporting parents).
- 2 `api_keys` rows.
- 2 `public_chat_sessions` rows.
- 1 `tenant_quotas` row.

Before the head upgrade:

```text
SEEDED (api_keys=2, public_chat_sessions=2, tenant_quotas=1, assistant_publications=1)
alembic version: 0008_assistant_publishing_and_api_keys
```

`alembic upgrade head` exit code `0`; `alembic current` reported
`0010_m10_remediation_schema_alignment (head)`.

After the head upgrade:

```text
VERSION ('0010_m10_remediation_schema_alignment', 37)
ROWS (api_keys=2, public_chat_sessions=2, tenant_quotas=1,
      assistant_publications=1, tenants=1, assistants=1)
API_KEYS_NULL (rows=2, assistant_id_nonnull=0)
SESSIONS_NULL (rows=2, conversation_id_nonnull=0)
api_keys.assistant_id type: CHAR(32)
public_chat_sessions.conversation_id type: CHAR(32)
tenant_quotas.daily_request_limit after 0010: absent
```

Result: **PASS** - rows survived, new columns exist and are NULL for pre-existing rows,
and migration `0010` removed the obsolete quota column as designed.

---

## 5. PostgreSQL gate

### 5.1 Environment

The project's existing disposable `m05_postgres_test` container was reused. It is the
compose service `m05-postgres` from `docker-compose.m05-postgres.yml` in project
`multi-tanant-caas`, running `pgvector/pgvector:pg16` on `127.0.0.1:55432`. Server:
PostgreSQL 16.15. No unrelated container was inspected beyond the read-only `docker ps`.

### 5.2 Fresh database: `m11_s2_fresh`

No manual version-table workaround was applied. The database was empty before the run.

```powershell
$env:DATABASE_URL="postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m11_s2_fresh"
$env:DATABASE_SYNC_URL="postgresql://m05_test:<redacted>@127.0.0.1:55432/m11_s2_fresh"
python -m alembic upgrade head
```

Result:

```text
EXIT=0
Running upgrade  -> 0001_initial_core_schema
Running upgrade 0001_initial_core_schema -> 0002_document_ingestion_engine
Running upgrade 0002_document_ingestion_engine -> 0003_embeddings_and_vector_stores
Running upgrade 0003_embeddings_and_vector_stores -> 0004_assistants_and_conversations
Running upgrade 0004_assistants_and_conversations -> 0005_add_assistant_byok_encrypted_key
Running upgrade 0005_add_assistant_byok_encrypted_key -> 0006_assistant_versions_and_configuration
Running upgrade 0006_assistant_versions_and_configuration -> 0007_provider_credentials_and_usage
Running upgrade 0007_provider_credentials_and_usage -> 0008_assistant_publishing_and_api_keys
Running upgrade 0008_assistant_publishing_and_api_keys -> 0009_m09_security_and_evaluation
Running upgrade 0009_m09_security_and_evaluation -> 0010_m10_remediation_schema_alignment

alembic current: 0010_m10_remediation_schema_alignment (head)
version row: ('0010_m10_remediation_schema_alignment', 37)
```

Version column type:

```text
version_num|character varying|255
```

Boolean defaults:

```text
eval_dataset_items|is_adversarial|false
eval_dataset_items|is_unanswerable|false
eval_datasets|is_system|false
```

Schema inventory:

```text
tables=47          (46 application tables + alembic_version)
fks=98
ix_indexes=119
tenant_tables=37
```

All 13 expected tables are present:

```text
assistant_memberships|PRESENT
assistant_prompts|PRESENT
embedding_configs|PRESENT
eval_dataset_items|PRESENT
eval_datasets|PRESENT
eval_run_results|PRESENT
eval_runs|PRESENT
invitations|PRESENT
message_attachments|PRESENT
provider_connections|PRESENT
resource_permissions|PRESENT
usage_records|PRESENT
vector_store_configs|PRESENT
```

Full table list:

```text
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

Sample foreign-key checks:

```text
fk_api_keys_assistant_id|api_keys.assistant_id->assistants
fk_public_chat_sessions_conversation_id|public_chat_sessions.conversation_id->conversations
eval_runs_tenant_id_fkey|eval_runs.tenant_id->tenants
eval_runs_assistant_id_fkey|eval_runs.assistant_id->assistants
eval_runs_dataset_id_fkey|eval_runs.dataset_id->eval_datasets
eval_run_results_run_id_fkey|eval_run_results.run_id->eval_runs
eval_run_results_item_id_fkey|eval_run_results.item_id->eval_dataset_items
provider_connections_tenant_id_fkey|provider_connections.tenant_id->tenants
usage_records_tenant_id_fkey|usage_records.tenant_id->tenants
invitations_tenant_id_fkey|invitations.tenant_id->tenants
assistant_memberships_assistant_id_fkey|assistant_memberships.assistant_id->assistants
message_attachments_message_id_fkey|message_attachments.message_id->messages
```

Required indexes, all present:

```text
ix_api_keys_assistant_id
ix_eval_dataset_items_dataset_id
ix_eval_datasets_tenant_id
ix_eval_run_results_item_id
ix_eval_run_results_run_id
ix_eval_runs_assistant_id
ix_eval_runs_dataset_id
ix_eval_runs_status
ix_eval_runs_tenant_id
ix_public_chat_sessions_conversation_id
```

Result: **PASS** - fresh `upgrade head` reached `0010` with no workaround; version column is
255 wide; all three boolean defaults are `false`; schema is complete.

### 5.3 Legacy 32 -> 255 widening and idempotence: `m11_s2_legacy`

To exercise the widening branch directly, a disposable database was migrated to `0002`,
then its version column was narrowed to simulate a database written by stock Alembic before
the fix:

```text
ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(32);
BEFORE|0002_document_ingestion_engine|len=30|type=character varying(32)
```

This narrowing was test setup, not a workaround used by the fresh run. Without any manual
widening, `alembic upgrade head` then produced:

```text
EXIT=0
Running upgrade 0002_document_ingestion_engine -> 0003_embeddings_and_vector_stores
... (0004 through 0010)
AFTER|0010_m10_remediation_schema_alignment|len=37|type=character varying(255)
tables=47
bool_defaults=eval_dataset_items.is_adversarial=false, eval_dataset_items.is_unanswerable=false, eval_datasets.is_system=false
```

A second `alembic upgrade head` on the same database exited `0` and applied no revisions,
confirming idempotence of the `IF NOT EXISTS` / `ALTER ... TYPE VARCHAR(255)` pair.

Result: **PASS**.

### 5.4 Seeded 0008 -> head preservation: `m11_s2_upgrade`

A second disposable database was upgraded to `0008`, seeded, then upgraded to head.

Seed contents (raw SQL, FK-valid UUIDs):

- 1 tenant, 1 assistant, 1 assistant publication (supporting parents).
- 2 `api_keys` rows.
- 2 `public_chat_sessions` rows.
- 1 `tenant_quotas` row.

Before the head upgrade:

```text
SEEDED|tenants=1|assistants=1|publications=1|api_keys=2|sessions=2|quotas=1|version=0008_assistant_publishing_and_api_keys
```

`alembic upgrade head` exit code `0`; the output applied only `0009` and `0010`.

After the head upgrade:

```text
version=0010_m10_remediation_schema_alignment
counts|tenants=1|assistants=1|publications=1|api_keys=2|sessions=2|quotas=1
api_keys|rows=2|assistant_id_nonnull=0
sessions|rows=2|conversation_id_nonnull=0
quotas|rows=1
api_keys.assistant_id|uuid
public_chat_sessions.conversation_id|uuid
daily_request_limit_present=0
sample|id=44444444-4444-4444-4444-444444444444|name=key-1|assistant_null=true
```

Result: **PASS** - every seeded row survived, the new columns exist with type `uuid`, and
pre-existing rows have NULL in the new columns.

### 5.5 Heads / current consistency

```text
python -m alembic heads   -> 0010_m10_remediation_schema_alignment (head)
m11_s2_fresh current      -> 0010_m10_remediation_schema_alignment (head)
m11_s2_upgrade current    -> 0010_m10_remediation_schema_alignment (head)
m11_s2_legacy version row -> 0010_m10_remediation_schema_alignment (37 chars)
```

The chain has one head and every upgraded database records it. **PASS**.

---

## 6. The 12 PostgreSQL-gated tests

Command (from `backend`):

```powershell
$env:M05_POSTGRES_TEST_URL="postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m05_integration"
python -m pytest `
  tests/integration/test_postgres_connection.py `
  tests/integration/test_postgres_migrations.py `
  tests/integration/test_postgres_tenant_isolation.py `
  tests/integration/test_postgres_fts.py `
  tests/integration/test_pgvector_operations.py `
  -v -p no:cacheprovider
```

The integration conftest reads `M05_POSTGRES_TEST_URL` (`backend/tests/integration/conftest.py:20-24`).
`test_postgres_version_is_16` asserts that `current_database()` is exactly
`m05_integration`, so the canonical target is that database.

| # | Test | Result |
|---|---|---|
| 1 | `tests/integration/test_postgres_connection.py::test_postgres_version_is_16` | PASSED |
| 2 | `tests/integration/test_postgres_connection.py::test_pgvector_extension_loaded_and_functional` | PASSED |
| 3 | `tests/integration/test_postgres_connection.py::test_transaction_rollback_and_commit_behavior` | PASSED |
| 4 | `tests/integration/test_postgres_migrations.py::test_migration_head_and_schema_tables` | PASSED |
| 5 | `tests/integration/test_postgres_migrations.py::test_vector_column_data_type_in_postgresql` | PASSED |
| 6 | `tests/integration/test_postgres_migrations.py::test_foreign_key_and_tenant_composite_constraints` | PASSED |
| 7 | `tests/integration/test_postgres_tenant_isolation.py::test_cross_tenant_isolation_on_real_postgresql` | PASSED |
| 8 | `tests/integration/test_postgres_tenant_isolation.py::test_department_isolation_on_real_postgresql` | PASSED |
| 9 | `tests/integration/test_postgres_fts.py::test_native_postgresql_fts_query_and_ranking` | PASSED |
| 10 | `tests/integration/test_postgres_fts.py::test_native_postgresql_fts_sql_injection_safety` | PASSED |
| 11 | `tests/integration/test_pgvector_operations.py::test_real_pgvector_insert_and_cosine_distance_ranking` | PASSED |
| 12 | `tests/integration/test_pgvector_operations.py::test_pgvector_rejects_dimension_mismatch` | PASSED |

Exact final summary line:

```text
============================= 12 passed in 18.81s =============================
```

Exit code: `0`.

### 6.1 Calibration note (non-gating)

The first attempt pointed the same environment variable at the fresh database
`m11_s2_tests`. Eleven tests passed; test 1 failed because the test hardcodes
`current_database() == "m05_integration"`:

```text
E       AssertionError: assert 'm11_s2_tests' == 'm05_integration'
1 failed, 11 passed in 16.02s
```

This was a test-target naming mismatch, not a migration or application failure. The
canonical run against `m05_integration` passed all 12 tests. The hardcoded database-name
assertion is a pre-existing test brittleness; it is listed in Section 10, not treated as a
remediation defect.

---

## 7. Application startup against PostgreSQL

A temporary Uvicorn process was started on `127.0.0.1:8015` with the fresh PostgreSQL
database:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://m05_test:<redacted>@127.0.0.1:55432/m11_s2_fresh"
$env:DATABASE_SYNC_URL="postgresql://m05_test:<redacted>@127.0.0.1:55432/m11_s2_fresh"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8015
```

Readiness: TCP port 8015 accepted connections; Uvicorn reported
`Uvicorn running on http://127.0.0.1:8015`.

Endpoint results:

```text
GET /health -> 200
{"status":"healthy","timestamp":"2026-11-12T10:59:22.746344Z","version":"0.1.0"}

GET /ready -> 200
{"status":"ready","database":"connected","timestamp":"2026-11-12T10:59:22.884740Z"}
```

Only that Uvicorn process was stopped. Post-stop check: zero listeners on port 8015.

Result: **PASS**.

---

## 8. Cleanup

All four disposable databases were dropped. The project's disposable PostgreSQL stack was
then removed with:

```powershell
docker compose -f docker-compose.m05-postgres.yml down -v
```

Output (exit code `0`):

```text
Container m05_postgres_test  Stopped
Container m05_postgres_test  Removed
Volume multi-tanant-caas_m05_postgres_data  Removed
Network multi-tanant-caas_default  Removed
```

The legacy-widening check required one restart of the same single PG container; it was
stopped and removed by the same command afterward. At no time were two PG containers
running.

Final Docker state:

```text
docker ps:
meta-graph-redis   redis:7-alpine            Up (pre-existing, untouched)
meta-graph-neo4j   neo4j:5.20.0-community    Up (pre-existing, untouched)

m05 containers: 0
m05 volumes:    0
m05 networks:   0
port 55432 LISTEN: none
port 8015 LISTEN:  none
pgvector/pgvector:pg16: retained (31c6867f8fd3)
```

No image, unrelated container, unrelated volume, or unrelated network was removed.
Result: **PASS**.

---

## 9. Preservation of the historical failure record

`docs/m11/M11_STAGE_2_POSTGRESQL_VALIDATION.md` was not edited or rewritten. Its
last-write timestamp remained `2026-11-12T15:30:06.7287332+05:00` throughout this stage.
That document's initial-failure record (the `VARCHAR(32)` version-table failure at `0003`,
the `0009` boolean-default failure, and the six test-fixture/loop-scope errors) remains the
historical record and is referenced here rather than duplicated or altered. This report is
a separate, independently executed re-validation.

The four source fixes remain uncommitted, exactly as found. No source file was modified by
this stage.

---

## 10. Gate summary and residual observations

| Required check | Result |
|---|---|
| Four expected diffs present and correct | PASS |
| No unexpected working-tree change | PASS |
| `env.py` helper ordering / guard / transaction / idempotence | PASS |
| SQLite fresh `upgrade head` exit 0 | PASS |
| SQLite `current` = `0010_m10_remediation_schema_alignment` | PASS |
| SQLite 0008 -> head seeded preservation | PASS |
| PostgreSQL fresh `upgrade head` with no workaround | PASS |
| PostgreSQL `alembic_version.version_num` = `character varying(255)` | PASS |
| PostgreSQL boolean defaults `false` (3 columns) | PASS |
| PostgreSQL 13 expected tables present | PASS |
| PostgreSQL sample FKs and indexes | PASS |
| PostgreSQL legacy 32 -> 255 widening | PASS |
| PostgreSQL repeated upgrade idempotence | PASS |
| PostgreSQL 0008 -> head seeded preservation | PASS |
| 12 PostgreSQL-gated tests | PASS (`12 passed in 18.81s`) |
| App `/health` and `/ready` against PostgreSQL | PASS (both 200) |
| `alembic heads` / `current` consistency | PASS |
| Cleanup of disposable resources | PASS |
| Historical failure record preserved | PASS |

Residual observations (none blocks the gate):

1. **Offline mode is unchanged.** `run_migrations_offline()` does not invoke the helper, so
   generated offline PostgreSQL SQL does not receive the version-table widening. This was
   intentionally left untouched and is a pre-existing limitation.
2. **The integration test hardcodes a database name.** `test_postgres_version_is_16`
   asserts `current_database() == "m05_integration"`; a valid `M05_POSTGRES_TEST_URL`
   pointing to another database fails that assertion. The canonical target passes 12/12.
3. **Global asyncio loop scope.** The new pytest settings apply to the entire backend test
   suite, not only the integration subset. The 12 gated tests pass; the broader unit suite
   was outside this stage's gate and was not rerun.
4. **Downgrade not exercised.** No downgrade function changed. The helper is
   direction-agnostic and only guarantees version-column capacity; downgrade behavior is
   therefore unaffected, but it was not separately executed.
5. **`ALTER TABLE` lock.** The widening runs once per Alembic invocation on a one-row table
   and takes the normal DDL lock. No contention was observed on the disposable instance.

```text
REVIEW_VERDICT = PASS
LIVE_POSTGRESQL_MIGRATION_VERIFICATION = PASS
```
