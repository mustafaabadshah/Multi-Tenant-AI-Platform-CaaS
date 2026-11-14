# M15.1 — Controlled Git Integration Plan

## 1. Safety Directive: Strict Path Allowlisting

Under no circumstances should `git add .` or broad recursive staging be executed.

All local tool configuration files, virtual environments, transient logs, and historical untracked milestone records (`docs/m10`–`docs/m14`) must remain completely undisturbed in the worktree.

---

## 2. Inventory and File Classification

### Group A: Approved Production Source Modifications (6 files)
- `backend/app/api/v1/observability.py`
- `backend/app/assistant_runtime/runtime.py`
- `backend/app/models/__init__.py`
- `backend/app/observability/tracer.py`
- `frontend/app/dashboard/observability/page.tsx`
- `frontend/lib/api.ts`

### Group B: Approved New Backend Implementation Files (5 files)
- `backend/alembic/versions/0011_m15_durable_request_traces.py`
- `backend/app/models/trace.py`
- `backend/app/observability/policy.py`
- `backend/app/observability/pricing.py`
- `backend/app/schemas/observability.py`

### Group C: Approved New Test Suites (2 files)
- `backend/tests/test_observability_v2.py`
- `backend/tests/test_observability_hardening.py`

### Group D: Approved Milestone 15 / 15.1 Documentation (18 files)
- `docs/m15/M15_INITIAL_AUDIT.md`
- `docs/m15/M15_ARCHITECTURE_DECISIONS.md`
- `docs/m15/M15_DATA_MODEL_AND_RETENTION.md`
- `docs/m15/M15_SECURITY_AND_PRIVACY.md`
- `docs/m15/M15_BACKEND_IMPLEMENTATION.md`
- `docs/m15/M15_FRONTEND_IMPLEMENTATION.md`
- `docs/m15/M15_TEST_RESULTS.md`
- `docs/m15/M15_RELEASE_GATE.md`
- `docs/m15/M15_FINAL_REPORT.md`
- `docs/m15/M15_1_INITIAL_REVIEW.md`
- `docs/m15/M15_1_RELIABILITY_VALIDATION.md`
- `docs/m15/M15_1_PRIVACY_SECURITY_VALIDATION.md`
- `docs/m15/M15_1_POSTGRES_MIGRATION_VALIDATION.md`
- `docs/m15/M15_1_METRICS_COST_VALIDATION.md`
- `docs/m15/M15_1_FULL_REGRESSION.md`
- `docs/m15/M15_1_GIT_INTEGRATION_PLAN.md`
- `docs/m15/M15_1_STAGING_RELEASE_PLAN.md`
- `docs/m15/M15_1_FINAL_REPORT.md`

### Group E: Excluded from Git Staging (DO NOT COMMIT)
- `.agents/` (local agent customizations)
- `.kilo/` (local AI model metadata)
- `skills-lock.json` (local agent tooling lock)
- `docs/m10/` (historical untracked records)
- `docs/m11/` (historical untracked records)
- `docs/m12/` (historical untracked records)
- `docs/m13/` (historical untracked records)
- `docs/m14/` (historical untracked records)
- `backend/.venv/` (local virtual environment)

---

## 3. Execution Commands (Pending Operator Authorization)

When the operator explicitly approves Git integration, execute:

```powershell
Set-Location "E:\MM Office\Multi-Tanant-CaaS"

# Stage source code and migration
git add backend/app/api/v1/observability.py
git add backend/app/assistant_runtime/runtime.py
git add backend/app/models/__init__.py
git add backend/app/models/trace.py
git add backend/app/observability/policy.py
git add backend/app/observability/pricing.py
git add backend/app/observability/tracer.py
git add backend/app/schemas/observability.py
git add backend/alembic/versions/0011_m15_durable_request_traces.py
git add frontend/app/dashboard/observability/page.tsx
git add frontend/lib/api.ts

# Stage tests
git add backend/tests/test_observability_v2.py
git add backend/tests/test_observability_hardening.py

# Stage M15 documentation
git add docs/m15/

# Verify exact staging index
git status --short

# Commit with standard message
git commit -m "feat(observability): release candidate Observability 2.0 with durable request traces, RAG diagnostics, and privacy controls"

# Push to origin (requires separate explicit operator authorization)
git push origin main
```
