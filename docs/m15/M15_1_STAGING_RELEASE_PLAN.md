# M15.1 — Staging Release and Rollback Procedure

## 1. Staging Target Identity

- **Backend Service:** Render Web Service (`https://mmaip-backend.onrender.com`)
- **Frontend Service:** Render Web Service (`https://mmaip-frontend.onrender.com`)
- **Staging Database:** Neon PostgreSQL 16 (Branch: `staging`)
- **Previous Known-Good Commit:** `e4926014471f00695b2de3c046fe529f867955b0`
- **Render Deployment Mode:** Manual Deploy (Auto-Deploy disabled for safety)

---

## 2. Step-by-Step Staging Release Sequence

### Step 1: Pre-Release Gate Sign-off
- All 59 regression tests passed locally.
- Frontend build compiled successfully with 0 type errors.
- Migration `0011` validated for PostgreSQL syntax and boolean defaults.
- Operator provides explicit authorization for Git commit and push.

### Step 2: Push Approved Revision
```powershell
git push origin main
```
Note the resulting commit SHA ($SHA_{release}$).

### Step 3: Neon Staging Database Migration
Execute Alembic upgrade against the Neon staging database URL:
```powershell
# Set Neon Staging connection string
$env:DATABASE_URL = "<NEON_STAGING_DATABASE_URL>"

# Run migration 0011
.venv\Scripts\alembic upgrade head
```
Verify the migration:
```powershell
.venv\Scripts\alembic current
# Expected: 0011_m15_durable_request_traces (head)
```

### Step 4: Backend Staging Deployment (Render)
1. In Render Dashboard, navigate to `mmaip-backend`.
2. Select **Manual Deploy** → **Deploy a specific commit**.
3. Input $SHA_{release}$.
4. Monitor build logs: verify Python dependencies install and service starts cleanly.
5. Verify health probe:
   ```powershell
   curl -i https://mmaip-backend.onrender.com/api/v1/health
   # Expected: HTTP 200 {"status": "healthy"}
   ```

### Step 5: Frontend Staging Deployment (Render)
1. In Render Dashboard, navigate to `mmaip-frontend`.
2. Select **Manual Deploy** → **Deploy a specific commit**.
3. Input $SHA_{release}$.
4. Monitor build logs: verify Next.js production build completes and server boots.

### Step 6: Post-Deployment Smoke Test
1. Log into `https://mmaip-frontend.onrender.com/login`.
2. Navigate to **Observability Console** (`/dashboard/observability`).
3. Verify KPIs load (Total Requests, Error Rate, Latency p50/p95/p99, Estimated Cost).
4. Run a test message in the chat interface:
   - Verify SSE streaming delivers tokens smoothly.
   - Refresh Observability page; verify the new request trace appears in the list.
5. Click the trace to open the Trace Inspector:
   - Check Overview, Spans Waterfall (`retrieval`, `context_assembly`, `provider_generation`), and Retrieval Diagnostics.
   - Verify input/output preview is masked or redacted according to policy.
6. Open **Policy & Retention** modal:
   - Verify current policy shows `METADATA_ONLY` and `30` days.

---

## 3. Safe, Zero-Data-Loss Rollback Strategy

If an unexpected production defect is detected post-deployment:

### Immediate Application Rollback (Zero Data Loss):
1. **Frontend:** In Render Dashboard (`mmaip-frontend`), trigger **Rollback** to previous commit `e4926014471f00695b2de3c046fe529f867955b0`.
2. **Backend:** In Render Dashboard (`mmaip-backend`), trigger **Rollback** to previous commit `e4926014471f00695b2de3c046fe529f867955b0`.
3. **Database Compatibility:** Migration `0011` is **strictly additive**. The old application code (`e492601`) does not query `request_traces` or `observability_policies`. Therefore, **the database DOES NOT need to be downgraded** for the application to function normally. Existing conversations, users, and documents remain 100% operational.

### Database Downgrade (If Requested by Operator):
If schema rollback is explicitly requested:
```powershell
.venv\Scripts\alembic downgrade 0010_m10_remediation_schema_alignment
```
This safely drops only `request_traces` and `observability_policies` without touching any other tables.
