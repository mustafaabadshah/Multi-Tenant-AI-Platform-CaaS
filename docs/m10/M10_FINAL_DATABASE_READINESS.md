# M10 Final Integration — Stage D: Database & Migration Readiness

**Date:** 2026-11-11
**Rules honored:** No destructive experiments on the development database. All checks on isolated temporary SQLite databases under `%TEMP%\kilo`.

---

## 1. Migration chain (measured)

| Check | Result |
|---|---|
| Single Alembic head | **PASS** — `alembic heads` → `0009_m09_security_and_evaluation (head)` |
| Chain linearity | **PASS** — 0001→0009 strictly linear (`down_revision` chain verified), no branches, no `branch_labels` |
| All models registered | **PASS** — all 35 domain models imported in `app/models/__init__.py`; eval models included |
| Migrations independent of `create_all` | **PARTIAL** — migrations are declarative (`op.*`), but the app lifespan (`main.py`) still runs `Base.metadata.create_all` unconditionally, so on any reachable DB the app can silently create a current schema and leave `alembic_version` stale. Alembic remains the documented path. |
| 0009 self-containment | **PASS** — declarative only, `down_revision=0008`, uses `batch_alter_table` (SQLite-safe) |
| Index/constraint model parity | **PARTIAL** — see drift check below |
| FK + cascades | **PASS** — 0009 FKs use `ON DELETE SET NULL` (api_keys.assistant_id, public_chat_sessions.conversation_id); tenant FKs cascade (consistent with models) |
| Tenant-scoped uniques | **PASS** — 0009 adds `ix_api_keys_assistant_id`, `ix_public_chat_sessions_conversation_id`; eval tables carry `tenant_id` FKs |
| Vector dimension compatibility | **PASS at model level** — dims validated by embedding provider + Qdrant store; `embedding_version` separates model changes |

## 2. Temporary SQLite checks (executed, isolated)

### 2.1 Fresh-database upgrade

| Step | Result |
|---|---|
| `alembic upgrade 0001`, `0002` | PASS |
| `alembic upgrade 0003` | **FAIL** — `NotImplementedError: No support for ALTER of constraints in SQLite dialect` at `0003_embeddings_and_vector_stores.py:34` (`op.create_foreign_key` on `knowledge_bases` outside batch mode). |

**MIG-1 (critical finding):** tracked migration `0003` is PostgreSQL-only. The documented local flow `alembic upgrade head` **fails on SQLite** at 0003. Impact: (a) fresh SQLite environments cannot be migrated via Alembic — they currently survive only because the app lifespan runs `create_all`; (b) CI never exercises Alembic (no `alembic upgrade` step in `ci.yml`). On PostgreSQL this constraint-add is legal, so production is unaffected. **Remediation (recommended, not applied):** wrap the two `create_foreign_key` calls in `with op.batch_alter_table(...)` guarded by `bind.dialect.name != "postgresql"`, or document SQLite as create_all-only. Per audit rules, historical migrations were not rewritten.

### 2.2 Upgrade-from-older-schema + data preservation (0008 → 0009)

Method: temp SQLite built to a 0008-era schema (columns `api_keys.assistant_id` and `public_chat_sessions.conversation_id` removed, eval tables absent), stamped `0008`, seeded with one `api_keys` row and one `public_chat_sessions` row, then `alembic upgrade head`.

| Check | Result |
|---|---|
| Upgrade to 0009 | **PASS** |
| `api_keys` row preserved, `assistant_id` = NULL | **PASS** |
| `public_chat_sessions` row preserved, `conversation_id` = NULL | **PASS** |
| 4 eval tables created | **PASS** |

### 2.3 Schema drift check (`alembic check`)

| Finding | Interpretation |
|---|---|
| Missing indexes on `api_keys` / `public_chat_sessions` in the test DB | Test-construction artifact (hand-built 0008 tables lacked indexes); not a migration defect. |
| `chunk_embeddings.vector` reflected as `NUMERIC` vs metadata `VECTOR` | Expected on SQLite (pgvector type renders as NUMERIC outside PostgreSQL). **Consequence: `alembic check` will always report this drift on SQLite; full drift verification requires PostgreSQL.** |

## 3. PostgreSQL readiness

- Integration harness exists: `tests/integration/` (12 tests) + `docker-compose.m05-postgres.yml` (port 55432, pgvector 16).
- No live PostgreSQL was reachable during this audit.

```text
LIVE_POSTGRESQL_VERIFICATION = NOT RUN
```
SQLite results above are NOT a substitute. Required before staging: run the 12 integration tests against the M05 Postgres container and execute `alembic upgrade head` on PostgreSQL.

## 4. Qdrant readiness (static review)

- Empty-document filter: **VERIFIED fail-closed** (`qdrant_store.py` returns `[]` when `document_ids` empty).
- Tenant filters / payload ACL: **VERIFIED statically** (tenant_id + knowledge_base_id + embedding_version payload filters; resource ACL enforced by retrieval authorization layer before Qdrant).
- Collection lifecycle per dimension: **VERIFIED statically** (`_collection_for_dim`).
- Dimension checks: **VERIFIED statically** (ValueError on mismatch; covered by unit tests).
- Rebuild/recovery scripts: present (`infrastructure/scripts/drill-live-qdrant-rebuild.sh`, `backend/app/commands/drill_qdrant_rebuild.py`) — **not executed**.

```text
LIVE_QDRANT_VERIFICATION = NOT RUN
```
No live Qdrant at `127.0.0.1:6333`; the 5 integration tests were skipped as designed.

## 5. Backup & restore

- Scripts present: `backup-postgres.ps1`, `backup-storage.ps1`, `restore-postgres.ps1`, `restore-storage.ps1`, `verify-backup.ps1`, `backup-paired.ps1`, plus runbooks in `docs/runbooks/`.
- **NOT executed in this audit** (would touch live infrastructure).

---

## Declarations

```text
DATABASE_MIGRATION_READINESS = PARTIAL
LIVE_POSTGRESQL_VERIFICATION = NOT RUN
LIVE_QDRANT_VERIFICATION = NOT RUN
```

Blockers to resolve before M11 staging: **MIG-1** (0003 SQLite incompatibility — decide fix vs documented create_all-only path) and Postgres/Qdrant live runs.
