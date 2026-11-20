# Critical Audit A — Alembic Migration Compatibility & Graph Linearity

## 1. Background & Root Cause Analysis

In the previous remediation iteration, the assistant BYOK encryption column (`byok_encrypted_key`) was introduced by directly modifying an existing historical migration:
`backend/alembic/versions/0004_assistants_and_conversations.py`

### Why Modifying Historical Migration 0004 Was Defective
1. **Schema Drift on Existing Environments**: Any staging, local, or developer database already migrated to head `0004` would record `version_num = '0004_assistants_and_conversations'`. Running `alembic upgrade head` would do nothing, leaving the physical database without `byok_encrypted_key`, resulting in immediate SQL runtime failures when the assistant model attempted to read or write the column.
2. **Loss of Immutability**: Production database migrations must be forward-only and immutable. Modifying past migration files breaks reproducibility across distributed deployment pipelines.

## 2. Corrective Strategy Implemented

1. **Restoration of 0004**: `backend/alembic/versions/0004_assistants_and_conversations.py` was restored to its exact historical baseline matching Git HEAD `448431c4b004dc4b134dc94705b7dd96d0f2a9f5`.
2. **Forward Migration 0005**: Created `backend/alembic/versions/0005_add_assistant_byok_encrypted_key.py`:
   - `revision = "0005_add_assistant_byok_encrypted_key"`
   - `down_revision = "0004_assistants_and_conversations"`
   - Implements `op.batch_alter_table("assistants")` for cross-dialect compatibility (PostgreSQL and SQLite).
   - Nullable `String(1024)` column with zero data loss for existing records.
   - Clean, reversible `downgrade()` dropping only the added column.

## 3. Migration Graph Verification

The full Alembic revision graph forms an unbroken linear sequence:
```text
base
  └── 0001_initial_core_schema
        └── 0002_document_ingestion_engine
              └── 0003_embeddings_and_vector_stores
                    └── 0004_assistants_and_conversations
                          └── 0005_add_assistant_byok_encrypted_key (HEAD)
```

## 4. Test Scenarios Executed

All three mandatory migration test scenarios were executed via `backend/tests/test_m05_migration_compatibility.py`:
- **Scenario A (Fresh Database)**: Linear migration DAG validation from base through 0005 head. `PASS`.
- **Scenario B (Existing Database at 0004)**: Upgraded pre-populated assistants table from 0004 to 0005. Verified legacy records remained intact, column was created as null, and subsequent ciphertext updates succeeded. `PASS`.
- **Scenario C (Downgrade and Re-upgrade)**: Downgraded 0005, verified only `byok_encrypted_key` was removed while assistant records persisted. Re-upgraded to 0005 and verified column restored. `PASS`.

## 5. Classification

**Result**: `MIGRATION_COMPATIBLE_WITH_NEW_REVISION_REQUIRED` (Resolved and verified via migration `0005`).
