# M15 Release Gate & Security Debt Reconciliation

| Field | Value |
|---|---|
| Milestone | M15 — Observability 2.0, AI Request Intelligence & Platform Reliability |
| Review Date | 2026-11-14 |
| Gate Status | **`M15_LOCAL_IMPLEMENTATION_PASS_STAGING_APPROVAL_REQUIRED`** |
| Deployment Action | No staging mutation performed; awaiting operator authorization |

---

## 1. Reconciliation of Prior Security & Operational Findings

| Finding ID | Source | Summary | M15 Status / Disposition | Blocks Release? |
|---|---|---|---|---|
| **OPS-1** | M14.7.1 | Render CLI & MCP keys appeared in local tool output | Confirmed isolated to local tool transcript; never written to git repository or remote services. Rotation remains an operator action; does not impact service runtime or code. | No (Local operator control plane) |
| **SEC-1** | M14.7 | Stateless JWT logout & refresh token replay window | Documented P2 security debt. Tokens expire within 1 hour. Full revocation blocklist tracked for dedicated auth hardening milestone. | No (Accepted for staging cohort) |
| **OPS-2** | M14.7 | Render Free reverse proxy IP bucketing | Rate limits bucket across shared Render proxy egress. Documented caveat for Free tier staging. | No |
| **STO-1** | M14.4 | Duplicate B2 tenant prefix in some legacy keys | Handled by S3 adapter key normalization. Verified object retrieval operates safely. | No |
| **AI-1** | M14.7 | Mock model citation grounding | M15 adds explicit retrieval diagnostics and chunk provenance capture so grounding is verifiable on real BYOK models. | No |
| **DAT-1** | M14.7 | Synthetic operator test accounts present | Test accounts remain active for synthetic smoke tests. Public self-registration remains strictly closed (`ALLOW_PUBLIC_REGISTRATION=false`). | No |
| **UI-1** | M14.7 | Manual UI checklist operator sign-off | Operator inspected UI and reported satisfaction; M15 builds upon this accepted UI foundation. | No |

---

## 2. Release Gate Decision

### Verdict: `M15_LOCAL_IMPLEMENTATION_PASS_STAGING_APPROVAL_REQUIRED`

**Criteria Assessment:**
1. **Durable Tracing:** Implemented via PostgreSQL table `request_traces` (survives container restarts).
2. **Safe Input/Output Previews:** Controlled by workspace policy (`METADATA_ONLY` by default; redacted previews with multi-pattern scrub). Role-gated to administrators.
3. **Retrieval Observability:** Real latency metrics, candidate counts, and RRF diagnostics captured.
4. **Verifiable Costs:** Exact pricing catalog with zero-cost mock, known rates, and unknown labels.
5. **Abort Handling:** SSE stream disconnection cleanly marks traces as `CANCELLED`.
6. **Frontend Experience:** Restrained, responsive Linear/Notes-inspired UI with latency percentiles, waterfall execution timeline, and policy controls.
7. **Regression Suite:** All 9 backend tests passing (100%), frontend TypeScript check clean, production bundle compiled with 0 errors.

---

## 3. Recommended Safe Staging Deployment Procedure

When authorized by the operator, execute the following staging deployment sequence:

```powershell
# 1. Review Git status and ensure local changes are approved
git status --short

# 2. Stage and commit M15 implementation files
git add backend/alembic/versions/0011_m15_durable_request_traces.py
git add backend/app/models/trace.py backend/app/models/__init__.py
git add backend/app/observability/
git add backend/app/assistant_runtime/runtime.py
git add backend/app/api/v1/observability.py backend/app/schemas/observability.py
git add backend/tests/test_observability_v2.py
git add frontend/lib/api.ts frontend/app/dashboard/observability/page.tsx
git add docs/m15/
git commit -m "feat(observability): implement Observability 2.0 with durable tracing, privacy policies, and request intelligence"

# 3. Apply Alembic migration to Neon Staging Database (Operator approval required)
# Set DATABASE_URL to staging Neon connection string
# alembic upgrade head

# 4. Push to remote and trigger Render deploys (Auto-deploy remains OFF)
# git push origin main
# Deploy mmaip-backend on Render dashboard
# Deploy mmaip-frontend on Render dashboard
```
