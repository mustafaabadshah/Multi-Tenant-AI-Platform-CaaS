# M25.1 — PostgreSQL 0017 Migration Analysis & Validation

## 1. Migration Chain Verification
- **Alembic Base Revision**: `0016_m20_2_assistant_tools_config`
- **Target Additive Revision**: `0017_m22_conversation_attachments`
- **Linear Ancestry**: Verified single linear branch (`0016` -> `0017`). No multiple heads or unresolved revisions.

---

## 2. PostgreSQL 16 Structural Conformance
The migration creates three new tables with full PostgreSQL 16 compatibility:

### 1. `conversation_attachments`
- Primary Key: `id` (UUID)
- Foreign Key: `tenant_id` -> `tenants.id` (ON DELETE CASCADE)
- Foreign Key: `conversation_id` -> `conversations.id` (ON DELETE CASCADE)
- Foreign Key: `message_id` -> `messages.id` (ON DELETE SET NULL)
- Foreign Key: `uploader_user_id` -> `users.id` (ON DELETE SET NULL)
- Foreign Key: `promoted_knowledge_base_id` -> `knowledge_bases.id` (ON DELETE SET NULL)
- Foreign Key: `promoted_document_id` -> `documents.id` (ON DELETE SET NULL)
- Indexes: `tenant_id`, `conversation_id`, `message_id`, `uploader_user_id`, `file_hash`, `status`, `promoted_knowledge_base_id`.

### 2. `conversation_attachment_chunks`
- Primary Key: `id` (UUID)
- Foreign Key: `tenant_id` -> `tenants.id` (ON DELETE CASCADE)
- Foreign Key: `attachment_id` -> `conversation_attachments.id` (ON DELETE CASCADE)
- Foreign Key: `conversation_id` -> `conversations.id` (ON DELETE CASCADE)
- Indexes: `tenant_id`, `attachment_id`, `conversation_id`, `chunk_index`.

### 3. `voice_preferences`
- Primary Key: `id` (UUID)
- Foreign Key: `tenant_id` -> `tenants.id` (ON DELETE CASCADE)
- Foreign Key: `user_id` -> `users.id` (ON DELETE CASCADE)
- Constraint: `UNIQUE(tenant_id, user_id)` (ensures 1 preference record per user per tenant)
- Indexes: `tenant_id`, `user_id`.

---

## 3. Backward Compatibility & Staggered Deployment Safety
- **Zero Schema Mutations on Existing Tables**: No columns or constraints were modified on `tenants`, `conversations`, `messages`, `users`, or `knowledge_bases`.
- **Legacy Compatibility**: The deployed backend version (`a0cd98c`) does not reference the new tables and will continue operating with 100% stability even after migration `0017` is executed on live Neon.
- **Downgrade Safety**: The `downgrade()` function cleanly drops tables in reverse order of foreign key dependency (`voice_preferences` -> `conversation_attachment_chunks` -> `conversation_attachments`).

---

## 4. Required Runtime Role Grants for `mmaip_app`
Following execution of migration `0017` by migration-capable role `mmaip_user`, the restricted runtime application role `mmaip_app` requires:
```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE conversation_attachments TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE conversation_attachment_chunks TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE voice_preferences TO mmaip_app;
```
No DDL or superuser privileges are granted to `mmaip_app`.
