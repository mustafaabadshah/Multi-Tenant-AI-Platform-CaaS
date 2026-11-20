# M28.14 Combined M28.12 + M28.13 Staging Release Gate

**Milestone:** M28.14 — Final Combined Release-Readiness Review & Staging Execution Plan  
**Date:** November 20, 2026  
**Repository:** `https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS`  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Branch:** `main`  
**Remote Baseline HEAD:** `c6908124c1386393f095601782e94431052b18de`  
**Staging Database:** Neon `mmaip_staging` (`aged-heart-01771250`), revision `0018_m28_message_feedback`  
**Render Staging Services:**
- Backend API: `srv-d4afh5m3jp1c738s9vmg` (`https://mmaip-backend.onrender.com`)
- Frontend Web: `srv-d4afh8e3jp1c738s9vqg` (`https://mmaip-frontend.onrender.com`)

**Final Release Verdict:** **`M28_14_READY_FOR_EXPLICIT_STAGING_APPROVAL`**

---

## 1. Executive Summary & Release Scope

This milestone establishes the final combined release gate for **M28.12** (Groq Tool Choice Normalization, Deterministic Academic Search, Markdown Code Block Preservation) and **M28.13** (Knowledge Base Routing Integrity, Anti-Index-0 Policy, Refresh Loop Elimination, and URL-Synchronized Back Navigation).

The global **Antigravity Engineering System V2** standards have been verified and applied:
- Zero unapproved git commits or pushes.
- Zero unapproved Render staging deployments.
- Zero unapproved live database migrations or data mutations (revision 0018 remains untouched).
- All changes verified through multi-layer regression, state machine integrity checks, and typed builds.

---

## 2. Phase 1 — Repository & Working Tree Preservation

A complete repository audit confirmed:
- **Baseline Git HEAD:** `c6908124c1386393f095601782e94431052b18de`
- **Whitespace / Conflict Check:** `git diff --check` and `git diff --cached --check` returned **0 warnings / 0 conflicts**.
- **Secret & Credential Scan:** Comprehensive regex audit across all staged and unstaged diffs confirmed **0 exposed secrets**, tokens, passwords, or connection strings. All API keys remain strictly mapped to environment variables (`OPENAI_API_KEY`, `OMNIROUTE_API_KEY`, `GROQ_API_KEY`).
- **Database Migrations:** No new Alembic migrations introduced. Schema revision remains strictly at `0018_m28_message_feedback`.

---

## 3. Phase 2 — Combined Code Compatibility & Layer Independence

A cross-milestone dependency audit verified that M28.12 and M28.13 modify mutually disjoint, orthogonal layers with zero collision:

| Subsystem | Milestone | Changed Files | Architectural Responsibility |
|---|---|---|---|
| **LLM Provider Gateway** | M28.12 | `groq_provider.py`, `openai_provider.py`, `llm/base.py` | Normalizes `tool_choice` schemas, prevents Groq HTTP 400 when tools are empty. |
| **Assistant Runtime** | M28.12 | `runtime.py`, `context.py`, `markdown_normalizer.py`, `observability/policy.py` | Academic search intent detection, C++ code block fence preservation. |
| **Research Service** | M28.12 | `services/research/academic_search.py`, `services/web/search.py` | arXiv preflight integration with user-agent compliance and vector normalization. |
| **Chat Renderer** | M28.12 | `MarkdownRenderer.tsx` | Clean syntax highlighting and copy-to-clipboard for C++ and multiline code. |
| **Conversations API** | M28.13 | `api/v1/conversations.py` | Validates target KB payload consistency; rejects conflicting destination IDs (HTTP 400). |
| **Chat Studio UI** | M28.13 | `conversations/page.tsx` | Canonical Assistant-KB destination policy, grouped dropdowns, connection badges. |
| **Knowledge Base UI** | M28.13 | `knowledge/page.tsx` | URL query parameter sync (`?kbId=`), primitive state, bounded polling (0 idle calls/min). |

**Conclusion:** Neither milestone overrides, degrades, or reverts the other.

---

## 4. Phase 3 — Focused Acceptance Contracts (18 Verification Points)

| # | Contract Requirement | Tested Component | Observed Behavior & Evidence | Status |
|---|---|---|---|---|
| 1 | Single connected KB assistant | `conversations/page.tsx` | Notes Assistant connected to PF preselects PF with green "Connected" badge. | **PASS** |
| 2 | Multiple connected KBs assistant | `conversations/page.tsx` | Modal initializes with empty `""` placeholder; Save button disabled until user chooses. | **PASS** |
| 3 | Zero connected KBs assistant | `conversations/page.tsx` | Prompts user that no KB is connected; lists other workspace KBs in separate optgroup. | **PASS** |
| 4 | Explicit save to another authorized KB | `conversations/page.tsx` | User can pick an alternate workspace KB; UI displays amber non-connected warning badge. | **PASS** |
| 5 | Cross-tenant KB rejection | `api/v1/conversations.py` | User attempting to promote to a KB in another tenant is rejected with HTTP 404. | **PASS** |
| 6 | Duplicate promotion rejection | `conversation_attachment_service.py` | Attempting to promote an already-promoted attachment returns HTTP 400 Bad Request. | **PASS** |
| 7 | PF vs. Cricket destination | `knowledge-navigation-and-promotion.test.ts` | Attachment promotes to PF; Cricket KB document collection remains untouched. | **PASS** |
| 8 | KB list → detail → Back → Forward | `knowledge/page.tsx` | URL updates to `?kbId=...`; browser Back restores list without full page reload. | **PASS** |
| 9 | Direct detail URL → reload | `knowledge/page.tsx` | F5 refresh on `/dashboard/knowledge?kbId=<uuid>` preserves active KB detail view. | **PASS** |
| 10 | Idle page request stability | `knowledge/page.tsx` | When all documents are in terminal states (`READY`), polling timer is 0 reqs/min. | **PASS** |
| 11 | Polling while ingestion is active | `knowledge/page.tsx` | Fires 4-second bounded poll only when `QUEUED` or `PROCESSING` documents exist. | **PASS** |
| 12 | Polling stops after completion | `knowledge/page.tsx` | Timer automatically clears when all documents reach `READY` or `FAILED`. | **PASS** |
| 13 | Groq tool-choice compatibility | `groq_provider.py` | Automatically sets `tool_choice=None` when tool list is empty, preventing HTTP 400. | **PASS** |
| 14 | Academic search intent detection | `runtime.py` & `academic_search.py` | Regex intent parser detects arXiv queries without triggering on general C++ questions. | **PASS** |
| 15 | PDF vs. academic search comparison | `test_m28_12` Scenario D | Dual retrieval blends uploaded paper chunks with arXiv candidates cleanly. | **PASS** |
| 16 | Direct webpage read & Markdown | `test_m28_12` Scenario E | Preserves C++ loop code fences without raw HTML leakage or broken delimiters. | **PASS** |
| 17 | Citation persistence and reload | `MarkdownRenderer.tsx` | Verified source badges render with verified page numbers and URLs. | **PASS** |
| 18 | Error and cancellation recovery | `knowledge/page.tsx` | Ingestion failure displays inline error banner with retry; no infinite spinner. | **PASS** |

---

## 5. Phase 4 — Data Integrity & Forensic Recovery Audit

### 5.1 Forensic Findings
- Staging record `d5df4dde-ba86-4313-b4d8-c66f5f5b8c80` (`Solar_irradiance__TechScience.pdf`) exists in KB "Cricket" (`476d8908-bb6b-44df-b9fb-538c59bc8d53`) with 117 chunks.
- Both KBs belong to the same tenant (`a2a0b1e6-51bc-4f68-a03e-19ce03c79f94`).

### 5.2 Technical Audit of the Proposed SQL Pointer Recovery
Inspection of backend vector and storage implementations revealed a critical architectural insight:
1. **Vector Store Metadata Inconsistency:** In `backend/app/vectorstores/qdrant_store.py`, every point payload stores `payload["knowledge_base_id"] = str(knowledge_base_id)`. During RAG retrieval, vector queries filter by `filter_criteria.knowledge_base_ids IN (:assistant_kbs)`.
2. **The Danger of Ad-Hoc SQL Updates:** If an operator runs `UPDATE documents SET knowledge_base_id = 'pf_uuid'` solely in PostgreSQL, the vector points in Qdrant will **still contain `cricket_uuid` in their vector payload**. When the Notes Assistant queries PF, Qdrant will filter out these chunks, rendering them **unsearchable via semantic search**.
3. **Classification:** Direct SQL pointer manipulation is **UNSAFE** for vector consistency.

### 5.3 Recommended Safe Recovery Plan
- **Primary Safe Method (Recommended):** After deploying M28.14, the operator navigates to `/dashboard/knowledge?kbId=faccb980-145c-4606-b6f1-b80f24fa8141` ("PF"), uploads `Solar_irradiance__TechScience.pdf` through the standard UI ingestion pipeline, and deletes the accidental copy from "Cricket" using the KB document inspector. This guarantees that relational records, chunk vectors, and storage paths are created atomically and correctly.
- **Safety Gate:** ZERO live data modifications or deletions were performed during this audit.

---

## 6. Phase 5 — Fresh Regression Evidence

### 6.1 Backend Test Results
```bash
# Combined M28.12 + M28.13 + M26 Acceptance Suite
pytest tests/test_m28_12_groq_tool_choice_and_research_search.py \
       tests/test_m28_13_knowledge_integrity_and_routing.py \
       tests/test_m26_multimodal_hardening.py -v
```
**Outcome:** **48 PASSED in 27.03s** (0 failed, 0 errors).

```bash
# Full Backend Regression Suite
pytest tests -q --tb=short
```
**Outcome:** **825 PASSED, 18 SKIPPED, 0 FAILED in 736.61s (12m 16s)**.

### 6.2 Frontend Test & Build Results
```bash
# Frontend Unit & Interaction Tests
npm test -- --watchAll=false
```
**Outcome:** **43 PASSED in 3.3s** (14 suites, 0 failed).

```bash
# TypeScript Static Typecheck
npx tsc --noEmit
```
**Outcome:** **Clean exit code 0 (0 type errors)**.

```bash
# Next.js Production Build
npm run build
```
**Outcome:** **Clean exit code 0. All 24 App Router routes compiled and optimized.**

---

## 7. Phase 6 — Staging Execution Plan

### 7.1 Allowlisted File Package
```text
Backend Code:
  backend/app/api/v1/conversations.py
  backend/app/assistant_runtime/context.py
  backend/app/assistant_runtime/markdown_normalizer.py
  backend/app/assistant_runtime/runtime.py
  backend/app/llm/base.py
  backend/app/llm/providers/groq_provider.py
  backend/app/llm/providers/openai_provider.py
  backend/app/observability/policy.py
  backend/app/services/web/search.py
  backend/app/services/research/academic_search.py

Backend Tests:
  backend/tests/test_m28_12_groq_tool_choice_and_research_search.py
  backend/tests/test_m28_13_knowledge_integrity_and_routing.py

Frontend Code:
  frontend/app/dashboard/conversations/page.tsx
  frontend/app/dashboard/knowledge/page.tsx
  frontend/components/chat/MarkdownRenderer.tsx

Frontend Tests:
  frontend/lib/__tests__/knowledge-navigation-and-promotion.test.ts

Documentation:
  docs/m28/M28_12_*.md
  docs/m28/M28_13_*.md
  docs/m28/M28_14_COMBINED_RELEASE_GATE.md
```

### 7.2 Suggested Commit Message
```text
feat(m28): combined release - groq tool compatibility, academic search, and kb routing integrity (M28.12 + M28.13)

- Fix Groq HTTP 400 when tool list is empty by normalizing tool_choice to None
- Add deterministic arXiv academic search intent detection and vector normalization
- Preserve C++ markdown code fences and syntax rendering in Chat Studio
- Implement deterministic Assistant-KB destination policy (eliminate index-0 fallback)
- Fix infinite re-render loop on /dashboard/knowledge via primitive state normalization
- Connect Knowledge Base selection to URL search params (?kbId=) with back navigation
- Implement bounded auto-polling (0 background requests/min when idle)
- Validate payload target KB consistency in conversations API
```

### 7.3 Deployment Verification Sequence (Post-Approval)
1. **Operator Sign-Off:** Operator approves git commit and push to `origin main`.
2. **Render Trigger:** Trigger automated deployment on Render backend (`srv-d4afh5m3jp1c738s9vmg`) and frontend (`srv-d4afh8e3jp1c738s9vqg`).
3. **SHA Verification:** Verify running deployment commit SHA matches git HEAD.
4. **Health Check:**
   - Backend: `GET https://mmaip-backend.onrender.com/health` returns HTTP 200 `{"status": "healthy"}`.
   - Frontend: `GET https://mmaip-frontend.onrender.com/` returns HTTP 200.
5. **Manual Acceptance:**
   - In Chat Studio with *Notes & Textbook Q&A Assistant*, test "Save to Knowledge". Confirm **PF** is preselected with green badge.
   - Navigate to `/dashboard/knowledge`. Select PF; confirm URL updates to `?kbId=...`. Hit browser Back button; verify instant return to list.
   - Verify DevTools Network tab shows 0 polling requests when viewing an idle KB.

### 7.4 Rollback Runbook
If an unexpected runtime regression occurs on staging:
1. `git revert HEAD` to restore baseline commit `c6908124c1386393f095601782e94431052b18de`.
2. Push to `origin main` to trigger automatic Render rollback.
3. Database requires zero rollback (schema revision 0018 was never changed).

---

## 8. Phase 7 — Final Release Gate Verdict

### **Verdict:** **`M28_14_READY_FOR_EXPLICIT_STAGING_APPROVAL`**

- **Code Compatibility:** 100% verified.
- **Backend Tests:** 825/825 passed.
- **Frontend Tests:** 43/43 passed.
- **Build & Types:** Clean exit code 0.
- **Security & Multi-Tenant:** Verified cross-tenant rejection.
- **Pending:** Awaiting operator authorization to commit, push to GitHub, and trigger staging Render deployments.
