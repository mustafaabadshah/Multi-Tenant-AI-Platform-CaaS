# M15.3 — Neon Staging Migration & Recovery Checkpoint Report

## 1. Target Infrastructure Identity

- **Platform:** Neon Serverless PostgreSQL 16
- **Project ID:** `aged-heart-01771250` (`mmaip-staging`)
- **Region:** `aws-us-west-2`
- **Staging Branch:** `staging` (ID: `br-tiny-wind-arvfyx75`)
- **Database:** `mmaip_staging`
- **Migration Role:** `mmaip_user`
- **Runtime Application Role:** `mmaip_app`

---

## 2. Pre-Migration Recovery Checkpoint

Prior to executing any schema modifications, a dedicated recovery branch was created from the verified staging branch:

- **Checkpoint Branch Name:** `pre-m15-observability-20261115`
- **Branch ID:** `br-lingering-resonance-arcdn0a5`
- **Parent Branch ID:** `br-tiny-wind-arvfyx75` (`staging`)
- **Compute Endpoint ID:** `ep-twilight-feather-ar1zjj6a`
- **Creation Timestamp:** `2026-11-14T20:15:08Z`
- **Verified State:** `ready`
- **Historical Branches Preserved:** `pre-m14-3-20261113T133826Z`, `mmaip_restore_drill`, and `main` were untouched.

---

## 3. Migration 0011 Execution

- **Command Executed:**
  ```powershell
  .venv\Scripts\alembic upgrade head
  ```
- **Connection Configuration:** Used `mmaip_user` direct connection with `ssl=require`.
- **Alembic Output:**
  ```text
  INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
  INFO  [alembic.runtime.migration] Will assume transactional DDL.
  INFO  [alembic.runtime.migration] Running upgrade 0010_m10_remediation_schema_alignment -> 0011_m15_durable_request_traces, M15: Durable request traces and workspace observability policies
  ```
- **Post-Migration Current Head:**
  ```powershell
  .venv\Scripts\alembic current
  # Output: 0011_m15_durable_request_traces (head)
  ```

---

## 4. Runtime Database Role Privileges (`mmaip_app`)

Because new tables created by Alembic belong to the migration owner (`mmaip_user`), explicit restricted DML grants were applied:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON request_traces TO mmaip_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON observability_policies TO mmaip_app;
```

### Verification Evidence:
Executed via `mmaip_app` role:
```text
TENANTS=2, USERS=2, ASSTS=2, CONVS=2, TRACES=0, POLICIES=0
```
- Existing tenants, users, assistants, and conversations were 100% preserved.
- `mmaip_app` can perform required DML on `request_traces` and `observability_policies`.
- `mmaip_app` remains strictly restricted: no DDL, no superuser, no table alteration capabilities.
