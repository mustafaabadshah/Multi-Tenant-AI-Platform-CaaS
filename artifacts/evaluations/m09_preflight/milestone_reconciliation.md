# M09 Preflight: Milestone Reconciliation & Heritage Verification

**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Date:** November 10, 2026  
**Auditor:** Principal Software Architect & QA Lead  
**Milestone:** M09 — Preflight Audit  

---

## 1. Milestone Status & Heritage Matrix

| Milestone | Reported Commit | Verified In Git | Status | Core Deliverables & Capabilities |
|---|---|---|---|---|
| **M01** | Historical | Yes (`7b5d010`, `11c77af`) | **PASS** | Modular monolith, multi-tenant RBAC, organizations, Next.js SaaS shell, Argon2id security. |
| **M02** | Historical | Yes (`bacd566`) | **PASS** | Document ingestion, extraction (PDF, DOCX, TXT), OCR engine, chunking engine. |
| **M03** | Historical | Yes (`448431c`) | **PASS** | Embeddings registry, vector stores (FTS, pgvector, Qdrant), BYOK encryption. |
| **M04** | Historical | Yes (`448431c`) | **PASS** | Conversational RAG, SSE streaming, multi-turn history, citations with page numbers. |
| **M05** | Historical | Yes (`bc194d0`, `4f75f68`) | **CONDITIONAL_PASS** | Hybrid retrieval (RRF), staging blueprints. **4 recovery drills explicitly DEFERRED**. |
| **M06** | `9595339` | Yes | **PASS** | Assistant Studio, 12 pre-configured templates, 5-step wizard, config version history. |
| **M07** | `ad46a44` | Yes | **PASS** | Knowledge Studio, Retrieval Playground, BYOK Vault, Quota management. |
| **M08** | `9479847` | Yes (HEAD) | **PASS** | Assistant Publishing, Embed Widget, Developer REST API, TypeScript & Python SDKs. |

---

## 2. Mandatory Verification: M05 Conditional Pass Preservation

Per the platform architecture standard:
- **M05 status remains:** `CONDITIONAL_PASS`
- The following 4 drills were explicitly deferred during M05 and **MUST REMAIN `DEFERRED — NOT RUN`**:
  1. **PostgreSQL Backup & Restore Verification:** Deferred due to local environment constraints (SQLite primary for dev).
  2. **Qdrant Rebuild & Recovery Verification:** Deferred; local development relies on CPU FTS/FastEmbed.
  3. **Live PostgreSQL Integration Tests:** Deferred to formal staging environments.
  4. **Live Qdrant Integration Tests:** Deferred to staging environments with Qdrant containers.
- **Rule:** Never promote M05 to `PASS` merely because M06, M07, M08, or M09 progress.

---

## 3. Reconciliation of Reported M08 Deliverables vs. Actual Repository State

Antigravity reported completion of Milestone M08 in commit `9479847`. Here is the evidence-based audit:

| M08 Capability Claimed | Physical Repository Verification | Audit Finding |
|---|---|---|
| **Standalone Public Chat (`/p/[publicId]`)** | `frontend/app/p/[publicId]/page.tsx` (382 lines) | **VERIFIED.** Implements public chat with zero private metadata exposure, streaming, and footnotes. Wrapped in `<Suspense>`. |
| **Website Embed Widget (`/embed/[publicId]`)** | `frontend/app/embed/[publicId]/page.tsx` (354 lines) | **VERIFIED.** Iframe-optimized layout, clean responsive view, domain whitelist check. |
| **Embed Loader Script (`/api/v1/public/embed.js`)** | `backend/app/api/v1/public_chat.py` (lines 178-208) | **VERIFIED.** Serves lightweight (1,042 bytes) JavaScript embed bootstrap loader. |
| **Developer API Endpoints (`/api/v1/developer/*`)** | `backend/app/api/v1/developer.py` (221 lines) | **VERIFIED.** Scoped API key management, assistant listing, and SSE chat streaming. |
| **TypeScript SDK (`@mmaip/client`)** | `sdk/typescript/` (`package.json`, `src/index.ts`, etc.) | **VERIFIED.** Full typings, Node.js + browser support, streaming SSE parser. |
| **Python SDK (`mmaip`)** | `sdk/python/` (`pyproject.toml`, `mmaip/client.py`, etc.) | **VERIFIED.** Built on `httpx`, synchronous and asynchronous streaming support. |
| **Entities & Database Migration** | `backend/app/models/publishing.py`, Alembic `0008` | **VERIFIED.** `AssistantPublication`, `APIKey`, `PublicChatSession` tables; `conversations.user_id` nullability. |
| **Public Knowledge Document Filtering** | `backend/app/assistant_runtime/runtime.py` (lines 148-158) | **VERIFIED.** Queries documents strictly filtering `access_level == 'PUBLIC'`. |
| **Developer API Key Hashing & Scopes** | `backend/app/services/api_key_service.py` (192 lines) | **VERIFIED.** SHA-256 hash storage, `mmaip_live_` prefix, scopes `assistant:read`, `assistant:chat`. |
| **Assistant Studio Publish Tab** | `frontend/app/dashboard/assistants/PublishTab.tsx` (336 lines) | **VERIFIED.** Integrated into Assistant Workspace with preflight checklist, domain management, and embed snippet. |
| **Developer API Keys UI in Settings** | `frontend/app/dashboard/settings/DeveloperApiKeysSection.tsx` (257 lines) | **VERIFIED.** Tab switcher in `/dashboard/settings` with key creation modal and one-time secret display. |
| **Knowledge Studio Chunk Inspector Fix** | `frontend/lib/api.ts` (lines 7-15) | **VERIFIED.** Added `getDocumentChunks`, `getDocumentContent`, `getDocumentHistory`. Restored drawer function. |
| **M08 Test Suite** | `backend/tests/test_m08_publishing_and_api_keys.py` | **VERIFIED.** 8 of 8 tests pass in 34.46s. |
| **Full Platform Regression Suite** | `backend/tests/` | **VERIFIED.** 197 passed, 18 skipped, 0 failures. |
| **Next.js Production Build** | `frontend/` (`npm run build`) | **VERIFIED.** Compiled 18 routes in 5.2s with 0 errors. |

---

## 4. Reconciliation Conclusion

All claimed M01–M08 milestones are reconciled against physical code and commit history. Commit `9479847` is verified as the true HEAD on branch `main`. The platform is in a verified, working state to begin M09 preflight analysis.
