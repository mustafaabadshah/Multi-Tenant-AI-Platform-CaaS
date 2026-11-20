# M20.4 — Neon Staging Migration & Recovery Checkpoint Report

| Metric | Target | Observed Value | Status |
|---|---|---|---|
| Project ID | `aged-heart-01771250` | `aged-heart-01771250` (`mmaip-staging`) | PASS |
| Staging Branch | `staging` | `br-tiny-wind-arvfyx75` | PASS |
| Host | Neon Direct Host | `ep-red-silence-armzu0jn.c-4.us-west-2.aws.neon.tech` | PASS |
| Database | `mmaip_staging` | `mmaip_staging` | PASS |
| Migration Role | `mmaip_user` | `mmaip_user` | PASS |
| Runtime App Role | `mmaip_app` | `mmaip_app` | PASS |
| Pre-Migration Revision | `0011` | `0011_m15_durable_request_traces` | PASS |
| Target Revision | `0016` | `0016_m20_2_assistant_tools_config` | PASS |

---

## 1. Pre-Migration Recovery Checkpoint

Prior to executing any DDL or schema upgrades, a dedicated recovery branch was established from the staging branch:

- **Checkpoint Branch Name:** `pre-m20-agentic-release-20261116`
- **Branch ID:** `br-holy-bird-ar61gvun`
- **Parent Branch ID:** `br-tiny-wind-arvfyx75` (`staging`)
- **Compute Endpoint ID:** `ep-silent-pond-arft6nc9`
- **Created At:** `2026-11-16T07:05:28Z`
- **Recovery State:** `ready`
- **Historical Branches Preserved:** `pre-m15-observability-20261115`, `pre-m14-3-20261113T133826Z`, `mmaip_restore_drill`, `main`.

---

## 2. Alembic Migration Upgrade Execution

Executed via `mmaip_user` migration credentials:
```powershell
python -m alembic upgrade head
```

### Migration Transition Sequence:
1. `0011_m15_durable_request_traces -> 0012_m16_auth_sessions_and_invitations`:
   - Created table `auth_sessions` for server-side session management and refresh token rotation.
   - Added `invitation_token_hash` and updated constraints on `invitations`.
2. `0012_m16_auth_sessions_and_invitations -> 0013_m17_durable_quota_reservations`:
   - Created table `quota_reservations` for atomic credit reservation and concurrency control.
3. `0013_m17_durable_quota_reservations -> 0014_m19_tool_registry`:
   - Created table `tools` for custom HTTP endpoints and built-in tool definitions.
4. `0014_m19_tool_registry -> 0015_m20_mcp_agentic_runtime`:
   - Created tables `mcp_connections`, `tool_approvals`, and `tool_invocation_logs`.
5. `0015_m20_mcp_agentic_runtime -> 0016_m20_2_assistant_tools_config`:
   - Added `tools_config` column to `assistants` table for assistant-level tool binding and security bounds.

### Verification of Current Revision:
```text
0016_m20_2_assistant_tools_config (head)
```

---

## 3. Data Integrity & Table Preservation Evidence

Connecting as restricted runtime role `mmaip_app`:
```text
Preserved data in tenants: count=2
Preserved data in users: count=2
Preserved data in assistants: count=3
Preserved data in conversations: count=5
Preserved data in request_traces: count=4
Preserved data in observability_policies: count=0
```
**Data Loss:** Exactly 0 rows lost. 100% preservation of all existing accounts, assistants, conversations, and traces.

---

## 4. Runtime Database Role Privileges (`mmaip_app`)

Explicit restricted DML grants were applied by `mmaip_user`:
```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON auth_sessions TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON quota_reservations TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON tools TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON tool_approvals TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON tool_invocation_logs TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON mcp_connections TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON eval_datasets TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON eval_dataset_items TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON eval_runs TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON eval_run_results TO mmaip_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO mmaip_app;
```

**Verification:** Role `mmaip_app` successfully queried all new tables without permission errors and remains strictly forbidden from executing schema DDL or superuser actions.
