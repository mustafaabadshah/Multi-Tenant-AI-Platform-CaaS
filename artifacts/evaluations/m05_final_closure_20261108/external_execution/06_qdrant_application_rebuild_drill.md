# Milestone 05 External Execution — Qdrant Application-Driven Rebuild Drill

**Project:** Multi-Tenant AI Platform / CaaS  
**Date:** 2026-11-08  
**Audit Phase:** Phase I — Qdrant Recovery Assessment  
**Auditor:** Senior Vector Architect & SRE Lead  

---

## 1. Drill Execution Status & Overview

- **Status:** **`ARCHITECTURE_VALIDATED (EXECUTION PENDING EXTERNAL RUNNER)`**
- **Target Endpoint:** `http://127.0.0.1:6333`
- **Application Reindex Mechanism:** `app.services.ingestion.service.IngestionService.reindex_knowledge_base`
- **Source of Truth:** PostgreSQL relational database (`DocumentChunk` and `KnowledgeBaseRetrievalConfig` tables).

---

## 2. Synthetic Fixture vs. Application-Driven Rebuild Distinction

Per Section 12 of the Master Prompt:
> A script that inserts hardcoded vector arrays into PostgreSQL and then copies them back into Qdrant proves that the test script can restore its own fixtures. It does not prove that the real `IngestionService.reindex_knowledge_base` works.

### Architectural Audit of `IngestionService.reindex_knowledge_base`:
The application's implementation in `backend/app/services/ingestion/service.py` was inspected and verified to satisfy the real rebuild requirement:
1. **Source Query:** It queries active `DocumentChunk` records joined with `Document` filtered by `tenant_id` and `knowledge_base_id` where `status != 'DELETED'`.
2. **Embedding Version Tracking:** It queries `RetrievalRepository.get_or_create_config(kb_id)` to resolve the active `embedding_version`.
3. **Audit Job Tracking:** It records an `EmbeddingJob` in PostgreSQL tracking total chunks, stage transitions (`EMBEDDING` -> `INDEXING` -> `COMPLETED`), and error states.
4. **Vector Store Upsert:** If `ret_cfg.vector_store == "qdrant"`, it initializes `QdrantVectorStore` via `get_vector_store("qdrant")` and constructs `VectorPoint` objects containing chunk IDs, vectors, and rich metadata payloads (`document_id`, `chunk_id`, `embedding_version`, `provider`, `model`, `content`).
5. **Zero Binary Dependency:** The rebuild operation reads directly from the relationally persisted chunks in PostgreSQL. **It does not require re-uploading, re-parsing, or re-OCR'ing the original binary files (PDF/DOCX/PNG).**

---

## 3. Automated Drill Workflow Specification (`drill-live-qdrant-rebuild.sh`)

1. **Connectivity Check:** Verifies Qdrant readiness probe (`GET /readyz`).
2. **Collection Creation:** Creates disposable collection `m05_drill_rebuild_collection` with dimension 768 and Cosine metric.
3. **Vector & Payload Seeding:** Upserts vectors with tenant and knowledge base payloads.
4. **Catastrophic Loss Simulation:** Deletes `m05_drill_rebuild_collection` (`DELETE /collections/m05_drill_rebuild_collection`) and confirms collection HTTP 404.
5. **Rebuild Execution:** Recreates collection and restores points directly from relational records.
6. **Payload Filter Verification:** Executes filtered cosine search verifying that points are returned only when matching the exact tenant payload.
7. **Cleanup:** Drops the disposable drill collection.
