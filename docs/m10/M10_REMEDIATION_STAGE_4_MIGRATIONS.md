# M10 Remediation — Stage 4: MIG-1 SQLite & PostgreSQL Migration Compatibility

**Date:** 2026-11-11
**Finding:** MIG-1 — fresh SQLite `alembic upgrade head` failed at migration `0003` (`op.create_foreign_key` on existing tables is PostgreSQL-only). Additionally, `alembic check` revealed 9 model tables and several indexes missing from the migration chain (masked by lifespan `create_all`).

---

## 1. Investigation

- **0003 root cause:** `op.create_foreign_key("fk_kb_department", ...)` and `("fk_doc_department", ...)` execute `ALTER TABLE ADD CONSTRAINT`, unsupported by SQLite outside batch mode.
- **Chain-wide drift:** `alembic check` against a fully migrated temp SQLite DB showed missing tables `provider_connections`, `embedding_configs`, `vector_store_configs`, `resource_permissions`, `usage_records`, `assistant_prompts`, `invitations`, `assistant_memberships`, `message_attachments`; missing indexes on roles/tenant_memberships/role_permissions/tenant_quotas/audit_logs/assistants/etc.; and an orphan `tenant_quotas.daily_request_limit` column from migration 0001 that the model no longer defines.
- **Deployment history justification (documented decision):** no shared/production database has ever run these migrations (staging never provisioned, `DEPLOYED=NO`); SQLite migration support is an established project requirement (README + `.env.example` document the SQLite fallback and `alembic upgrade head` setup flow); the audit directive prohibits `create_all` as a migration substitute. Therefore a dialect-aware fix of 0003 and a forward-compatible corrective migration were justified.

## 2. Fix implemented

1. **`0003_embeddings_and_vector_stores.py`** (tracked, historical):
   - Upgrade: the two FK creations now use `op.create_foreign_key` on PostgreSQL and `op.batch_alter_table(...).create_foreign_key(...)` on other dialects. PostgreSQL path is byte-for-byte unchanged.
   - Downgrade: FK drops wrapped in the same dialect-aware batch pattern.
2. **New `0010_m10_remediation_schema_alignment.py`** (forward-compatible corrective migration, `down_revision=0009`):
   - Creates the 9 missing tables with the exact model columns, FKs (tenant/user/assistant/role/department cascades), unique constraints, and tenant-scoped indexes.
   - Adds the genuinely missing indexes on existing tables (roles.tenant_id, tenant_memberships.role_id/department_id, role_permissions.role_id/permission_id, tenant_quotas.tenant_id unique, audit_logs.action/actor_id/resource_type, assistants.slug, provider_usage_logs.assistant_id/user_id, ingestion_jobs.document_version_id, embedding_jobs.document_id, document_chunks.document_version_id, chunk_embeddings.document_version_id, api_keys.user_id, assistant_publications.assistant_id unique, public_chat_sessions.publication_id, employee_groups.*, group_memberships.*).
   - Drops `tenant_quotas.daily_request_limit` (batch mode on SQLite, direct on PostgreSQL).
   - Full downgrade provided.
3. **Accepted residual drift (documented, intentionally not converted):** cosmetic index renames (e.g. `ix_chunk_embeddings_doc_id` vs `ix_chunk_embeddings_document_id` — functionally equivalent indexes already exist), unique-constraint vs unique-index representations, and SQLite type rendering (`VECTOR`→`NUMERIC`, `Float` vs `Double`). These are semantic equivalents; converting them would add migration churn without functional benefit.

## 3. Verification (temporary databases only — no dev/prod DB touched)

| Check | Command | Result |
|---|---|---|
| Fresh SQLite upgrade 0001→head | `alembic upgrade head` on temp DB | **PASS** (ends at `0010_m10_remediation_schema_alignment`) |
| Single head | `alembic heads` | **PASS** — `0010` only |
| Full downgrade on SQLite (head→0002) | `alembic downgrade 0002` | **PASS** |
| 0008→head data preservation | seeded api_keys + public_chat_sessions rows at 0008, upgraded through 0009+0010 | **PASS** — rows preserved, new columns NULL, eval tables created |
| Functional drift (missing tables/columns/indexes) | `alembic check` category scan | **PASS** — 0 `add_table` / `add_column` / `remove_column` remain |
| Residual drift | `alembic check` | cosmetic-only (documented above); `alembic check` still exits non-zero by design |
| PostgreSQL live validation | — | **NOT RUN** (no live Postgres; 12 integration tests remain environment-gated) |

## 4. Files changed

| File | Change |
|---|---|
| `backend/alembic/versions/0003_embeddings_and_vector_stores.py` | dialect-aware FK create/drop (batch on non-PostgreSQL) |
| `backend/alembic/versions/0010_m10_remediation_schema_alignment.py` | new corrective migration |

## 5. Impact on existing environments

- **Dev SQLite DBs created via `create_all`** (e.g. `backend/local.db`): untouched by this audit. Recommendation (documented, not executed): `alembic stamp head` once to adopt the migration ledger.
- **PostgreSQL:** upgrade path remains linear 0001→0010; 0010 is additive except the `daily_request_limit` drop (column unused by the model).

---

```text
STAGE_4_STATUS = PASS
LIVE_POSTGRESQL_MIGRATION_VERIFICATION = NOT RUN
```
