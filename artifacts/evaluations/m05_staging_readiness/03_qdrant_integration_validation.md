# M05 Phase 2 — Qdrant Live Integration & Vector Lifecycle Report

**Project:** Multi-Tenant AI Platform / CaaS  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Execution Date:** 2026-11-07  
**Auditor:** Senior Vector Database & Integration Test Engineer  
**Status:** **PARTIAL (Adapter Logic & Dimension Separation Validated; Dedicated Integration Suite Created; Live Daemon Run Paused Due to Host RAM Threshold)**

---

## 1. Environment & Resource State

| Metric / Parameter | Value | Assessment |
|---|---|---|
| **Host OS** | Windows 11 Home / Pro (amd64) | Verified |
| **Python Version** | Python 3.12.3 (`backend\.venv`) | Verified |
| **`qdrant-client` Library** | Version 1.9.0 | Installed |
| **Target Qdrant Image** | `qdrant/qdrant:v1.9.0` | Verified in Compose specification |
| **Target Port** | `127.0.0.1:6333` (HTTP) / `6334` (gRPC) | Verified free (no conflicting binds) |
| **Docker Engine Daemon** | **STOPPED** (`//./pipe/docker_engine` not found) | Service inactive |
| **Available Host RAM** | **~1.31 GB** (1,347,072 KB) | **BELOW 2.0 GB SAFETY THRESHOLD** |
| **Resource Safety Decision** | Container start held per M05 rules | Host stability protected |

---

## 2. Qdrant Adapter Architecture & Codebase Inspection

Inspected [`backend/app/vectorstores/qdrant_store.py`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/vectorstores/qdrant_store.py):

### A. Dimensional Isolation (Option B)
- **Collection Naming:** `_collection_for_dim(self, dims: int) -> str` returns `{self.collection_name}_{dims}` (e.g. `mmaip_knowledge_chunks_384` vs `mmaip_knowledge_chunks_1536`).
- **Safety Guarantee:** Collections in Qdrant have an immutable vector dimensionality fixed at creation. By isolating collections by dimensionality, 384-dimensional models (such as `all-MiniLM-L6-v2`) and 1536-dimensional models (such as `text-embedding-3-small`) never collide in the same physical space.
- **Batch Dimension Consistency:** Line 92 validates that all points in an upsert batch have uniform dimensions matching the declared size before transmission to Qdrant.

### B. Payload Indexing & Fast Lookups
In `_ensure_collection` (lines 68–78), the adapter automatically provisions keyword and integer payload indices:
- `tenant_id`: `PayloadSchemaType.KEYWORD`
- `knowledge_base_id`: `PayloadSchemaType.KEYWORD`
- `embedding_version`: `PayloadSchemaType.INTEGER`

This guarantees $O(1)$ filtered lookups on large multi-tenant indexes rather than performing full collection scans.

### C. Mandatory Tenant Filtering on Search
In `search()` (lines 141–175), `must_conditions` enforces:
```python
must_conditions = [
    qmodels.FieldCondition(key="tenant_id", match=qmodels.MatchValue(value=str(filter_criteria.tenant_id))),
    qmodels.FieldCondition(key="embedding_version", match=qmodels.MatchValue(value=filter_criteria.embedding_version)),
]
```
The tenant filter cannot be omitted or overridden from client parameters.

### D. Scoped Deletions
`delete(chunk_ids, tenant_id)` and `delete_document(document_id, tenant_id)` wrap chunk IDs in a filter selector requiring `tenant_id == str(tenant_id)`. Guessing chunk UUIDs or document UUIDs across tenants cannot delete foreign vectors.

### E. Source of Truth Boundary
The relational PostgreSQL database remains the authoritative permission boundary:
- Retrieved Qdrant candidates pass through [`RetrievalAuthorizer.filter_authorized_candidates`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/retrieval/authorization.py#L66-L115).
- If a document was soft-deleted (`DELETED`), superseded by a newer version, or belongs to a restricted department, it is discarded regardless of its presence in Qdrant payloads.

---

## 3. Safe Reindexing & Vector Lifecycle

The platform enforces a non-destructive reindexing lifecycle:

```text
Step 1: Create new immutable EmbeddingVersion (e.g. version = 2, dims = 384)
Step 2: Adapter creates target space {collection_name}_{dims}
Step 3: Ingestion worker generates and upserts embeddings with embedding_version = 2
Step 4: Validate indexing completeness and basic retrieval integrity
Step 5: Atomically switch RetrievalConfig.embedding_version = 2 in relational DB
Step 6: Previous vector space (version = 1) is retained for immediate rollback capability
Step 7: Obsolete vectors pruned only after verified retention window
```

---

## 4. Dedicated Qdrant Integration Suite

Created [`backend/tests/integration/test_qdrant_live_integration.py`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/tests/integration/test_qdrant_live_integration.py) registered with the `qdrant_integration` pytest marker:

| Test Case | Objective | Target Feature Verified |
|---|---|---|
| `test_qdrant_service_connectivity_and_health` | Verify health check endpoint | Connects to `get_collections()` and confirms status is healthy |
| `test_qdrant_collection_creation_and_dimension_isolation` | Test collection isolation | Asserts spaces `test_m05_xxx_384` and `test_m05_xxx_4` are created separately |
| `test_qdrant_upsert_and_filtered_search` | Test vector upsert & search | Upserts 384-dimensional vectors and ranks nearest neighbor |
| `test_qdrant_cross_tenant_payload_isolation` | Test cross-tenant isolation | Confirms Tenant B queries return 0 results for Tenant A points |
| `test_qdrant_scoped_deletion` | Test tenant-scoped deletion | Confirms Tenant B cannot delete Tenant A chunks |

### Test Execution Evidence:
- **Command:** `.venv\Scripts\python -m pytest tests/integration/test_qdrant_live_integration.py -v`
- **Result:** **5 skipped in 2.50s (0 failures, 0 errors)**.
- **Skip Reason:** Live Qdrant vector database is offline at `http://127.0.0.1:6333` (`is_qdrant_online()` detected offline daemon and skipped with clear resume guidance).

---

## 5. Isolated Qdrant Compose Specification

Created [`docker-compose.m05-qdrant.yml`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docker-compose.m05-qdrant.yml):
- **Image:** `qdrant/qdrant:v1.9.0`
- **Port:** Binds to `127.0.0.1:6333` (HTTP) and `6334` (gRPC).
- **Memory Limit:** Strict `256m` memory limit (extremely lightweight, CPU only, zero GPU).
- **Healthcheck:** Automatic TCP ping test on port 6333.

---

## 6. Exact Instructions for Manual Live Execution

Once host physical RAM is freed:

```powershell
# 1. Start Docker Desktop and confirm engine is running
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
docker info

# 2. Start the isolated, lightweight (256 MB) Qdrant container
Set-Location "E:\MM Office\Multi-Tanant-CaaS"
docker compose -f docker-compose.m05-qdrant.yml up -d

# 3. Execute the live Qdrant integration suite
Set-Location "E:\MM Office\Multi-Tanant-CaaS\backend"
.venv\Scripts\python -m pytest tests/integration/test_qdrant_live_integration.py -m qdrant_integration -v

# 4. Stop the container when finished
Set-Location "E:\MM Office\Multi-Tanant-CaaS"
docker compose -f docker-compose.m05-qdrant.yml down
```

---

## 7. Git Status

```powershell
git status --short
 M backend/alembic/versions/0004_assistants_and_conversations.py
 M backend/app/assistant_runtime/runtime.py
 M backend/app/llm/providers/openai_provider.py
 M backend/pyproject.toml
?? artifacts/evaluations/m05_staging_readiness/02_postgresql_pgvector_validation.md
?? artifacts/evaluations/m05_staging_readiness/03_qdrant_integration_validation.md
?? artifacts/evaluations/m05_staging_readiness/results/
?? backend/tests/integration/
?? docker-compose.m05-postgres.yml
?? docker-compose.m05-qdrant.yml
```

---

## 8. Phase Boundary Stop Condition

Per M05 instructions, execution has stopped here. **Phase 3 (Retrieval Quality, Hybrid Ranking, and Evaluation Correction) has not been started.**

Awaiting your review and approval before proceeding to Phase 3.
