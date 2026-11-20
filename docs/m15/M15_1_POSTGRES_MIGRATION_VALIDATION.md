# M15.1 — PostgreSQL Migration 0011 Validation Report

## 1. Revision Graph & Identity

- **Migration File:** `backend/alembic/versions/0011_m15_durable_request_traces.py`
- **Revision ID:** `0011_m15_durable_request_traces`
- **Down Revision:** `0010_m10_remediation_schema_alignment`
- **Alembic Heads:** Exactly one head (`0011_m15_durable_request_traces (head)` verified via `alembic heads`).
- **Graph Continuity:** Completely linear; zero branched or diverging heads.

---

## 2. PostgreSQL Compatibility & Defect Remediation

### Defect Identified During M15.1 Inspection:
In the initial M15 migration draft:
```python
sa.Column("is_token_estimated", sa.Boolean(), nullable=False, server_default="1"),
sa.Column("has_preview", sa.Boolean(), nullable=False, server_default="0"),
```
In PostgreSQL, string literals `"1"` and `"0"` render as `DEFAULT '1'` or `DEFAULT 1`, which triggers:
`ERROR: column "is_token_estimated" is of type boolean but default expression is of type integer`.

### Remediation Applied:
Updated to use SQLAlchemy boolean expression constructs:
```python
sa.Column("is_token_estimated", sa.Boolean(), nullable=False, server_default=sa.true()),
sa.Column("has_preview", sa.Boolean(), nullable=False, server_default=sa.false()),
```
This is fully portable across both PostgreSQL 16 and SQLite, and matches the established patterns from migrations `0007`, `0008`, and `0009`.

---

## 3. Schema Structure & Index Optimization

### Table: `request_traces`
- Primary Key: `id` (`sa.Uuid()`)
- Unique Identifier: `trace_id` (`sa.String(36)`) with unique index `ix_request_traces_trace_id`
- Multi-Tenant Foreign Key: `tenant_id` (`sa.ForeignKey("tenants.id", ondelete="CASCADE")`)
- Resource Foreign Keys:
  - `assistant_id`: `sa.ForeignKey("assistants.id", ondelete="SET NULL")`
  - `conversation_id`: `sa.ForeignKey("conversations.id", ondelete="SET NULL")`
- Composite Indexes for Zero-Scan Filtering:
  - `ix_request_traces_tenant_created` on `(tenant_id, created_at)`: Accelerates paginated time-ordered feeds and retention cutoff purges.
  - `ix_request_traces_tenant_status` on `(tenant_id, status)`: Accelerates failure rate and status filters.
  - `ix_request_traces_tenant_assistant` on `(tenant_id, assistant_id)`: Accelerates per-assistant drilldowns.
  - `ix_request_traces_tenant_traffic` on `(tenant_id, traffic_type)`: Accelerates separation of internal vs preview requests.

### Table: `observability_policies`
- Primary Key: `tenant_id` (`sa.ForeignKey("tenants.id", ondelete="CASCADE")`)
- Capture Mode: `sa.String(20)`, server default `"METADATA_ONLY"`
- Retention: `sa.Integer()`, server default `30` days

---

## 4. Backwards Compatibility & Rollback Safety

1. **Non-Destructive DDL:** Migration `0011` only creates new tables and indexes. It makes zero modifications or column additions to existing tables (`tenants`, `users`, `assistants`, `conversations`, `messages`, `knowledge_bases`).
2. **Application Decoupling:** The previously deployed backend (`e492601`) has zero references to `request_traces`. If migration `0011` is applied before backend deployment, existing staging functionality is completely unaffected.
3. **Downgrade Safety:**
   `downgrade()` executes:
   ```python
   op.drop_table("observability_policies")
   op.drop_table("request_traces")
   ```
   Cleanly drops only the observability tables without risk to user, conversation, or vector data.
