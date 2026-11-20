# M28.2 PostgreSQL Migration 0018 Release Safety Validation

## 1. Migration Specification
- **File:** `backend/alembic/versions/0018_m28_message_feedback.py`
- **Revision:** `0018_m28_message_feedback`
- **Down Revision:** `0017_m22_conversation_attachments` (matches live Neon staging Alembic revision)
- **Table Introduced:** `message_feedback`
  - Columns: `id` (UUID, PK), `tenant_id` (UUID, FK -> tenants.id, ON DELETE CASCADE), `message_id` (UUID, FK -> messages.id, ON DELETE CASCADE), `user_id` (UUID, FK -> users.id, ON DELETE CASCADE), `rating` (String(16), NOT NULL), `comment` (Text), `tags` (JSONB), `status` (String(32), NOT NULL, default 'new'), `created_at` (DateTime(timezone=True)), `updated_at` (DateTime(timezone=True)).
  - Indexes:
    - `ix_message_feedback_tenant_id`
    - `ix_message_feedback_message_id`
    - `ix_message_feedback_user_id`
    - `ix_message_feedback_status`
    - `uq_feedback_msg_user` (`tenant_id`, `message_id`, `user_id`)

## 2. Validation Execution (Isolated Engine Test)
Executed programmatic upgrade, downgrade, and re-upgrade test using Alembic configuration:
1. `alembic upgrade head`: Applied 0017 -> 0018 cleanly. Created `message_feedback` table with constraints and indexes.
2. `alembic downgrade -1`: Rolled back 0018 -> 0017 cleanly. Dropped `message_feedback` table and associated indexes.
3. `alembic upgrade head`: Re-applied 0018 cleanly, confirming idempotency and repeatable execution.

## 3. Data Safety & Backward Compatibility
- Additive schema change: does not modify or drop existing tables or columns.
- Preserves existing conversations, messages, and attachments.
- Runtime backend code functions normally whether `message_feedback` table has 0 rows or existing rows.

## 4. Runtime Grants Plan for Neon Staging
When applied to live Neon staging with `neondb_owner`:
```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE message_feedback TO mmaip_app;
```
*(Will be executed only upon explicit operator authorization in Stage 9/10).*

## 5. Recovery Plan
Prior to applying migration 0018 to live Neon staging branch `br-tiny-wind-arvfyx75`, take a fresh Neon recovery checkpoint (e.g., `checkpoint_m28_pre_migration`). Do NOT reuse old checkpoint `br-young-rice-arlmh348`.

## 6. Gate Assessment
**POSTGRES_0018_MIGRATION_READY = PASS**
Migration 0018 is verified safe, idempotent, additive, and fully rollback-compatible.
