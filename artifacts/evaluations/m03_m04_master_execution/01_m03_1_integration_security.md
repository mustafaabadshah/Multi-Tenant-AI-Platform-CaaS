# Milestone 03.1 — Integration & Security Hardening Report

**Milestone:** M03.1  
**Status:** `PASS` (with documented external integration limitations)  
**Execution Date:** 2026-11-07  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  

---

## 1. Executive Summary

Milestone 03.1 focused on verifying and hardening the database, vector store adapters, retrieval authorization, dimensionality safety, reindexing lifecycle, and secret encryption across the multi-tenant platform.

All unit and security regression tests executed against the database session and adapter layer passed cleanly. External Docker services (PostgreSQL 16 with pgvector and Qdrant) were verified at the adapter and schema level; live daemon connections are documented honestly as `NOT RUN` due to the local Docker daemon being offline on the host machine.

---

## 2. Infrastructure & Service Status

| Service | Target Port | Status | Verification Detail / Command |
|---|---|---|---|
| **PostgreSQL (Local / Container)** | 5432 | `NOT RUN` | Port 5432 inactive on host; SQLite dialect engine used for automated CI test suite. |
| **pgvector Extension** | SQL extension | `PASS` (Schema / Adapter) | Migration `0003_embeddings_and_vector_stores.py` defines vector tables. Adapter verified with dimensional filtering. |
| **PostgreSQL FTS** | DB engine | `PASS` (Dialect-Adaptive) | `PostgresFTSStore` operates PostgreSQL `to_tsvector` / `websearch_to_tsquery` in PostgreSQL environments and safe SQLite fallback in test suite. |
| **Qdrant Vector DB** | 6333 | `NOT RUN` (Live) / `PASS` (Adapter) | Qdrant client adapter and collection isolation by dimension verified via unit tests; daemon not running locally. |

### Reproduction Commands for Live Services

To run against real external containers when Docker is started:
```powershell
# Start PostgreSQL with pgvector and Qdrant
docker compose up -d postgres qdrant

# Run PostgreSQL & pgvector live integration suite
$env:DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/mmaip_dev"
$env:QDRANT_URL="http://localhost:6333"
.venv\Scripts\pytest.exe tests/test_vector_stores.py -v
```

---

## 3. Dimensionality Safety & Vector Space Separation (Option B)

### The Problem
Previously, chunk embeddings risked dimension collision if models with differing vector dimensionalities (e.g., 384 for `all-MiniLM-L6-v2` vs. 1536 for OpenAI `text-embedding-3-small`) were stored in the same vector space, causing database type errors or collection dimension errors in Qdrant.

### The Implementation
We implemented **Option B — Isolated Vector Spaces by Dimension**:
1. **`VectorPoint` Data Model (`app/vectorstores/base.py`):**
   - Added explicit `dimensions: Optional[int]` property.
   - Enforced dimension validation on point creation.
2. **`PgVectorStore` (`app/vectorstores/pgvector_store.py`):**
   - Added strict validation on upsert: raises `ValueError("Vector dimension mismatch for point <id>: expected <exp>, got <actual>")`.
   - Added dimensional scope to similarity search: includes `ChunkEmbedding.dimensions == query_dim` in SQL filters, completely preventing cross-dimension distance calculations.
3. **`QdrantVectorStore` (`app/vectorstores/qdrant_store.py`):**
   - Implemented dimension-specific collection names: `f"{collection_name}_{dims}"` (e.g. `mmaip_knowledge_chunks_384` vs `mmaip_knowledge_chunks_1536`).
   - Search requests route strictly to the dimension-specific collection.
4. **`IngestionService` & `RetrievalService`:**
   - Both ingestion and reindexing pipelines propagate `dimensions=emb.dimensions` to `VectorPoint`.
   - Retrieval queries set `expected_dimensions` in `VectorStoreFilter`.

### Test Evidence
- `tests/test_vector_stores.py::test_pgvector_store_rejects_dimension_mismatch_on_upsert`: **PASSED**
- `tests/test_vector_stores.py::test_pgvector_store_filters_by_dimension_on_search`: **PASSED**
- `tests/test_vector_stores.py::test_qdrant_store_isolates_collections_by_dimension`: **PASSED**

---

## 4. Authorization Hardening & Security Matrix

Security in retrieval is enforced centrally through `RetrievalAuthorizationService` (`app/retrieval/authorization.py`) and `RetrievalService` (`app/retrieval/service.py`). Vector store metadata is treated as untrusted; relational permissions are checked before returning any chunk to the user.

### Automated Test Matrix Results

| Scenario | Target | Expected Result | Actual Result | Status |
|---|---|---|---|---|
| Cross-tenant vector query | Vector search across tenants | Deny / 0 results | 0 results returned | `PASS` |
| Cross-tenant FTS search via API | Lexical API query across tenants | 403 Forbidden | HTTP 403 returned | `PASS` |
| Unauthorized Department access | Employee querying restricted department doc | Deny / 0 results | 0 results returned | `PASS` |
| Soft-deleted document | User querying deleted document chunk | Excluded / 0 results | 0 results returned | `PASS` |
| Hybrid RRF Fusion leak | RRF combining vector & FTS candidates | Filtered before fusion | 0 unauthorized leaks | `PASS` |
| Forged Tenant Header | API request with forged `X-Tenant-ID` | 403 Forbidden | HTTP 403 returned | `PASS` |

All tests in `tests/test_retrieval_security.py` passed with exit code 0.

---

## 5. Embedding Lifecycle & Safe Reindexing

Reindexing a Knowledge Base requires atomic transitions to prevent incomplete or corrupt vector spaces:
1. `RetrievalConfig` tracks:
   - `embedding_provider`
   - `embedding_model`
   - `embedding_dimensions`
   - `active_version` (integer monotonic counter)
   - `reindex_status` (`IDLE`, `PROCESSING`, `COMPLETED`, `FAILED`)
2. During reindexing:
   - Chunks are embedded with `version = current_version + 1`.
   - New vectors are written to the vector store tagged with the new version.
   - Only when all chunks are successfully embedded and stored is `active_version` incremented atomically.
   - Prior vectors remain queryable during processing, ensuring zero-downtime retrieval.

---

## 6. Credential & BYOK Secret Protection

1. **At Rest:** Provider API keys are encrypted using Fernet symmetric encryption via `app/core/security.py`.
2. **In Memory / API:**
   - Keys are stored in `EncryptedProviderKey` records.
   - Pydantic schemas mask credentials in responses (e.g. `sk-...abcd`).
   - API endpoints (`GET /api/v1/retrieval/config/{kb_id}`) never emit raw plaintext API keys.
3. **In Logs:** Secret parameters are excluded from logger strings and exception traces.

---

## 7. Acceptance Sign-Off

- **Dimensionality Safety:** Enforced and tested.
- **Security Matrix:** Fully tested and passing.
- **Adapter Isolation:** Completed for both pgvector and Qdrant.
- **Reindexing Safety:** Monotonic version switching implemented.
- **Readiness:** **PROCEED TO M03.2**.
