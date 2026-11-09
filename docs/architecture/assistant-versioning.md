# Assistant Configuration Versioning & Rollback Architecture

## 1. Overview

In enterprise multi-tenant deployments, assistant configuration cannot be destructively overwritten without an audit trail. Milestone M06 introduces persistent, tenant-scoped configuration snapshots in `assistant_versions` with forward-only rollback semantics.

---

## 2. Schema: `assistant_versions` Table

Created via forward migration `0006_assistant_versions_and_configuration.py`:

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | UUID | Primary Key |
| `tenant_id` | UUID | Foreign Key -> `tenants.id` (TenantScoped) |
| `assistant_id` | UUID | Foreign Key -> `assistants.id` (ON DELETE CASCADE) |
| `version_num` | Integer | Incremental index (1, 2, 3...) per assistant |
| `model_name` | String | Recorded model identifier at snapshot time |
| `system_prompt` | Text | Captured persona instructions |
| `config_snapshot` | JSON | Complete serialization of assistant state |
| `actor_id` | UUID (nullable) | Foreign Key -> `users.id` (Audit author) |
| `change_summary` | String (nullable) | Human-readable explanation of change |
| `created_at` | DateTime (UTC) | Immutable creation timestamp |

Composite Indexes:
- `ix_assistant_versions_tenant_assistant_version`: `(tenant_id, assistant_id, version_num)`

---

## 3. Forward-Only Rollback Protocol

When an authorized user requests rollback to historical version $V_k$:

1. **Authorization & Tenant Verification**: The server verifies that the requesting user belongs to `tenant_id` and owns the assistant.
2. **Snapshot Retrieval**: Version $V_k$ is retrieved strictly with `WHERE assistant_id = :id AND tenant_id = :tenant_id AND version_num = :target_version`.
3. **Restoration**: The assistant's active fields (name, prompt, temperature, top_k, retrieval_mode, behavior) are restored from `config_snapshot`.
4. **New Version Generation**: A new version $V_{current + 1}$ is generated:
   $$\text{New Version} = V_{current} + 1$$
5. **Preservation Invariant**: Historical records ($V_1, \dots, V_{current}$) are **never** modified or deleted.
6. **Audit Event**: An audit log entry is dispatched to the tenant audit trail:
   `action="assistant.version_rollback"`, `target_version=k`, `restored_version=current+1`.

```
[ v1: Initial Exam Setup ]  --->  [ v2: Temperature Boost ]  --->  [ v3: Forward Rollback to v1 ]
    (Recorded at 10:00)              (Recorded at 10:15)             (Recorded at 10:30)
                                                                    Snapshot matches v1!
                                                                    History 100% intact!
```
