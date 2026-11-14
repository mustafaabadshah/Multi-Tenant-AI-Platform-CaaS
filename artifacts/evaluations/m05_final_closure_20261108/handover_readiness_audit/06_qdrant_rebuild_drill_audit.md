# Milestone 05 External Execution — Qdrant Application-Driven Rebuild Drill Audit

**Project:** Multi-Tenant AI Platform / CaaS  
**Target Script:** `infrastructure/scripts/drill-live-qdrant-rebuild.sh`  
**Application Entrypoint:** `backend/app/services/ingestion/service.py` (`IngestionService.reindex_knowledge_base`)  
**Audit Phase:** Phase 7 — Qdrant Rebuild Drill Audit  
**Auditor:** Senior Vector Architect & SRE Lead  

---

## 1. Compliance Checklist (Section 7 Requirements)

| # | Audit Requirement | Script Implementation Detail | Audit Finding |
|---|---|---|---|
| 1 | Creates disposable test data in PostgreSQL | Omitted in shell script (does not interact with PostgreSQL) | **DEFECT / OMISSION** |
| 2 | Persists document chunks & retrieval config in DB | Omitted in shell script | **DEFECT / OMISSION** |
| 3 | Creates disposable Qdrant collection | Lines 35–45: Creates `m05_drill_rebuild_collection` via `curl PUT` | **COMPLIANT** |
| 4 | Deletes collection to simulate catastrophic loss | Lines 70–78: Deletes collection via `curl DELETE` and asserts 404 | **COMPLIANT** |
| 5 | Invokes actual application reindex service | Omitted: Script does not execute Python `IngestionService` | **DEFECT / OMISSION** |
| 6 | Reads source chunks from PostgreSQL | Omitted: Script does not query database | **DEFECT / OMISSION** |
| 7 | Recreates collection via actual vector-store code | Lines 82–106: Recreates collection and points using raw `curl` | **FIXTURE-ONLY** |
| 8 | Executes real search after rebuild | Lines 110–123: Executes `/points/search` with tenant filter | **COMPLIANT** |
| 9 | Verifies tenant-scoped filtering | Lines 115–127: Asserts `tenant_id == "tenant_drill_01"` | **COMPLIANT** |
| 10 | Cleans up only disposable test resources | Lines 134–136: Deletes `m05_drill_rebuild_collection` | **COMPLIANT** |

---

## 2. In-Depth Technical Finding: Fixture Restoration vs. Real Rebuild

### The Shell Script Reality:
In `infrastructure/scripts/drill-live-qdrant-rebuild.sh`:
- **Line 50:** `SAMPLE_VECTOR=$(python3 -c "import json; v = [0.05]*768; v[0] = 0.9; print(json.dumps(v))")`
- **Lines 52–67:** Inserts the hardcoded `SAMPLE_VECTOR` into Qdrant using `curl`.
- **Lines 70–78:** Deletes the collection.
- **Lines 82–106:** Re-creates the collection and re-inserts the exact same hardcoded `SAMPLE_VECTOR` using `curl`.

### The Application Reality (`backend/app/services/ingestion/service.py`, lines 456–536):
```python
async def reindex_knowledge_base(self, knowledge_base_id: uuid.UUID | str) -> Any:
    # 1. Fetch all active chunks in this KB joined with Document where status != 'DELETED'
    # 2. Query RetrievalRepository for active embedding_version
    # 3. Create tracked EmbeddingJob (status: PROCESSING, stage: EMBEDDING)
    # 4. Generate embeddings via EmbeddingService
    # 5. Initialize qdrant_store = get_vector_store("qdrant")
    # 6. Execute await qdrant_store.upsert(qpoints, self.tenant_id, kb_id)
    # 7. Update EmbeddingJob to COMPLETED
```
`IngestionService.reindex_knowledge_base` is an enterprise-grade, relational-backed reindexer. However, `drill-live-qdrant-rebuild.sh` does **not** call this method; it executes a synthetic curl-based point recreation.

---

## 3. Drill Classification & Recommendation

### Classification:
**`FIXTURE_RESTORE_ONLY`** (per Section 7 & 12 directives: *"A script that recreates hardcoded vectors or copies fixture vectors directly into Qdrant is NOT an application-driven rebuild. If Qdrant rebuild is fixture-only, do not classify as HANDOVER_READY."*)

### Recommended Operator Enhancement:
On the external Linux runner, the operator should execute a Python script that invokes the real application service:
```python
from app.services.ingestion.service import IngestionService
# Call await IngestionService(session, tenant_id).reindex_knowledge_base(kb_id)
# Verify qdrant_store.search returns the reconstructed points
```
This converts the recovery drill from `FIXTURE_RESTORE_ONLY` to genuine `APPLICATION_REBUILD_PASS`.
