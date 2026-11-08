# Milestone 05 — Qdrant Application-Driven Rebuild Implementation

**Audit Phase:** Defect B Remediation  
**Date:** 2026-11-08  
**Target Script:** `infrastructure/scripts/drill-live-qdrant-rebuild.sh`  
**Helper Module:** `backend/app/commands/drill_qdrant_rebuild.py`  
**Classification:** Promoted from `FIXTURE_RESTORE_ONLY` to **`APPLICATION_REBUILD_READY`**  

---

## 1. Remediation Details

### 1.1 From Synthetic Fixture to Application-Driven Recovery
The initial implementation of `drill-live-qdrant-rebuild.sh` re-created collections and synthetic points using hardcoded JSON via raw `curl`, completely bypassing the application's ingestion engine.

The drill now executes through `backend/app/commands/drill_qdrant_rebuild.py`, which:
1. Creates disposable `Tenant`, `KnowledgeBase`, `Document`, and two `DocumentChunk` records in PostgreSQL.
2. Configures `RetrievalConfig` to use Qdrant and the deterministic `mock` embedding provider (`mock-embedding-small`, 384 dimensions).
3. Invokes `IngestionService.reindex_knowledge_base` to generate initial embeddings and upsert points to Qdrant via `QdrantVectorStore.upsert`.
4. Executes initial tenant-filtered vector search to prove indexing and payload filtering work.
5. Simulates catastrophic collection loss by calling `client.delete_collection("mmaip_knowledge_chunks_384")`.
6. Invokes `IngestionService.reindex_knowledge_base` a second time to execute the actual application rebuild directly from PostgreSQL chunks.
7. Verifies that the rebuilt collection has exactly 2 points, content is retrieved for the authorized tenant, and cross-tenant searches return 0 points.
8. Executes a third reindex to prove **idempotency**: point count remains exactly 2 (zero duplicate points created).
9. Cleans up only the disposable collection and database records.

### 1.2 Mandatory Evidence Markers
All 8 required evidence markers are produced and verified:
1. `SOURCE_DATA_PERSISTED_PASS`: Source chunks and retrieval configuration committed in PostgreSQL.
2. `INITIAL_APPLICATION_INDEX_PASS`: Initial application indexing completed with job status `COMPLETED`.
3. `COLLECTION_LOSS_SIMULATED_PASS`: Collection deleted and verified absent from Qdrant.
4. `APPLICATION_REINDEX_ENTRYPOINT_INVOKED`: Production `IngestionService.reindex_knowledge_base` called.
5. `POSTGRES_SOURCE_RELOAD_PASS`: Chunks reloaded from relational database.
6. `QDRANT_REBUILD_PASS`: Collection and vectors recreated via `QdrantVectorStore.upsert`.
7. `TENANT_FILTER_VERIFICATION_PASS`: Rebuilt points searchable by authorized tenant; cross-tenant search isolated.
8. `IDEMPOTENT_REINDEX_PASS`: Repeated reindex produces exactly the same point count without duplicates.
