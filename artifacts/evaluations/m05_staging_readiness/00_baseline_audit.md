# M05 Phase 0 — Baseline Repository & Architecture Audit

**Project:** Multi-Tenant AI Platform / CaaS  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Remote Git:** `https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS.git`  
**Execution Date:** 2026-11-07  
**Auditor:** Principal Software Architect & QA Lead  
**Execution Phase:** Phase 0 — Baseline Repository Audit  

---

## 1. Executive Summary & Verification of Historical Claims

This audit establishes the ground truth of the repository at the start of **M05: Staging Readiness & Production Validation**. All historical claims from previous milestone reports have been independently inspected against actual source code, database models, migrations, tests, and runtime environments.

| Historical Claim | Code Inspection Status | Test Verification Status | Ground Truth Finding |
|---|---|---|---|
| **M01: Multi-Tenant Foundation (RBAC, Tenants, Auth)** | Verified | **PASS** (16/16 tests pass) | Complete implementation with Argon2id, JWT, 8 roles, granular permissions, tenant isolation repositories. Runs on SQLite in unit tests. |
| **M02: Document Ingestion, OCR & Parsers** | Verified | **PASS** (19/19 tests pass) | Multi-format parsers (PDF, DOCX, XLSX, PPTX, CSV, JSON, SQL, TXT, MD), chunking strategies, SHA-256 deduplication. Badho OCR is an honest placeholder; Tesseract has graceful fallback. |
| **M03.1: Vector Store Isolation by Dimension** | Verified | **PASS** (6/6 tests pass) | Dimensional isolation implemented in `PgVectorStore` (raises ValueError on mismatch) and `QdrantVectorStore` (`{collection}_{dims}`). Tested against SQLite and mock payload logic. |
| **M03.1: Relational Authorization (`RetrievalAuthorizer`)** | Verified | **PASS** (5/5 tests pass) | Independent secondary authorization filter checks department and tenant ACLs before returning vector/FTS search results. |
| **M03.2: CPU Semantic Embeddings (`fastembed` ONNX)** | Verified | **PASS** (6/6 tests pass) | `SentenceTransformerProvider` uses lightweight ONNX runtime (`all-MiniLM-L6-v2`, 384 dims, ~22 MB model) with bounded memory on CPU. |
| **M03.2: Retrieval Benchmark (25 queries, 6 docs)** | Verified | **PASS** (Harness executed) | Benchmark in `backend/evaluations/` separates answerable queries (N=22) from unanswerable queries (N=3). Semantic Recall@3 is 100%, MRR is 0.9697, No-Answer rejection is 100%. |
| **M03.3: Native PostgreSQL / pgvector Live Integration** | Partially Verified | **NOT RUN** | Migrations `0001`–`0004` contain valid pgvector DDL and FTS queries, but existing pytest runs exclusively on `sqlite+aiosqlite:///:memory:`. Real PostgreSQL has not run in automated tests. |
| **M03.3: Qdrant Live Service Integration** | Partially Verified | **NOT RUN** | Adapter logic implemented and collection naming tested, but live Qdrant daemon connection has not run (daemon offline). |
| **M04: Assistant Runtime, SSE Streaming, Citations** | Verified | **PASS** (5/5 tests pass) | `Assistant`, `AssistantKnowledgeBase`, `Conversation`, `Message`, and `MessageCitation` models and migration `0004` active. SSE endpoint `/api/v1/conversations/{id}/messages/stream` implemented. Context manager enforces `<KNOWLEDGE_BASE_CONTEXT>` prompt injection boundaries. |
| **Frontend: Linear × Apple Notes Chat & Assistants UI** | Verified | **PASS** (Next.js build clean) | UI implemented in `frontend/app/dashboard/assistants/page.tsx` with streaming chat, interactive `[1]` citation chips, and citation preview drawer. |

---

## 2. Git & Working Tree Safety Audit

Command outputs executed at baseline:
```powershell
git status --short
# (empty - working tree clean)

git branch --show-current
# main

git log -5 --oneline
# 448431c feat: complete M03.1-M03.3 hardening, CPU semantic embeddings, and M04 Conversational RAG
# bacd566 feat(milestone-02): implement secure document ingestion, extraction, OCR, chunking engine and rename to Multi-Tenant AI Platform-CaaS
# 11c77af feat: implement Next.js enterprise SaaS frontend with workspace switcher and RBAC management
# 7b5d010 feat: implement backend modular monolith, multi-tenant RBAC, and security regression suite
# 585d560 docs: establish architecture and engineering standards

git remote -v
# origin https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS.git (fetch)
# origin https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS.git (push)

git rev-parse HEAD
# 448431c4b004dc4b134dc94705b7dd96d0f2a9f5
```

- **Uncommitted Changes:** None. The working tree is completely clean.
- **Remote Synchronization:** Up to date with `origin/main`.
- **Safety Directive:** No destructive commands (`git reset --hard`, `git clean -fd`) shall be executed. All work proceeds incrementally.

---

## 3. Baseline Quality Gates Execution Results

### 3.1 Backend Test Suite (Pytest)
- **Command:** `.venv\Scripts\python -m pytest tests/ -v`
- **Platform:** Windows 11, Python 3.12.3, pytest-9.2.0
- **Database Engine:** `sqlite+aiosqlite:///:memory:`
- **Result:** **70 passed in 77.73 seconds (100% pass rate)**
- **Breakdown:**
  - `test_assistants_and_rag.py`: 5 passed
  - `test_auth.py`: 5 passed
  - `test_chunking.py`: 6 passed
  - `test_document_tenant_isolation.py`: 2 passed
  - `test_embedding_providers.py`: 6 passed
  - `test_health.py`: 2 passed
  - `test_hybrid_retrieval.py`: 3 passed
  - `test_ingestion_pipeline.py`: 3 passed
  - `test_ingestion_to_embedding.py`: 2 passed
  - `test_ocr.py`: 4 passed
  - `test_organizations_and_departments.py`: 2 passed
  - `test_parsers.py`: 9 passed
  - `test_password_hashing.py`: 2 passed
  - `test_rbac_permissions.py`: 1 passed
  - `test_retrieval_security.py`: 5 passed
  - `test_tenant_isolation_security.py`: 5 passed
  - `test_tenants.py`: 2 passed
  - `test_vector_stores.py`: 6 passed

### 3.2 Backend Code Quality (Ruff)
- **Command:** `.venv\Scripts\ruff check .`
- **Result:** **3 fixable lint issues detected**:
  1. `alembic/versions/0004_assistants_and_conversations.py:9:1`: `I001` Unsorted import block.
  2. `app/assistant_runtime/runtime.py:3:1`: `I001` Unsorted import block.
  3. `app/llm/providers/openai_provider.py:11:29`: `F401` Unused import `app.core.config.settings`.

### 3.3 Frontend Lint (ESLint)
- **Command:** `npm run lint` (in `frontend/`)
- **Result:** **0 errors, 19 warnings**
  - All warnings are non-blocking `@typescript-eslint/no-unused-vars` and `react-hooks/exhaustive-deps`.

### 3.4 Frontend Production Build (Next.js 16.4.5 Turbopack)
- **Command:** `npm run build` (in `frontend/`)
- **Result:** **PASS (15/15 static pages prerendered in 1904ms)**
  - Routes verified: `/`, `/_not-found`, `/dashboard`, `/dashboard/assistants`, `/dashboard/audit`, `/dashboard/departments`, `/dashboard/employees`, `/dashboard/groups`, `/dashboard/knowledge`, `/dashboard/settings`, `/dashboard/workspace`, `/login`, `/register`.

---

## 4. Hardware Constraints & Environment Inventory

- **Host Machine:** Windows 11, Intel Core i3-7100U / HD Graphics 620, no dedicated GPU.
- **Physical Memory:** Total 8.00 GB; Available Free Physical Memory: **1.42 GB**.
- **Docker Daemon:** Docker Desktop CLI 25.0.3 installed, but **Docker engine daemon is NOT running**.
  - Attempting to launch Docker Desktop under 1.42 GB free memory risks heavy swapping/thrashing.
  - Integration testing strategies must accommodate lightweight, standalone, or strictly isolated container execution.
- **OmniRoute Local Gateway:** Configured as default URL `http://localhost:20128/v1` in `.env.example`, but runtime gracefully falls back to direct OpenAI BYOK or deterministic mock provider when OmniRoute is offline.
- **Local Database:** No native PostgreSQL service running in Windows services; unit tests run in memory via SQLite.

---

## 5. Architectural Discovery & Codebase Structure

The codebase is organized as a strict, clean **Modular Monolith**:

```text
E:\MM Office\Multi-Tanant-CaaS\
├── backend\
│   ├── alembic\versions\             # 4 sequential schema migrations (0001 - 0004)
│   ├── app\
│   │   ├── api\v1\                   # 16 versioned API routers
│   │   ├── assistant_runtime\        # ContextManager (prompt boundaries) & Runtime (SSE, RAG)
│   │   ├── chunking\                 # Recursive, markdown, table, token-bounded chunkers
│   │   ├── core\                     # Security, crypto (Fernet), config, constants
│   │   ├── database\                 # Async SQLAlchemy session and base mixins
│   │   ├── embeddings\               # Providers: fastembed ONNX, local projection, mock, OpenAI
│   │   ├── llm\                      # Universal OpenAI-compatible gateway & test mock
│   │   ├── models\                   # Tenant, User, KB, Document, Assistant, Conversation
│   │   ├── parsers\                  # 9 file format parsers
│   │   ├── repositories\             # Tenant-scoped database access layer
│   │   ├── retrieval\                # RRF fusion, authorizer, reranker, citation service
│   │   ├── schemas\                  # Pydantic v2 request/response schemas
│   │   └── vectorstores\             # PgVectorStore, FtsStore, QdrantStore
│   ├── evaluations\                  # 25-query benchmark dataset and runner
│   └── tests\                        # 19 test files (70 test cases)
├── frontend\                         # Next.js 16 (App Router, Tailwind CSS, Lucide, TypeScript)
├── infrastructure\                   # Docker Compose, Dockerfiles, init-db.sql
└── artifacts\evaluations\            # Master execution reports & audit records
```

---

## 6. Discrepancy & Evaluation Accounting Resolution

The benchmark evaluation accounting question raised in the M05 specification has been thoroughly investigated:

- **Claim:** 25 queries, but percentages appeared to use a denominator of 22.
- **Investigation:** In `backend/evaluations/dataset.json` and `backend/evaluations/evaluate_retrieval.py`:
  - `num_queries`: 25
  - `answerable_queries`: 22 (used for ranking evaluation: Recall@K, Precision@K, MRR, nDCG)
  - `unanswerable_queries`: 3 (evaluated specifically for out-of-domain / no-answer rejection)
- **Conclusion:** The accounting is scientifically sound: calculating Recall on queries with 0 ground-truth chunks would result in zero-division errors or false degradation. The 3 unanswerable queries achieved **100% rejection accuracy** (cosine similarity < 0.40).

---

## 7. Known Risks & Implementation Plan

### Identified Gaps:
1. **Live PostgreSQL & pgvector Validation:** Tests currently run on SQLite. Real pgvector queries (cosine `<=>` operator, GIN indexes) must be validated with an actual PostgreSQL 16 environment.
2. **Qdrant Live Integration:** Qdrant collection life cycle has not been validated against a running instance.
3. **Prompt Injection Hardening:** While `<KNOWLEDGE_BASE_CONTEXT>` tags exist, explicit adversarial test cases (indirect injection, system prompt exfiltration attempts) need to be formally executed.
4. **Credential Rotation & Recovery:** Fernet key backup and restore procedures must be documented and tested.
5. **PDF Citation Highlighting:** Citation provenance contains document metadata and page numbers, but visual chunk bounding box highlighting in the frontend preview modal requires implementation.

### Sequential M05 Execution Order:
- **Phase 0:** Baseline Audit *(Current)*
- **Phase 1:** Real PostgreSQL 16, FTS, and pgvector Validation
- **Phase 2:** Qdrant Live Integration and Vector Lifecycle
- **Phase 3:** Retrieval Quality, Hybrid Ranking, and Evaluation Re-run
- **Phase 4:** Tenant Isolation, Resource ACL, and Assistant Security
- **Phase 5:** Prompt Injection and RAG Input Security
- **Phase 6:** LLM Provider, Streaming, and Failure Validation
- **Phase 7:** Database Migrations, Recovery, and Backup/Restore
- **Phase 8:** Staging Deployment Readiness
- **Phase 9:** PDF Citation Highlighting
- **Phase 10:** Expanded Regression Suite
- **Phase 11:** Architecture & Code Quality Review
- **Phase 12:** Documentation & Operational Handover
- **Phase 13:** Final M05 Release Sign-Off
