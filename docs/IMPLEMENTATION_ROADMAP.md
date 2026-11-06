# MM AI Platform — Implementation Roadmap

This roadmap documents the phased evolution from the current core multi-tenant foundation to an enterprise-grade AI chatbot platform.

---

## Phase 1: Foundation, Multi-Tenant Core & Identity (Current Milestone)
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
- [ ] Multi-format parsing pipeline (PDF, DOCX, TXT, CSV, XLSX, PPTX, JSON, SQL)
- [ ] OCR integration for scanned documents & images (local Tesseract and Badho OCR adapter)
- [ ] Document chunking strategies (recursive character, semantic boundary, markdown header splitting)
- [ ] Background job worker (async ingestion pipeline with status tracking & retry queues)
- [ ] Local filesystem storage and S3-compatible cloud storage abstractions

---

## Phase 3: Embeddings, Vector Stores & Hybrid Retrieval
- [ ] Embedding adapter layer (Local Sentence-Transformers, OpenAI-compatible via OmniRoute)
- [ ] Dual vector store backend:
  - PostgreSQL pgvector extension for co-located relational + vector queries
  - Qdrant integration for high-throughput standalone vector search
- [ ] Full-Text Search (FTS) using PostgreSQL `tsvector` and `tsquery`
- [ ] Reciprocal Rank Fusion (RRF) for hybrid keyword + vector retrieval
- [ ] Re-ranking pipeline (Cross-Encoder models)

---

## Phase 4: Chat Orchestration & OmniRoute Gateway Integration
- [ ] Conversation and message streaming via Server-Sent Events (SSE)
- [ ] OmniRoute Gateway integration (`http://localhost:20128/v1`) with dynamic model selection (`auto`)
- [ ] Context window assembly with grounded citations and chunk references
- [ ] Assistant prompt templates, system instructions, and persona configurations
- [ ] Multi-turn conversational memory with sliding window context management

---

## Phase 5: Enterprise Controls, Observability & Analytics
- [ ] Arize Phoenix / OpenTelemetry distributed tracing and LLM evaluation
- [ ] Tenant quota enforcement (storage caps, monthly token budgets, concurrency limits)
- [ ] Ragas & DeepEval continuous RAG quality assessment
- [ ] Embeddable web widget for public customer-support assistants
- [ ] Fine-grained BYOK (Bring-Your-Own-Key) credential management for enterprise tenants
