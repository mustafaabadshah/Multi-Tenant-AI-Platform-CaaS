# Phase Zero: Initial Repository Audit

**Date:** 2026-11-07  
**Repository:** Multi-Tenant AI Platform-CaaS (`E:\MM Office\Multi-Tanant-CaaS`)  
**Branch:** `main` (commit `bacd566`)  
**Auditor:** Principal AI Platform Architect & Release Engineering Agent

---

## 1. Architectural Overview & System State

The platform is designed as an asynchronous, security-first modular monolith:
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic.
- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind CSS, Lucide icons, Linear × Apple Notes design direction.
- **Multi-Tenancy:** Dual tenancy (Individual & Organization workspaces), strict relational scoping on every tenant entity (`WHERE tenant_id = :tenant_id`), composite foreign keys, and role-based access control (RBAC).
- **Ingestion & Processing (Milestone 02):** Multi-format parser registry (PDF, DOCX, XLSX, PPTX, CSV, JSON, SQL, TXT, Markdown), OCR engine (Tesseract CPU fallback & Badho contract), chunking strategies (recursive, markdown, token, structured), and local storage abstraction.
- **Retrieval & Embeddings (Milestone 03 Foundation):**
  - Embedding providers: `omniroute`, `openai`, `local` (CPU feature projection), and `mock`.
  - Vector stores: `pgvector` (PostgreSQL vector search), `qdrant` (external vector database), and `fts` (PostgreSQL full-text search).
  - Hybrid retrieval with Reciprocal Rank Fusion ($RRF(d) = \sum \frac{1}{k + rank_r(d)}$) and secondary security authorization (`RetrievalAuthorizer`).
  - Frontend tabs in `/dashboard/knowledge`: Documents table & upload, Retrieval & vector settings, Search sandbox, and Index status.

---

## 2. Identified Deficiencies & Investigation Areas

### 2.1 Dimensionality & Vector Column Inconsistency (Crucial Finding)
In `backend/app/models/knowledge.py`:
`ChunkEmbedding` defines `embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)`.
However:
- Sentence-Transformers (`all-MiniLM-L6-v2`) produces **384-dimensional** embeddings.
- Small models produce **384** or **768** dimensions, while OpenAI produces **1536** (or customizable).
- In pgvector, a column declared as `Vector(1536)` strictly rejects vectors of dimension 384 or any non-1536 size.
- Storing vectors of differing dimensions in the same physical column or collection causes database constraint violations or corrupted distance calculations.
**Solution Required (M03.1):** Implement isolated vector spaces / separate collections by embedding configuration. For PostgreSQL / SQLite fallback, allow dimension-aware storage or separate vector columns/tables per dimension space, and strictly validate dimensions before database upsert and query.

### 2.2 Genuine Semantic Local Embedding Provider (M03.2)
Currently, `LocalEmbeddingProvider` in `backend/app/embeddings/providers/local_provider.py` implements a lightweight deterministic feature projection using SHA-256 tokens and character frequencies.
While fast, zero-dependency, and deterministic, it is **not a genuine semantic embedding model**.
**Solution Required (M03.2):** Add a genuine CPU-compatible semantic embedding provider using `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) with lazy loading, no automatic heavy downloads, clear unavailable-model behavior, and keep local feature projection explicitly labeled as a test/baseline projection.

### 2.3 External Services Availability & Testing Integrity
- **Docker Daemon:** Not currently running on the Windows host.
- **PostgreSQL / pgvector:** Native service not currently listening on port 5432.
- **Qdrant:** Not running on port 6333.
- **OmniRoute:** Not running on port 20128.
- **Testing Standard:** Unit tests pass against SQLite and mocks. In accordance with platform guidelines, real daemon tests for Qdrant and pgvector must be explicitly marked `NOT RUN` when daemon is offline rather than fabricated as passed.

### 2.4 Assistant Runtime & Conversational RAG (M04 Gap)
Currently, `backend/app/models/` contains stubs for assistants in Milestone 01, but:
- No complete conversational chat engine or message history persistence.
- No Server-Sent Events (SSE) streaming chat endpoint.
- No conversation context manager with token budget bounds.
- No assistant-to-knowledge-base RAG binding with execution-time permission revalidation.
- Frontend `/dashboard/assistants` is an early CRUD list without conversational chat or citation viewing.

---

## 3. Audit Summary

| Component | Status | Notes |
|---|---|---|
| Core RBAC & Multi-Tenancy | Solid | 100% negative security tests passing |
| Ingestion & Parsers | Solid | Robust format coverage and deduplication |
| Retrieval & Fusion | Operational | RRF and secondary authorization working |
| Dimensionality Strategy | Inconsistent | `Vector(1536)` fixed mapping requires dimension-space handling |
| Local Embeddings | Prototype | Feature projection needs genuine `all-MiniLM-L6-v2` semantic provider |
| Assistants & Chat RAG | Stubs only | Target of Milestone 04 |
