# M28.1 — Migration & Release Gate Plan

## 1. Alembic Migration Inspection
- **Migration ID:** `0018_m28_message_feedback`
- **Down Revision:** `0017_m22_conversation_attachments`
- **File:** `backend/alembic/versions/0018_m28_message_feedback.py`
- **Head Status:** Single linear Alembic head verified.
- **Table Introduced:** `message_feedback`
  - Columns: `id` (UUID, PK), `tenant_id` (UUID, Indexed), `conversation_id` (UUID, Indexed), `message_id` (UUID, Indexed), `user_id` (UUID, Indexed), `rating` (VARCHAR 16), `category` (VARCHAR 32), `comment` (TEXT), `status` (VARCHAR 16), `metadata` (JSONB), `created_at` (TIMESTAMPTZ), `updated_at` (TIMESTAMPTZ).
  - Constraints: Unique constraint `uq_feedback_msg_user (conversation_id, message_id, user_id)` guaranteeing idempotent ratings.
  - Foreign Keys: `tenant_id` references `tenants.id`, `conversation_id` references `conversations.id`, `message_id` references `messages.id`.

## 2. Staging Deployment Sequence (Approval Required)
When authorized by the operator for deployment to Neon staging:
1. **Checkpoint:** Verify Neon staging branch `br-tiny-wind-arvfyx75` current revision (`0017_m22_conversation_attachments`).
2. **Migration Execution:** Run `alembic upgrade head` applying revision `0018_m28_message_feedback`.
3. **Runtime Role Permissions:** Ensure runtime PostgreSQL user `neondb_owner` / application role possesses `SELECT, INSERT, UPDATE, DELETE` grants on `message_feedback`.
4. **Backend Staging Deploy:** Trigger deploy on Render service `srv-dbrk57gn74is73fqo4k0`.
5. **Frontend Staging Deploy:** Trigger deploy on Render service `srv-dbrkthcipgvc739d6oh0`.
6. **Live Smoke Validation:** Run operator acceptance checklist against staging URL.
