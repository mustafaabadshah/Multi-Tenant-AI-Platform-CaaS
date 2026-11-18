# M28 — Controlled Staging Release Plan

**Milestone:** M28  
**Project:** Multi-Tenant AI Platform (CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Repository:** `https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS`  
**Date:** November 17, 2026  
**Status:** READY FOR OPERATOR REVIEW & APPROVAL  

---

## 1. Safety & Deployment Prerequisite Gate

Pursuant to the Master Execution Prompt Safety Contract:
- **No Git commit or push** without operator approval.
- **No Neon migration execution** without operator approval.
- **No Render staging deployment** without operator approval.
- **Zero additional paid cloud services.**

All local implementation, TypeScript type checking, unit tests, and production builds have passed cleanly.

---

## 2. Release Inventory: Changed Files

### Backend
1. `backend/alembic/versions/0018_m28_message_feedback.py` (New: additive migration for `message_feedback` table)
2. `backend/app/models/conversation.py` (Modified: added `MessageFeedback` model and relationships)
3. `backend/app/models/__init__.py` (Modified: exported `MessageFeedback`)
4. `backend/app/schemas/feedback.py` (New: request and response schemas for feedback and telemetry)
5. `backend/app/schemas/provider.py` (Modified: added quota storage bytes and document count fields)
6. `backend/app/services/feedback_service.py` (New: multi-tenant feedback management service)
7. `backend/app/services/quota_service.py` (Modified: added storage and document aggregation)
8. `backend/app/api/v1/conversations.py` (Modified: added feedback endpoints and status triage)
9. `backend/app/api/v1/beta.py` (New: added `GET /api/v1/beta/cohort` endpoint)
10. `backend/app/api/v1/router.py` (Modified: registered beta router)
11. `backend/tests/test_m28_message_feedback.py` (New: 6 unit tests for feedback operations)
12. `backend/tests/test_m28_beta_and_quota.py` (New: 2 unit tests for beta cohort and quota aggregation)

### Frontend
1. `frontend/lib/api.ts` (Modified: added feedback, beta, quota methods, types, and fixed duplicate declarations)
2. `frontend/app/dashboard/layout.tsx` (Modified: added Evaluations and Beta Quality to Operate nav group)
3. `frontend/app/dashboard/conversations/page.tsx` (Modified: added in-app thumbs up/down, reason picker, and comment)
4. `frontend/app/dashboard/evaluations/page.tsx` (New: RAG Evaluation Studio interface)
5. `frontend/app/dashboard/beta/page.tsx` (New: Private Beta Quality Operations console)
6. `frontend/app/dashboard/settings/page.tsx` (Modified: live usage meters with progress bars and reset date)

### Documentation Suite
1. `docs/m28/M28_0_BASELINE_AND_REUSE_AUDIT.md`
2. `docs/m28/M28_1_MESSAGE_FEEDBACK.md`
3. `docs/m28/M28_2_EVALUATION_STUDIO.md`
4. `docs/m28/M28_3_BETA_OPERATIONS.md`
5. `docs/m28/M28_4_USAGE_AND_QUOTAS.md`
6. `docs/m28/M28_5_SECURITY_AND_REGRESSION.md`
7. `docs/m28/M28_RELEASE_PLAN.md`
8. `docs/m28/M28_MASTER_FINAL_REPORT.md`

---

## 3. Staging Deployment Execution Sequence (Post-Approval)

When authorized by the human operator, the following linear sequence will be executed:

1. **Step 1: Git Commit & Push**
   - Stage exact changed files.
   - Commit: `feat(m28): private beta quality operations, in-app feedback, evaluation studio and tenant quotas`
   - Push to `origin/main`.

2. **Step 2: Neon Staging Database Migration**
   - Run Alembic upgrade: `alembic upgrade head` targeting Neon branch `br-tiny-wind-arvfyx75`.
   - Advances revision from `0017_m22_conversation_attachments` to `0018_m28_message_feedback`.
   - Adds single additive table `message_feedback` with 0 table drops or locks.

3. **Step 3: Render Staging Services Deploy**
   - Trigger Backend deploy on `srv-dbrk57gn74is73fqo4k0`.
   - Trigger Frontend deploy on `srv-dbrkthcipgvc739d6oh0`.
   - Monitor deploy logs until `live`.

4. **Step 4: Non-Destructive Smoke Acceptance**
   - Verify `/health` on backend (200 OK).
   - Verify `/api/v1/beta/cohort` endpoint responds with valid schema.
   - Verify frontend routes `/dashboard/evaluations` and `/dashboard/beta` load without console errors.

---

## 4. Rollback Strategy

1. **Database:** Revision `0018` is completely additive. If rolled back:
   `alembic downgrade 0017_m22_conversation_attachments` drops only `message_feedback`.
2. **Render Services:** Can be instantly rolled back to commit `190030d054c04e7cb5239b4d832249ffc4edae1e` via Render deploy rollback without service downtime.
