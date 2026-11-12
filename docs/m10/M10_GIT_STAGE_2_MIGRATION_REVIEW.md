# M10 Git Integration - Stage 2: Migration Release Review

- **Timestamp (UTC):** 2026-11-12T07:10:46Z (task start; execution followed immediately)
- **Repository:** `E:\MM Office\Multi-Tanant-CaaS`
- **Branch / HEAD:** `main` / `9479847b846aaae43cb8f51e81cf18aaf2646d0f`
- **Scope:** Stage 2 migration release review for the M10 Git Integration phase.
- **Mode:** Read-only on the repository except for this one document; no git mutations; no migration edits; no package installs; no connection to the real dev/staging databases.
- **Database policy:** Every alembic execution used a disposable SQLite file under `C:\Users\MUSTAF~1\AppData\Local\Temp\kilo\`. The real `backend/data/mmaip_dev.db` was never opened by a migration or a test.
- **Toolchain:** Windows PowerShell 5.1; backend venv `backend\.venv`; Python 3.12.3; Alembic 1.20.1; SQLAlchemy 2.1.8; SQLite 3.45.1; `pgvector` installed.
- **Environment override:** `alembic.ini` has no `sqlalchemy.url`; `backend/alembic/env.py` falls back to `settings.DATABASE_URL`, so the per-process `$env:DATABASE_URL` value overrode `backend/.env` safely for each run. All alembic commands below were executed from `backend`.

> **LIVE_POSTGRESQL_MIGRATION_VERIFICATION = NOT RUN**
> No live PostgreSQL instance was available. PostgreSQL semantics were reviewed by source inspection only. No PostgreSQL claim in this document is an execution result.

---

## 1. Revision chain and single head

### 1.1 Chain table

| Revision | down_revision | Purpose |
|---|---|---|
| `0001_initial_core_schema` | `None` | Core: users, tenants, organizations, roles/permissions, departments, tenant memberships, employee groups/memberships, assistants, knowledge bases, audit logs, tenant quotas. |
| `0002_document_ingestion_engine` | `0001_initial_core_schema` | Ingestion configs, documents, document versions, document chunks, ingestion jobs, ingestion events. |
| `0003_embeddings_and_vector_stores` | `0002_document_ingestion_engine` | pgvector extension (PostgreSQL only), department/access columns and FKs on knowledge bases and documents, retrieval configs, chunk embeddings, embedding jobs. |
| `0004_assistants_and_conversations` | `0003_embeddings_and_vector_stores` | Assistant LLM/retrieval configuration columns, assistant-knowledge-base links, conversations, messages, message citations. |
| `0005_add_assistant_byok_encrypted_key` | `0004_assistants_and_conversations` | `assistants.byok_encrypted_key`. |
| `0006_assistant_versions_and_configuration` | `0005_add_assistant_byok_encrypted_key` | Additional assistant configuration columns and the `assistant_versions` table. |
| `0007_provider_credentials_and_usage` | `0006_assistant_versions_and_configuration` | `provider_credentials`, `provider_usage_logs`, and `tenant_quotas.daily_request_limit`. |
| `0008_assistant_publishing_and_api_keys` | `0007_provider_credentials_and_usage` | `assistant_publications`, `api_keys`, `public_chat_sessions`; `provider_usage_logs.credential_source/traffic_type`; makes `conversations.user_id` nullable. |
| `0009_m09_security_and_evaluation` | `0008_assistant_publishing_and_api_keys` | `api_keys.assistant_id`, `public_chat_sessions.conversation_id`, and the four `eval_*` tables. |
| `0010_m10_remediation_schema_alignment` | `0009_m09_security_and_evaluation` | Creates the nine model tables missing from 0001-0009, adds 38 missing indexes, drops the orphan `tenant_quotas.daily_request_limit`; full downgrade. |

### 1.2 Single-head evidence

Command (from `backend`):

```powershell
$env:DATABASE_URL = "sqlite+aiosqlite:///C:/Users/MUSTAF~1/AppData/Local/Temp/kilo/m10_s2_fresh.db"
& ".\.venv\Scripts\alembic.exe" heads
```

Output:

```text
0010_m10_remediation_schema_alignment (head)
```

- **Exit code:** `0`
- **Head count:** 1
- **Expected head:** matched exactly.

`alembic history` exit code `0` showed the linear chain `0001 -> 0002 -> ... -> 0010` with no merge revisions, no branches, and no second head. Every `down_revision` equals the previous revision ID; `0001` has `down_revision = None`.

---

## 2. Dialect-specific migration review

### 2.1 `0003_embeddings_and_vector_stores`

PostgreSQL path (unchanged semantics):

- `CREATE EXTENSION IF NOT EXISTS vector` only when `bind.dialect.name == "postgresql"`.
- `op.create_foreign_key("fk_kb_department", ...)` and `op.create_foreign_key("fk_doc_department", ...)` execute directly outside batch mode on PostgreSQL. This is the original PostgreSQL-compatible form.
- Downgrade drops both constraints with direct `op.drop_constraint(..., type_="foreignkey")` on PostgreSQL.

SQLite/non-PostgreSQL path:

- The same two FK creations are wrapped in `op.batch_alter_table(...).create_foreign_key(...)`, which rebuilds the table because SQLite cannot `ALTER TABLE ADD CONSTRAINT`.
- Downgrade uses `op.batch_alter_table(...).drop_constraint(..., type_="foreignkey")`.
- `render_as_batch=True` is set in `env.py`, but 0003 still explicitly wraps these operations so the intent is local and unambiguous.

Verification: a dedicated temp database was upgraded to `0002`, seeded with one `knowledge_bases` row and one `documents` row, upgraded to `0003`, and downgraded back to `0002` (section 5.5). Both directions exited `0`; rows survived; `department_id` was `NULL` and `access_level` defaulted to `tenant` on upgrade; both columns disappeared on downgrade.

Caveat: SQLite foreign-key enforcement is off by default, so this test proves DDL compatibility and table-rebuild data preservation, not runtime FK enforcement. PostgreSQL remains the enforcement authority.

### 2.2 `0010_m10_remediation_schema_alignment`

- On PostgreSQL: `op.drop_column("tenant_quotas", "daily_request_limit")` directly in `upgrade()`; `op.add_column(...)` directly in `downgrade()`.
- On SQLite/other: the same operations run inside `op.batch_alter_table("tenant_quotas", schema=None)`.
- Table creation, index creation, and all nine new tables use portable SQLAlchemy constructs (`sa.Uuid`, `sa.String`, `sa.Text`, `sa.Boolean`, `sa.Integer`, `sa.BigInteger`, `sa.DateTime(timezone=True)`, `sa.ForeignKey`). These map to PostgreSQL-native types (UUID, VARCHAR, TEXT, BOOLEAN, INTEGER, BIGINT, TIMESTAMPTZ).
- PostgreSQL-valid boolean/string server defaults are used (`"true"`, `"http://localhost:20128/v1"`, etc.).

### 2.3 Other dialect-sensitive operations encountered

- `0005`, `0006`, `0008`, and `0009` use `batch_alter_table`. On PostgreSQL, Alembic's batch mode emits native `ALTER TABLE` for these supported operations rather than rebuilding the table; no table copy is required. This is existing behavior, not changed in this stage.
- `0008` uses direct `op.add_column`/`op.drop_column` for `provider_usage_logs`; SQLite 3.45.1 supports both, and the full downgrade passed.
- SQLite reports `Will assume non-transactional DDL`. A mid-migration SQLite failure could therefore leave partial DDL; all reviewed runs were clean. PostgreSQL DDL is transactional.

---

## 3. `0010` contents inventory

### 3.1 Nine created tables

All nine are present in `Base.metadata` and were verified against their models (section 6).

| Table | Columns | Foreign keys (ondelete) | Unique definition | Indexes |
|---|---|---|---|---|
| `provider_connections` | `id`, `tenant_id`, `provider_type`, `base_url`, `api_key_hash`, `is_active`, `created_at`, `updated_at` | `tenant_id -> tenants.id` CASCADE | - | `ix_provider_connections_tenant_id` |
| `embedding_configs` | `id`, `tenant_id`, `model_name`, `dimensions`, `batch_size`, `created_at`, `updated_at` | `tenant_id -> tenants.id` CASCADE | - | `ix_embedding_configs_tenant_id` |
| `vector_store_configs` | `id`, `tenant_id`, `store_type`, `endpoint`, `collection_name`, `created_at`, `updated_at` | `tenant_id -> tenants.id` CASCADE | - | `ix_vector_store_configs_tenant_id` |
| `resource_permissions` | `id`, `tenant_id`, `user_id`, `resource_type`, `resource_id`, `permission`, `created_at`, `updated_at` | `tenant_id -> tenants.id` CASCADE; `user_id -> users.id` CASCADE | `uq_resource_permission` (`tenant_id`, `user_id`, `resource_type`, `resource_id`, `permission`) | `ix_resource_permissions_tenant_id`, `ix_resource_permissions_user_id` |
| `usage_records` | `id`, `tenant_id`, `metric_name`, `quantity`, `recorded_at` | `tenant_id -> tenants.id` CASCADE | - | `ix_usage_records_tenant_id`, `ix_usage_records_metric_name`, `ix_usage_records_recorded_at` |
| `assistant_prompts` | `id`, `assistant_id`, `prompt_type`, `content`, `is_active`, `created_at`, `updated_at` | `assistant_id -> assistants.id` CASCADE | - | `ix_assistant_prompts_assistant_id` |
| `invitations` | `id`, `tenant_id`, `email`, `role_id`, `department_id`, `token`, `expires_at`, `accepted_at`, `created_at`, `updated_at` | `tenant_id -> tenants.id` CASCADE; `role_id -> roles.id` CASCADE; `department_id -> departments.id` SET NULL | unique `token` | `ix_invitations_tenant_id`, `ix_invitations_email`, unique `ix_invitations_token` |
| `assistant_memberships` | `id`, `assistant_id`, `department_id`, `group_id`, `created_at`, `updated_at` | `assistant_id -> assistants.id` CASCADE; `department_id -> departments.id` CASCADE; `group_id -> employee_groups.id` CASCADE | - | `ix_assistant_memberships_assistant_id` |
| `message_attachments` | `id`, `tenant_id`, `message_id`, `filename`, `file_path`, `created_at`, `updated_at` | `tenant_id -> tenants.id` CASCADE; `message_id -> messages.id` CASCADE | - | `ix_message_attachments_tenant_id`, `ix_message_attachments_message_id` |

Notes:

- `usage_records` intentionally has `recorded_at` but no `created_at`/`updated_at`, matching its model (it is not `TimestampMixin`).
- `assistant_prompts` and `assistant_memberships` intentionally have no `tenant_id`, matching their models; tenant isolation for them is via the parent assistant.
- `invitations.token` is implemented as a unique index, matching the model's `unique=True, index=True`.

### 3.2 Added indexes on pre-existing tables (23)

| Table | Indexes added by 0010 |
|---|---|
| `roles` | `ix_roles_tenant_id` |
| `role_permissions` | `ix_role_permissions_role_id`, `ix_role_permissions_permission_id` |
| `tenant_memberships` | `ix_tenant_memberships_role_id`, `ix_tenant_memberships_department_id` |
| `tenant_quotas` | `ix_tenant_quotas_tenant_id` (unique) |
| `employee_groups` | `ix_employee_groups_department_id`, `ix_employee_groups_tenant_id` |
| `group_memberships` | `ix_group_memberships_group_id`, `ix_group_memberships_membership_id` |
| `audit_logs` | `ix_audit_logs_action`, `ix_audit_logs_actor_id`, `ix_audit_logs_resource_type` |
| `assistants` | `ix_assistants_slug` |
| `provider_usage_logs` | `ix_provider_usage_logs_assistant_id`, `ix_provider_usage_logs_user_id` |
| `ingestion_jobs` | `ix_ingestion_jobs_document_version_id` |
| `embedding_jobs` | `ix_embedding_jobs_document_id` |
| `document_chunks` | `ix_document_chunks_document_version_id` |
| `chunk_embeddings` | `ix_chunk_embeddings_document_version_id` |
| `api_keys` | `ix_api_keys_user_id` |
| `assistant_publications` | `ix_assistant_publications_assistant_id` (unique) |
| `public_chat_sessions` | `ix_public_chat_sessions_publication_id` |

Total: 15 indexes on the nine new tables + 23 on existing tables = **38 indexes**. All 38 were confirmed present at head; none were missing.

### 3.3 Column drop

- `tenant_quotas.daily_request_limit` is dropped at the end of `upgrade()`.
- The migration comment/docstring says the column "exists in migration 0001". That is inaccurate: `0001_initial_core_schema` never defines it. It is added by `0007_provider_credentials_and_usage` with `server_default="1000"`. This is a documentation-only inaccuracy; the drop itself is correct.
- `downgrade()` restores the column with `server_default="10000"`, not the `"1000"` used by 0007. Structural symmetry is complete, but this restored default differs. The column is unused by the ORM, so there is no functional impact; see section 4 and section 9.

---

## 4. Column-drop safety evidence

### 4.1 Model has no such column

`backend/app/models/administration.py` defines `TenantQuota` with exactly: `id`, `tenant_id`, `max_users`, `max_assistants`, `max_storage_bytes`, `monthly_token_limit`, `created_at`, `updated_at`. There is no `daily_request_limit` mapped attribute.

### 4.2 Grep results

Command (repo root, excluding `.git`, `.venv`, `node_modules`, `__pycache__`, `.next`):

```powershell
rg -n "daily_request_limit" .
```

Code/service/schema hits:

| Location | Meaning | Hard dependency? |
|---|---|---|
| `backend/app/services/quota_service.py:18` | `DEFAULT_DAILY_REQUEST_LIMIT = 2_000` | No |
| `backend/app/services/quota_service.py:84` | `getattr(quota, "daily_request_limit", DEFAULT_DAILY_REQUEST_LIMIT)` | **No** - guarded fallback |
| `backend/app/services/quota_service.py:252` | Same guarded fallback in the usage summary | **No** - guarded fallback |
| `backend/app/services/quota_service.py:262` | Builds a response dict key `"daily_request_limit"` from the computed limit | No |
| `backend/app/schemas/provider.py:68` | Response DTO field `daily_request_limit: int` | No - computed API contract |
| `frontend/lib/api.ts:523`, `frontend/app/dashboard/providers/page.tsx:244,249` | Frontend consumes the computed summary field | No |

The only other hits are migrations (`0007`, `0010`), documentation/artifacts, and the pre-existing `backend/data/mmaip_dev.db` file itself. No raw SQL, repository, or model maps the column.

Critical nuance: the service references are **not zero**, but they are soft `getattr(..., default)` reads. Because `TenantQuota` never mapped the column, the ORM object never exposed it even before the drop; the fallback value (2000) was already the effective runtime value. The drop therefore changes no ORM-visible behavior. The response field name remains part of the provider usage summary contract and is populated from the fallback/computed value.

**Conclusion:** the column is orphaned at the ORM level and safe to drop. No code path requires the physical column.

---

## 5. SQLite execution matrix

All databases were fresh disposable files under `C:\Users\MUSTAF~1\AppData\Local\Temp\kilo\`. Each file was deleted before the run. Commands below are the exact PowerShell forms used from `backend` (the `$env:DATABASE_URL` line is omitted only where obvious).

| ID | Scenario | Command(s) | Exit | Result |
|---|---|---|---|---|
| T1 | Single head | `alembic heads` | 0 | Only `0010_m10_remediation_schema_alignment (head)`. |
| T2 | Chain order | `alembic history` | 0 | Linear `0001 -> ... -> 0010`; no branches/merges. |
| T3 | Fresh base -> head | `alembic upgrade head` on new `m10_s2_fresh.db` | 0 | All 10 migrations applied; `alembic current` = `0010_m10_remediation_schema_alignment (head)`. |
| T4 | 0008 -> head with seeded data | `alembic upgrade 0008...`; seed; `alembic upgrade head` | 0 | Rows preserved; new nullable columns `NULL`; eval + 0010 tables present. |
| T5 | Full downgrade head -> 0002 | `alembic downgrade 0002_document_ingestion_engine` | 0 | Reached `0002_document_ingestion_engine`; 20 tables remain; 0003+ artifacts gone. |
| T6 | Re-upgrade 0002 -> head | `alembic upgrade head` | 0 | Reached `0010_m10_remediation_schema_alignment`; all objects recreated. |
| T7 | 0010-only downgrade | `alembic downgrade 0009_m09_security_and_evaluation` | 0 | Nine tables and all 38 indexes dropped; `daily_request_limit` restored. |
| T8 | 0010 re-upgrade | `alembic upgrade head` | 0 | Nine tables and 38 indexes recreated; column dropped again. |
| T9 | 0003 batch path with data | `upgrade 0002`; seed KB/document; `upgrade 0003`; `downgrade 0002` | 0 / 0 | Rows preserved in both directions; new columns added and removed correctly. |
| T10 | `tenant_quotas` batch drop with data | `downgrade 0009`; seed quota row; `upgrade head` | 0 / 0 | Quota row preserved; `daily_request_limit` removed; other values intact. |
| T11 | Drift check | `alembic check` | -1 (non-zero) | 0 functional operations; cosmetic residual only (section 7). |

### 5.1 Fresh upgrade detail

`T3` output applied, in order:

```text
-> 0001_initial_core_schema
0001 -> 0002_document_ingestion_engine
0002 -> 0003_embeddings_and_vector_stores
0003 -> 0004_assistants_and_conversations
0004 -> 0005_add_assistant_byok_encrypted_key
0005 -> 0006_assistant_versions_and_configuration
0006 -> 0007_provider_credentials_and_usage
0007 -> 0008_assistant_publishing_and_api_keys
0008 -> 0009_m09_security_and_evaluation
0009 -> 0010_m10_remediation_schema_alignment
```

Final state: 46 application tables (excluding `alembic_version`), 119 `ix_%` indexes, `alembic_version` = `0010_m10_remediation_schema_alignment`. `tenant_quotas` columns: `id`, `tenant_id`, `max_users`, `max_assistants`, `max_storage_bytes`, `monthly_token_limit`, `created_at`, `updated_at` (no `daily_request_limit`).

### 5.2 0008 -> head data preservation detail

At `0008`, one row was seeded in each of `tenants`, `users`, `assistants`, `assistant_publications`, `api_keys`, and `public_chat_sessions`:

- `api_keys`: `name = legacy-key`, `key_prefix = mmaip_live_`, `key_hash = hash-abc`, `is_active = 1`.
- `public_chat_sessions`: `session_token = tok-1`, `client_ip_hash = ip-hash`, `user_agent = UA`.

After `0009` and `0010`:

- `api_keys` count = 1; original values preserved; `assistant_id = NULL`.
- `public_chat_sessions` count = 1; original values preserved; `conversation_id = NULL`.
- `tenants`, `users`, `assistants`, `assistant_publications` counts all remained 1.
- All nine 0010 tables existed with 0 rows.
- All four `eval_*` tables existed with 0 rows.
- `tenant_quotas.daily_request_limit` was absent.

This is a true data-preservation test for the 0009 batch rebuilds of `api_keys` and `public_chat_sessions`.

### 5.3 Full downgrade and re-upgrade detail

`T5` downgraded through every revision from `0010` to `0002` with exit `0`. At `0002`:

- 20 tables remained: `assistants`, `audit_logs`, `departments`, `document_chunks`, `document_versions`, `documents`, `employee_groups`, `group_memberships`, `ingestion_configs`, `ingestion_events`, `ingestion_jobs`, `knowledge_bases`, `organizations`, `permissions`, `role_permissions`, `roles`, `tenant_memberships`, `tenant_quotas`, `tenants`, `users`.
- `knowledge_bases.department_id/access_level` and `documents.department_id/access_level` were absent.
- `tenant_quotas.daily_request_limit` was absent (0007's downgrade removes it).
- 0003+ tables (`retrieval_configs`, `chunk_embeddings`, `embedding_jobs`, conversations/messages/citations, assistant versions, provider tables, publishing tables, eval tables) were absent.

`T6` re-upgraded from `0002` to head with exit `0`; `alembic current` returned `0010_m10_remediation_schema_alignment (head)`. Core rows (`tenants`, `users`, `assistants`) survived the full down/up cycle because they belong to 0001/0006-era schema. Rows in 0008+ tables were intentionally dropped by the 0008 downgrade.

### 5.4 0010 downgrade symmetry detail

At head, all 38 indexes created by 0010 were present (0 missing). After `alembic downgrade 0009_m09_security_and_evaluation` (exit `0`):

- All nine 0010 tables were gone.
- All 38 0010 indexes were gone.
- The four `eval_*` tables from 0009 remained, as expected.
- `tenant_quotas.daily_request_limit` was restored as `INTEGER NOT NULL DEFAULT '10000'` (SQLite `pragma table_info` position 8).
- Re-upgrade to head exit `0`.

The 38-index check used an explicit list derived from the migration source (15 on new tables + 23 on existing tables), so the result is not a spot check.

### 5.5 0003 batch-path data preservation

On `m10_s2_0003.db`:

1. `upgrade 0002_document_ingestion_engine` -> exit `0`.
2. Seeded one `knowledge_bases` row (`KB-keep`) and one `documents` row (`doc.txt`).
3. `upgrade 0003_embeddings_and_vector_stores` -> exit `0`. Counts stayed 1/1; `knowledge_bases.department_id = NULL`, `access_level = 'tenant'`; `documents.department_id = NULL`, `access_level = 'tenant'`.
4. `downgrade 0002_document_ingestion_engine` -> exit `0`. Counts stayed 1/1; both `department_id` and `access_level` were gone from both tables.

This directly exercises both SQLite batch rebuilds (FK creation and FK removal) with live rows.

### 5.6 `tenant_quotas` batch-drop data preservation

On `m10_s2_data.db` at `0009`, a `tenant_quotas` row was seeded with `max_users=7`, `max_assistants=3`, `max_storage_bytes=123456`, `monthly_token_limit=999999`, `daily_request_limit=1234`. After `upgrade head` (exit `0`):

- Row count = 1.
- `max_users=7`, `max_assistants=3`, `max_storage_bytes=123456`, `monthly_token_limit=999999` all preserved.
- `daily_request_limit` absent.

This proves the SQLite batch table rebuild performed by the column drop preserves the row and all remaining columns.

---

## 6. Model parity for the nine 0010 tables

### 6.1 Method

The fresh head database was inspected with SQLAlchemy `inspect()` and compared to `Base.metadata.tables` for each of the nine tables. The comparison covered:

- column names and nullability,
- primary-key columns,
- foreign-key column sets, referred tables/columns, and `ondelete` options,
- unique constraints and unique indexes (semantic column sets),
- non-unique index column sets.

`Base.metadata` inclusion was checked separately. `alembic check` (which performs a full autogenerate comparison, including type comparison) reported no drift for any of the nine tables.

### 6.2 Results

| Table | Columns/nullability | PK | FKs + ondelete | Unique | Indexes | Overall |
|---|---|---|---|---|---|---|
| `provider_connections` | OK | OK | OK | OK | OK | **PASS** |
| `embedding_configs` | OK | OK | OK | OK | OK | **PASS** |
| `vector_store_configs` | OK | OK | OK | OK | OK | **PASS** |
| `resource_permissions` | OK | OK | OK | OK | OK | **PASS** |
| `usage_records` | OK | OK | OK | OK | OK | **PASS** |
| `assistant_prompts` | OK | OK | OK | OK | OK | **PASS** |
| `invitations` | OK | OK | OK | OK | OK | **PASS** |
| `assistant_memberships` | OK | OK | OK | OK | OK | **PASS** |
| `message_attachments` | OK | OK | OK | OK | OK | **PASS** |

`Base.metadata` includes all nine table names: **True**.

### 6.3 Observations

- Foreign-key cascade semantics match the models exactly: tenant FKs CASCADE; `resource_permissions.user_id` CASCADE; `assistant_prompts.assistant_id` CASCADE; `invitations.role_id` CASCADE and `department_id` SET NULL; `assistant_memberships` assistant/department/group CASCADE; `message_attachments.message_id` CASCADE.
- `uq_resource_permission` matches the model's named composite unique constraint. `invitations.token` matches the model's unique index. No extra or missing unique definitions were found.
- Several migrations add DB-level `server_default` values that the models express only as Python-side defaults (for example `provider_connections.base_url`, `embedding_configs.model_name/dimensions/batch_size`, `vector_store_configs.store_type`, `assistant_prompts.prompt_type/is_active`, `usage_records.quantity`). The values are consistent with the Python defaults. This is an additive migration style, not a parity defect; `compare_server_default` is not enabled in `env.py`, so `alembic check` does not evaluate it.
- `alembic check` reported no type change for any of the nine tables. The two type changes it did report are on pre-existing tables (`assistants.temperature`, `chunk_embeddings.vector`) and are SQLite rendering artifacts (section 7).

---

## 7. `alembic check` residual drift

Command:

```powershell
$env:DATABASE_URL = "sqlite+aiosqlite:///C:/Users/MUSTAF~1/AppData/Local/Temp/kilo/m10_s2_fresh.db"
& ".\.venv\Scripts\alembic.exe" check
```

- **Exit code:** `-1` (non-zero; expected because cosmetic operations remain).
- **Functional operations remaining:** `0` `add_table`, `0` `add_column`, `0` `remove_column`, `0` `remove_table`.
- **Operation counts:** `4` `remove_constraint`, `14` `remove_index`, `13` `add_index`, `2` `modify_type`.

### 7.1 Residual categories

**A. Unique constraint vs unique index representations (4 constraints; 3 index conversions)**

| Existing database object | Model expectation | Assessment |
|---|---|---|
| `uq_api_keys_key_hash` + non-unique `ix_api_keys_key_hash` | unique `ix_api_keys_key_hash` | Equivalent; uniqueness preserved. |
| `uq_publication_assistant_id` | already-present unique `ix_assistant_publications_assistant_id` | Equivalent; uniqueness preserved (0010 created the unique index). |
| `uq_publication_public_id` + non-unique `ix_assistant_publications_public_id` | unique `ix_assistant_publications_public_id` | Equivalent; uniqueness preserved. |
| `uq_public_chat_sessions_session_token` + non-unique `ix_public_chat_sessions_session_token` | unique `ix_public_chat_sessions_session_token` | Equivalent; uniqueness preserved. |

**B. Index renames (11 stale names; 10 replacement indexes because one replacement already exists)**

| Stale index | Model/expected index | Status |
|---|---|---|
| `ix_assistant_kbs_assistant_id` | `ix_assistant_knowledge_bases_assistant_id` | rename only |
| `ix_assistant_kbs_kb_id` | `ix_assistant_knowledge_bases_knowledge_base_id` | rename only |
| `ix_assistant_kbs_tenant_id` | `ix_assistant_knowledge_bases_tenant_id` | rename only |
| `ix_chunk_embeddings_doc_id` | `ix_chunk_embeddings_document_id` | rename only |
| `ix_chunk_embeddings_hash` | `ix_chunk_embeddings_content_hash` | rename only |
| `ix_chunk_embeddings_kb_id` | `ix_chunk_embeddings_knowledge_base_id` | rename only |
| `ix_chunk_embeddings_version` | `ix_chunk_embeddings_embedding_version` | rename only |
| `ix_document_chunks_version_id` | `ix_document_chunks_document_version_id` | stale name only; 0010 already created the target index |
| `ix_embedding_jobs_kb_id` | `ix_embedding_jobs_knowledge_base_id` | rename only |
| `ix_ingestion_configs_kb_id` | `ix_ingestion_configs_knowledge_base_id` | rename only |
| `ix_retrieval_configs_kb_id` | `ix_retrieval_configs_knowledge_base_id` | rename only |

These index pairs cover the same columns; only the names differ. The `ix_document_chunks_version_id` case produces one `remove_index` and no `add_index` because 0010's `ix_document_chunks_document_version_id` already satisfies the model.

**C. SQLite type rendering (2 `modify_type` operations)**

| Column | SQLite reflected type | Model type | Assessment |
|---|---|---|---|
| `assistants.temperature` | `FLOAT()` | `Double()` | Both are 8-byte floating point; cosmetic SQLite rendering. |
| `chunk_embeddings.vector` | `NUMERIC()` | `VECTOR()` | SQLite renders the pgvector type as NUMERIC; PostgreSQL stores `vector`. Cosmetic SQLite-only. |

### 7.2 PostgreSQL-only caveat for `alembic check`

The SQLite check did not report `tenant_quotas.tenant_id`, but PostgreSQL reflection may additionally report the unnamed unique constraint created by 0001 alongside the unique index created by 0010. Both enforce uniqueness; this falls under the same accepted unique-constraint-vs-unique-index category. The same applies to the 0008 unique constraints on `api_keys.key_hash`, `assistant_publications.assistant_id/public_id`, and `public_chat_sessions.session_token`. Because live PostgreSQL was not run, the exact PostgreSQL autogenerate output is not claimed.

**Conclusion:** zero functional drift; residual drift is cosmetic/equivalent and matches the categories explicitly accepted in 0010's docstring and Stage 4's migration report.

---

## 8. PostgreSQL verification status

```text
LIVE_POSTGRESQL_MIGRATION_VERIFICATION = NOT RUN
```

- No live PostgreSQL server was available; no PostgreSQL connection string was used; no PostgreSQL container was started.
- PostgreSQL semantics were preserved **by inspection only**, specifically:
  - 0003 keeps `CREATE EXTENSION IF NOT EXISTS vector`, direct `create_foreign_key`, and direct `drop_constraint` on PostgreSQL; the batch wrappers are unreachable on that dialect.
  - 0010 keeps direct `drop_column`/`add_column` on PostgreSQL; only SQLite/other dialects enter batch mode.
  - 0010's new-table DDL uses SQLAlchemy types that map to PostgreSQL-native UUID/BOOLEAN/BIGINT/TEXT/VARCHAR/TIMESTAMPTZ, and server defaults are PostgreSQL-valid literals.
  - The revision chain is linear and does not skip PostgreSQL-specific branches.
- Residual PostgreSQL risks that only a live run can settle: pgvector extension availability/permissions; FK creation against any pre-existing violating data; lock duration for the `daily_request_limit` drop; and actual autogenerate output for the unique-constraint-vs-unique-index cases.
- This stage does **not** claim PostgreSQL migration success. Any release gate requiring live PostgreSQL must remain open.

---

## 9. Findings and release notes

1. **Single head and linear chain:** confirmed; expected head `0010_m10_remediation_schema_alignment`.
2. **SQLite upgrade/downgrade:** all paths pass, including full downgrade to `0002` and re-upgrade to head.
3. **Data preservation:** passed for 0008 -> head (api keys and public chat sessions), 0003 batch rebuilds, and the 0010 `tenant_quotas` batch drop.
4. **Model parity:** all nine 0010 tables match their SQLAlchemy models for columns/nullability, PK, FKs/ondelete, unique definitions, and indexes; all nine are in `Base.metadata`.
5. **Column-drop safety:** `daily_request_limit` is not a model attribute. Two service reads use `getattr(..., default)`, so they were already using the fallback and are not hard dependencies. The drop is safe.
6. **Documentation inaccuracy:** 0010's docstring says the dropped column came from 0001; it actually came from 0007. No migration edit was made in this stage.
7. **Downgrade default asymmetry:** 0010 downgrade restores `daily_request_limit` with default `10000`, while 0007 created it with `1000`. Structure is symmetric; only the restored default differs. Because the column is unused by the ORM, impact is nil, but a future cleanup could align it.
8. **`create_all`-initialized databases:** 0010 is not idempotent. A database bootstrapped by `Base.metadata.create_all()` and then stamped at `0009` would already have the nine tables, so 0010's `create_table` calls would fail with "table already exists". Operational guidance: verify `alembic current` and the table inventory before upgrading; apply 0010 only to a fresh/linear migration chain or a parity-verified database. This is a deployment caveat, not a defect in the linear upgrade path.
9. **Redundant uniqueness:** `tenant_quotas.tenant_id` carries both the 0001 unnamed unique constraint and the 0010 unique index. Both enforce the same rule; harmless, but it may surface as a cosmetic `remove_constraint` item on PostgreSQL autogenerate.
10. **`alembic check` is not a clean pass:** it exits non-zero by design here. The release criterion is the functional-drift count (zero), not a zero exit code.

---

## 10. Verdict

```text
MIGRATION_CHAIN_SINGLE_HEAD              = PASS (0010_m10_remediation_schema_alignment)
MIGRATION_CHAIN_LINEARITY                = PASS (0001 -> 0010, no branches)
SQLITE_FRESH_UPGRADE_BASE_TO_HEAD        = PASS (exit 0)
SQLITE_0008_TO_HEAD_DATA_PRESERVATION    = PASS (rows preserved; new columns NULL)
SQLITE_FULL_DOWNGRADE_HEAD_TO_0002       = PASS (exit 0)
SQLITE_REUPGRADE_0002_TO_HEAD            = PASS (exit 0)
SQLITE_0010_DOWNGRADE_SYMMETRY           = PASS (9 tables + 38 indexes removed; column restored)
SQLITE_0003_BATCH_PATH_UPGRADE_DOWNGRADE = PASS (rows preserved both directions)
MODEL_PARITY_NINE_TABLES                 = PASS (columns/FKs/unique/indexes)
COLUMN_DROP_SAFETY                       = PASS (no hard model/service dependency)
ALEMBIC_CHECK_FUNCTIONAL_DRIFT           = 0 add_table / 0 add_column / 0 remove_column / 0 remove_table
ALEMBIC_CHECK_RESIDUAL_DRIFT             = COSMETIC ONLY (unique constraint/index, index renames, SQLite type rendering)
LIVE_POSTGRESQL_MIGRATION_VERIFICATION   = NOT RUN
```

**Release assessment:** the SQLite migration chain is internally consistent, reversible, and model-aligned. The only unverified surface is a live PostgreSQL execution; PostgreSQL semantics are preserved by inspection, not by execution.