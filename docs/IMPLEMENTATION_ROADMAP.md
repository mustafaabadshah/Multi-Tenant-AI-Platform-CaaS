# MM AI Platform — Implementation Roadmap

This roadmap documents the phased evolution from the current core multi-tenant foundation to an enterprise-grade AI chatbot platform.

> **Status reconciliation performed 2026-11-11 (M10 Final Integration Audit).** Checkboxes below reflect code-verified implementation, not milestone reports alone. See `docs/m10/M10_FINAL_PROJECT_STATUS.md` for the authoritative current status, and `docs/m10/M10_FINAL_INTEGRATION_REPORT.md` for the release gate.

---

## Phase 1: Foundation, Multi-Tenant Core & Identity
- [x] Repository topology & engineering standards (`AGENTS.md`, `README.md`, CI workflows)
- [x] Relational database schema with full domain models (Identity, Organizations, RBAC, Assistants, Knowledge Bases, Auditing)
- [x] Provider-agnostic authentication with Argon2id password hashing and JWT sessions
- [x] Multi-tenant workspace architecture (Individual and Organization workspaces)
- [x] Organization hierarchy (Departments, Employee Groups, Memberships, Invitations)
- [x] Granular RBAC and role permissions
- [x] Strict tenant isolation with composite constraints and scoped repository pattern
- [x] Comprehensive negative security regression tests
- [x] Enterprise Next.js App Router frontend with real-time workspace switching
- [x] Health (`/health`) and Readiness (`/ready`) endpoints

---

## Phase 2: Document Processing, Extraction & OCR Engine
- [x] Multi-format parsing pipeline (PDF, DOCX, TXT, CSV, XLSX, PPTX, JSON, SQL) — `backend/app/parsers/`
- [x] OCR integration for scanned documents & images (local Tesseract and Badho OCR adapter) — `backend/app/ocr/`
- [x] Document chunking strategies (recursive character, semantic boundary, markdown header splitting) — `backend/app/chunking/`
- [x] Background job worker (async ingestion pipeline with status tracking & retry queues) — `backend/app/services/ingestion/` (process-local; startup recovery added in M09)
- [x] Local filesystem storage and S3-compatible cloud storage abstractions — `backend/app/storage/` (S3 adapter added in M09; `aioboto3` dependency pending)

---

## Phase 3: Embeddings, Vector Stores & Hybrid Retrieval
- [x] Embedding adapter layer (OmniRoute / OpenAI-compatible / Sentence-Transformers-fastembed / Local CPU / Mock)
- [x] Dual vector store backend:
  - PostgreSQL pgvector extension for co-located relational + vector queries
  - Qdrant integration for high-throughput standalone vector search
- [x] Full-Text Search (FTS) using PostgreSQL `tsvector` and `tsquery`
- [x] Reciprocal Rank Fusion (RRF) for hybrid keyword + vector retrieval
- [x] Re-ranking pipeline (Cross-Encoder models) — implemented (`backend/app/retrieval/reranking.py`); live-provider verification not run

> Live PostgreSQL (12 tests) and Qdrant (5 tests) integration suites exist but were **NOT RUN** in local audits (no live containers). Deferred to M11 staging.

---

## Phase 4: Chat Orchestration & OmniRoute Gateway Integration
- [x] Conversation and message streaming via Server-Sent Events (SSE)
- [x] OmniRoute Gateway integration (`http://localhost:20128/v1`) with dynamic model selection (`auto`) — **optional provider**; direct OpenAI/Anthropic/Gemini/Groq BYOK paths are independent of OmniRoute
- [x] Context window assembly with grounded citations and chunk references
- [x] Assistant prompt templates, system instructions, and persona configurations
- [x] Multi-turn conversational memory with sliding window context management

---

## Phase 5: Enterprise Controls, Observability & Analytics
- [x] Observability — **substituted**: in-process ring-buffer tracer with SSE trace IDs + persisted JSON (`backend/app/observability/`), instead of Arize Phoenix/OpenTelemetry. Phoenix compose profile remains available but unused by app code.
- [x] Tenant quota enforcement (storage caps, monthly token budgets, concurrency limits) — in-process atomic reservations (`quota_service.py`); single-instance only
- [x] RAG quality assessment — **substituted**: custom deterministic evaluation framework with metrics + optional LLM-judge scaffold (`backend/app/evaluation/`), instead of Ragas/DeepEval. Judge path not wired into runs (audit finding D3).
- [x] Embeddable web widget for public customer-support assistants — `/embed/[publicId]`
- [x] Fine-grained BYOK (Bring-Your-Own-Key) credential management for enterprise tenants — Fernet-encrypted vault, strict no-fallback policy

---

## Milestone Status (M06–M10)

| Milestone | Status | Evidence |
|---|---|---|
| M06 Assistant Studio | COMPLETE | 12 templates, wizard, versioning; `tests/test_m06_assistant_studio.py` |
| M07 Knowledge Studio & BYOK | COMPLETE | `tests/test_m07_knowledge_and_providers.py` |
| M08 Publishing & SDKs | COMPLETE | commit `9479847`; `tests/test_m08_publishing_and_api_keys.py` |
| M09 Security/Evaluation/Observability | COMPLETE (uncommitted) | migration `0009`, `app/evaluation/`, `app/observability/` |
| M10 Stages 1–5 | CONDITIONAL_PASS | `docs/m10/M10_STAGE_*.md`; user visual acceptance pending; 18 skipped live tests; 4 physical drills deferred |
| M10 Stage 6 (Markdown & citations) | CONDITIONAL_PASS — final report missing | `MarkdownRenderer.tsx` integrated (5 surfaces); 2 markdown tests failing; citation dedup gaps |

---

## Next Milestones (not started)

- **M11 — Controlled Staging Deployment:** deploy backend (Render) + frontend (Vercel), managed PostgreSQL/pgvector + Qdrant + S3, run Alembic migrations on PostgreSQL, execute the deferred live integration tests and the 4 M05 physical recovery drills.
- **M12 — Enterprise SSO (SAML/OIDC) & Cross-Tenant Analytics.**

**Known pre-M11 blockers (from M10 Final Integration Audit):** migration `0003` SQLite incompatibility (MIG-1); 6 failing stale tests; `fastembed` + `aioboto3` missing from `pyproject.toml`; frontend invite roles `manager`/`admin` absent from backend catalog (SEC-1); staging storage must be S3-backed.
