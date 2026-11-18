# M28.2 Staging Release Package & Deployment Sequence

## 1. Package Overview
This release combines M28 (Feedback, Evaluation Studio, Beta Operations, Usage Quotas), M28.1 (Usability overhaul, 3-tier navigation, starter prompts, HTML parser), and M28.2 (Connection-level SSRF defense, 2 MiB stream limiting, source-aware grounding, typed ingestion error taxonomy).

## 2. Git Allowlist & Change Summary
- **Backend Modifications:**
  - `backend/app/api/v1/conversations.py`
  - `backend/app/api/v1/router.py`
  - `backend/app/assistant_runtime/context.py`
  - `backend/app/assistant_runtime/runtime.py`
  - `backend/app/models/__init__.py`
  - `backend/app/models/conversation.py`
  - `backend/app/parsers/__init__.py`
  - `backend/app/parsers/csv_parser.py`
  - `backend/app/parsers/registry.py`
  - `backend/app/schemas/provider.py`
  - `backend/app/services/ingestion/limits.py`
  - `backend/app/services/ingestion/service.py`
  - `backend/app/services/quota_service.py`
  - `backend/app/services/web/kb_saver.py`
  - `backend/app/services/web/reader.py`
  - `backend/app/services/web/ssrf.py`
- **Backend Additions:**
  - `backend/alembic/versions/0018_m28_message_feedback.py`
  - `backend/app/api/v1/beta.py`
  - `backend/app/parsers/html.py`
  - `backend/app/schemas/feedback.py`
  - `backend/app/services/feedback_service.py`
  - `backend/tests/test_m28_1_html_and_web_repair.py`
  - `backend/tests/test_m28_beta_and_quota.py`
  - `backend/tests/test_m28_message_feedback.py`
- **Frontend Modifications:**
  - `frontend/app/dashboard/assistants/page.tsx`
  - `frontend/app/dashboard/conversations/page.tsx`
  - `frontend/app/dashboard/layout.tsx`
  - `frontend/app/dashboard/page.tsx`
  - `frontend/app/dashboard/settings/page.tsx`
  - `frontend/lib/api.ts`
- **Frontend Additions:**
  - `frontend/app/dashboard/beta/page.tsx`
  - `frontend/app/dashboard/evaluations/page.tsx`

## 3. Deployment Sequence (Pending Operator Explicit Authorization)
1. **Source Freeze & Push:**
   - Review allowlist for secrets or unintended files (verified clean).
   - Git commit: `git commit -m "feat(m28): release candidate M28.2 - security hardening, web grounding, HTML repair, and UX polish"`
   - Git push to `origin/main`.
2. **Neon Staging Checkpoint:**
   - Create recovery branch checkpoint on Neon staging branch `br-tiny-wind-arvfyx75`: `checkpoint_m28_pre_migration`.
3. **Database Migration:**
   - Apply Alembic migration `0017` -> `0018_m28_message_feedback` using migration credentials.
   - Run runtime grant if necessary: `GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE message_feedback TO mmaip_app;`.
4. **Backend Deploy (Render):**
   - Trigger deploy on Render service `srv-dbrk57gn74is73fqo4k0` (`https://mmaip-backend.onrender.com`).
   - Poll `/health` until HTTP 200 is confirmed.
5. **Frontend Deploy (Render):**
   - Trigger deploy on Render service `srv-dbrkthcipgvc739d6oh0` (`https://mmaip-frontend.onrender.com`).
   - Verify index and login routes return 200.
6. **Live Verification:**
   - Run bounded synthetic smoke tests.
   - Execute operator manual acceptance checklist.

## 4. Rollback Plan
- **Frontend Rollback:** Redeploy previous Render commit from UI dashboard (instant).
- **Backend Rollback:** Redeploy previous Render commit from UI dashboard.
- **Database Rollback:** If migration rollback is required before production data is accumulated, run `alembic downgrade -1` or restore from Neon recovery checkpoint `checkpoint_m28_pre_migration`.

## 5. Cost Gate
- Render Free Tier maintained (0 added compute costs).
- Zero paid API endpoints added.
- OmniRoute / OpenAI compatibility maintained without forcing vendor fees.
- **Gate:** `COST_BUDGET_VERIFIED = PASS`
