# M10 Stage 3 — Knowledge Management, Ingestion & Retrieval Audit Report

**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Milestone:** M10 Stage 3  
**Audit Scope:** Full Knowledge Lifecycle (Create KB → Ingest/Import → Validate → Process → Inspect → Configure → Attach to Assistant → Retrieve → Cite → Evaluate → Update/Rename → Reprocess → Remove/Archive)  
**Date:** 2026-11-10  
**Status:** COMPLETE  

---

## 1. Executive Summary

Milestone M10 Stage 3 audits and completes the end-to-end Knowledge Management, Ingestion, and Retrieval subsystem. The architecture was designed to provide ordinary users with an intuitive, zero-configuration document ingestion experience while exposing granular controls (chunking strategies, vector database selection, embedding dimensions, RRF fusion constant $k$, and retrieval sandboxes) for advanced administrators.

Prior to Stage 3, the foundational data models and ingestion parsers were present from Milestone 02 and Milestone 03, but had specific lifecycle gaps:
1. **Missing KB Update/Rename Endpoint:** `KnowledgeBaseUpdateRequest` was defined in Pydantic schemas, but `backend/app/api/v1/knowledge.py` lacked a `PATCH /{kb_id}` route.
2. **Hardcoded Document Count in Single KB Lookup:** `GET /api/v1/knowledge/{kb_id}` returned a hardcoded `document_count=0` rather than querying real active documents.
3. **Silent Lexical Fallback in Semantic Search:** If embedding generation failed when `target_mode == "semantic"`, lexical candidates were fetched into a local variable but were not assigned to the final candidate list, resulting in empty responses without diagnostic indication.
4. **Knowledge Studio Frontend UI Completeness:** The Knowledge Studio lacked UI controls to rename/edit KB metadata or trigger collection deletion from the workspace header.

All identified gaps were remediated with strict adherence to tenant isolation and security boundaries.

---

## 2. Knowledge Management Capability Matrix

| Lifecycle Capability | Backend Model / Service | API Route | Frontend UI Component | Test Coverage | Status & Audit Decision |
|---|---|---|---|---|---|
| **Create Knowledge Base** | `KnowledgeRepository.create` | `POST /api/v1/knowledge` | `KnowledgePage` (Create Container Modal) | `test_01`, `test_22` | **VERIFIED.** Scoped to active tenant with `ACTIVE` default status. |
| **Inspect / Read KB** | `KnowledgeRepository.get_by_id` + `get_document_count` | `GET /api/v1/knowledge/{id}` | `KnowledgePage` (Detailed KB View) | `test_01`, `test_22` | **VERIFIED.** Returns real document count, excluding soft-deleted documents. |
| **List Knowledge Bases** | `KnowledgeRepository.list_with_counts` | `GET /api/v1/knowledge` | `KnowledgePage` (Grid card view with doc count) | `test_01`, `test_22` | **VERIFIED.** Outer join on active documents; department-filtered. |
| **Rename / Update KB** | `KnowledgeRepository.update` | `PATCH /api/v1/knowledge/{id}` | `KnowledgePage` (Rename / Edit Modal) | `test_01`, `test_22` | **IMPLEMENTED.** Allows renaming and updating description; audit logged. |
| **Delete / Archive KB** | `TenantScopedRepository.delete` | `DELETE /api/v1/knowledge/{id}` | `KnowledgePage` (Delete KB confirmation dialog) | `test_01`, `test_22` | **VERIFIED.** Cascades to documents, versions, chunks, jobs, and embeddings. |
| **Multi-Assistant Association** | `AssistantKnowledgeBase` junction table | `POST/PUT /api/v1/assistants` | Assistant Wizard Step 3 & Workspace Studio | `test_02`, `test_18` | **VERIFIED.** Deleting one assistant does NOT destroy the shared KB. |
| **Upload Document** | `IngestionService.upload_document` | `POST /api/v1/knowledge/{id}/documents` | Drag-and-drop dropzone & file browser | `test_03`, `test_07` | **VERIFIED.** Enforces 50 MB limit, safe filename sanitization, SHA-256 dedup. |
| **URL Web Ingestion** | `fetch_url_content_safe` + `IngestionService` | `POST /api/v1/documents/ingest-url` | `KnowledgePage` (Ingest Web Page Modal) | `test_retrieval_security.py` | **VERIFIED.** Enforces SSRF guardrails (blocks RFC 1918, link-local, cloud metadata). |
| **Document Parsers** | `ParserRegistry` (TXT, MD, JSON, CSV, PDF, DOCX, XLSX, PPTX, SQL) | Automated in `IngestionService.execute_job` | Processed automatically upon upload | `test_04` | **VERIFIED.** Static AST parsing for SQL via `sqlglot`; zero live execution. |
| **OCR Processing** | `OCRRegistry` (Tesseract / Mock) | Ingestion Pipeline Step 4 | Pipeline Config Modal (toggle OCR, language) | `test_05` | **VERIFIED.** Graceful fallback when OCR is disabled or provider unavailable. |
| **Document Chunking** | `ChunkingRegistry` (recursive, structured, markdown, token) | Ingestion Pipeline Step 5 | Pipeline Config Modal (chunk size, overlap) | `test_06` | **VERIFIED.** Preserves `page_number`, `heading_path`, `chunk_hash`, and index. |
| **Durable Ingestion Jobs** | `IngestionJobRepository`, `run_ingestion_in_background` | `GET/POST /api/v1/ingestion/jobs/*` | Real-time status polling & history timeline | `test_08`, `test_09` | **VERIFIED.** Supports retry, cancellation, and restart recovery (`recover_orphaned_jobs`). |
| **Embedding Generation** | `EmbeddingService` + `EmbeddingRegistry` | `POST /api/v1/knowledge/{id}/reindex` | Workspace Retrieval Settings & Index Status | `test_10`, `test_21` | **VERIFIED.** Supports OmniRoute, OpenAI, local, mock; enforces dimension consistency. |
| **Vector Storage** | `PostgresFTSStore`, `PgVectorStore`, `QdrantVectorStore` | Retrieval & Vector API routes | Index Status Tab (`IndexStatusTab.tsx`) | `test_11`, `test_12` | **VERIFIED.** Chunks cascade-deleted upon document removal; no orphaned vectors. |
| **Lexical Retrieval** | `PostgresFTSStore.search_lexical` | `POST /api/v1/retrieval/search` | Search Sandbox (`RetrievalPreviewTab.tsx`) | `test_12`, `test_13` | **VERIFIED.** Pure full-text keyword retrieval without requiring embedding models. |
| **Semantic Retrieval** | `VectorStore.search` | `POST /api/v1/retrieval/search` | Search Sandbox (`RetrievalPreviewTab.tsx`) | `test_14` | **VERIFIED.** Cosine similarity nearest neighbor search with expected dimension validation. |
| **Hybrid Fusion (RRF)** | `reciprocal_rank_fusion` | `POST /api/v1/retrieval/search` | Search Sandbox with diagnostic inspector | `test_15` | **VERIFIED.** $1/(k + \text{rank})$ score merging; overlapping candidates elevated. |
| **Fail-Closed Allowlist** | `VectorStoreFilter.document_ids` | Retrieval & Vector query filters | Filter parameter in assistant inference | `test_16` | **VERIFIED.** Empty allowlist (`document_ids=[]`) returns 0 candidates immediately. |
| **Cross-Tenant Isolation** | `RetrievalAuthorizer.validate_knowledge_bases` | Unified in `RetrievalService.search` | Enforced transparently on all searches | `test_17` | **VERIFIED.** Adversarial search cannot discover or read other tenant documents. |
| **Assistant Authorization** | `AssistantKnowledgeBase` validation | Assistant Runtime RAG stage | Workspace Assistant Chat & Public Chat | `test_18`, `test_19` | **VERIFIED.** Assistants cannot query unconnected KBs; public chats exclude restricted docs. |
| **Citation Provenance** | `format_citations` | Returned in `SearchResponse.citations` | Chat messages citation badges & footnotes | `test_20` | **VERIFIED.** Citations include title, page, section; raw disk paths strictly excluded. |
| **Reprocessing & Cleanup** | `DocumentRepository.save_chunks` | `POST /api/v1/documents/{id}/reprocess` | Document table "Reprocess" icon button | `test_21` | **VERIFIED.** Atomically deletes old version chunks before saving new chunks. |
| **Knowledge Studio UX** | Next.js 16 App Router | Dashboard `/dashboard/knowledge` | Knowledge Base Grid, Document Table, Modals | `test_22`, typecheck, build | **VERIFIED.** Linear × Apple Notes design; real-time status polling, chunk inspection. |

---

## 3. In-Depth Subsystem Audits

### 3.1 Security & Tenant Boundary Enforcement
- **Composite Primary Keys & Scoping:** All queries across `KnowledgeRepository`, `DocumentRepository`, `IngestionJobRepository`, and `RetrievalRepository` enforce `WHERE tenant_id = :tenant_id`.
- **Authoritative Candidate Filtering:** `RetrievalAuthorizer.filter_authorized_candidates` executes an authoritative secondary database check on retrieved vector candidates, verifying:
  1. The document exists and belongs to the authenticated tenant.
  2. The document is not in `DELETED` status.
  3. The document does not belong to a different department (unless the actor is an admin).
  4. The document is not marked with `access_level="restricted"` when queried by non-admin or public actors.

### 3.2 SQL Parser Safety Verification
- **File:** `backend/app/parsers/sql_parser.py`
- **Audit Findings:** The SQL parser uses `sqlglot` for pure abstract syntax tree (AST) traversal. It identifies table definitions, columns, constraints, views, and indexes without connecting to or executing against any SQL engine. Uploaded `.sql` and `.ddl` files can never execute arbitrary commands or modify databases.

### 3.3 Offline Resilience & Lexical Fallback
- **File:** `backend/app/retrieval/service.py`
- **Audit Findings:** When the embedding provider is offline or unreachable:
  - Hybrid search catches the exception, logs a warning, and continues with lexical candidates.
  - Semantic search falls back to full-text lexical search and properly populates `candidates` with the lexical candidates.
  - Diagnostics transparently record `fallback_to_lexical=True`, `embedding_error="<details>"`, and `retrieval_mode_actual="lexical"`.
  - No misleading similarity scores are presented to users.

### 3.4 Background Job Idempotency and Recovery
- **File:** `backend/app/services/ingestion/recovery.py`
- **Audit Findings:** `recover_orphaned_jobs` identifies background jobs left in `PROCESSING` status during an abrupt server crash or process restart. It transitions them to `FAILED` with `error_category="PROCESS_RESTART"` and stage `"INTERRUPTED"`, updating the associated document and recording audit events so jobs can be cleanly retried by users without leaving zombie tasks.
