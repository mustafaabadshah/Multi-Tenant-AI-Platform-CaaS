# M28.0 — Baseline and Reuse Audit Report

**Milestone:** M28.0  
**Project:** Multi-Tenant AI Platform (CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Repository:** `https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS`  
**Branch:** `main`  
**Current HEAD:** `e1d82d8def8a8d79cdd215731ab701960b00d528`  
**Remote `origin/main`:** `e1d82d8def8a8d79cdd215731ab701960b00d528`  
**Alembic Revision:** `0017_m22_conversation_attachments`  
**Date:** November 17, 2026  

---

## 1. Git Inspection & Baseline Verification

Pursuant to Phase 1 instructions, the local repository and remote branches were inspected:
- Current branch: `main`
- Current local HEAD: `e1d82d8def8a8d79cdd215731ab701960b00d528`
- Remote `origin/main`: `e1d82d8def8a8d79cdd215731ab701960b00d528` (synchronized, 0 commits ahead/behind)
- `git diff --check`: 0 whitespace or formatting errors.
- Working copy clean with standard untracked milestone documentation and local cache files.

### Baseline Release History
- `190030d054c04e7cb5239b4d832249ffc4edae1e`: `feat(m27): integrate secure web intelligence and reliable voice chat` (deployed to Render staging)
- `e1d82d8def8a8d79cdd215731ab701960b00d528`: `docs(m27): add M27.2 authorized staging release report`

---

## 2. Staging Infrastructure Status & Reconciliation

- **Backend Service:** `srv-dbrk57gn74is73fqo4k0` (`https://mmaip-backend.onrender.com`) — Status: `Live` (Deploy `dep-dbu275afngtc73aj3al0`)
- **Frontend Service:** `srv-dbrkthcipgvc739d6oh0` (`https://mmaip-frontend.onrender.com`) — Status: `Live` (Deploy `dep-dbu27r56e07s73bjdsfg`)
- **Neon Staging Database:** `mmaip_staging` on project `aged-heart-01771250`, branch `br-tiny-wind-arvfyx75`
- **Verified Alembic Revision:** `0017_m22_conversation_attachments` (58 public tables intact)
- **Live Acceptance:** All 11 technical endpoints verified 200 OK.
- **Operator Audio Acceptance:** Recorded as `PENDING_OPERATOR_ACCEPTANCE` until physical microphone and speaker testing is performed by the human operator.

---

## 3. Existing Quality Infrastructure Reuse Matrix

| Subsystem / Component | Existing Verified Implementation | Missing / Required Capability | Smallest Required Change (Reuse Strategy) |
|---|---|---|---|
| **AI Evaluation Service** | `backend/app/services/evaluation_service.py` provides `list_datasets`, `create_dataset`, `seed_system_benchmarks`, `execute_eval_run`, `get_run`, `list_runs`. | Frontend dashboard integration; runner progress state; dataset management UI. | **Reuse 100% of backend engine.** Build `/dashboard/evaluations` connecting directly to existing endpoints in `api/v1/evaluation.py`. |
| **Starter Benchmarks** | `backend/app/evaluation/starter_benchmarks.py` defines 3 comprehensive deterministic RAG benchmarks (`Financial Q&A`, `Product Support`, `Policy & Compliance`). | One-click seeding and dataset trigger from UI. | **Reuse existing benchmarks.** Expose seeded datasets in Evaluation Studio without creating synthetic mock scores. |
| **Evaluation Metrics** | `backend/app/evaluation/metrics.py` implements: Context Recall, Precision@k, Recall@k, MRR, NDCG, Answer Completeness, Faithfulness, Unsupported Claims, Citation Accuracy. | Visual representation of metric definitions, evaluator types, and fallback to `NOT_EVALUATED` when ground truth is missing. | **Reuse existing metric functions.** Display precise definitions and avoid fabricated constant scores. |
| **Quota & Usage Service** | `backend/app/services/quota_service.py` tracks monthly tokens, daily requests, active in-flight reservations, breakdown by provider and traffic type. | Tenant-level storage bytes and document count aggregation; settings UI gauge widget. | **Extend `get_usage_summary()`** to count active documents and storage bytes from `Document` and `ConversationAttachment`. Build Settings Usage widget. |
| **Invitations & Cohort** | `backend/app/models/invitation.py` & `backend/app/api/v1/members.py` manage tenant invites, tokens, expiration, and role assignments (`employee`, `viewer`). | Dedicated Beta Cohort inspection view showing invited testers, status, turn counts, and satisfaction rate. | **Add `GET /api/v1/beta/cohort`** summarizing real invitations and member activity for authorized admins. |
| **Audit Logs** | `backend/app/models/administration.py` defines `AuditLog` table with actor, action, resource, IP, and structured JSON details. | Audit event recording for feedback submissions and status changes. | **Reuse existing `AuditLog` model** to log feedback lifecycle events. |
| **In-App Message Feedback** | `backend/app/models/conversation.py` has `Message`, `ConversationAttachment`, `MessageCitation`. No dedicated feedback table. | Dedicated `message_feedback` entity with user scoping, idempotency, rating (`THUMBS_UP`/`THUMBS_DOWN`), category, comment, and review lifecycle. | **Create `MessageFeedback` model** in `app/models/conversation.py` with linear additive Alembic migration `0018_m28_message_feedback.py`. |

---

## 4. Architectural Boundaries for M28

1. **Zero Fake Metrics:** Evaluation scores are computed strictly from real test cases or marked `NOT_EVALUATED`.
2. **Zero Mandatory Paid APIs:** Default evaluation runs use deterministic local retrieval against knowledge bases; no paid LLM judge is required.
3. **No Outbound Email / Public Registration Changes:** Beta invitations remain manually created by admins; email delivery uses existing staging mock/console delivery.
4. **Strict Multi-Tenant Scoping:** Feedback, evaluations, cohort status, and quotas are physically partitioned by `tenant_id`.
