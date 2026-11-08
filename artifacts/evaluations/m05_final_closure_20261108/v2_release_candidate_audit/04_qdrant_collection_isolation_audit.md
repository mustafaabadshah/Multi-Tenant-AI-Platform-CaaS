# Critical Audit B — Qdrant Collection Ownership & Deletion Safety

## 1. Tracing Application Collection Naming & Hardcoding Defect

In the previous remediation, `backend/app/commands/drill_qdrant_rebuild.py` contained:
```python
DRILL_COLLECTION_BASE = "mmaip_knowledge_chunks"
DRILL_COLLECTION_FULL = f"{DRILL_COLLECTION_BASE}_{DRILL_DIMS}"  # "mmaip_knowledge_chunks_384"
...
await qclient.delete_collection(DRILL_COLLECTION_FULL)
```
Inspection revealed that `mmaip_knowledge_chunks` is the platform-wide production collection prefix for vector knowledge chunks. Calling `delete_collection` on this name in a recovery drill could catastrophic wipe real knowledge base vectors if executed on an environment containing production or staging data.

## 2. Dynamic Collection Injection Architecture

To solve this without duplicating ingestion logic or breaking the dependency boundary:
1. **Configuration Setting Added**: Added `QDRANT_COLLECTION_NAME: str = "mmaip_knowledge_chunks"` to `Settings` in `backend/app/core/config.py`.
2. **QdrantVectorStore Dynamic Resolution**:
   In `backend/app/vectorstores/qdrant_store.py`:
   ```python
   self.collection_name = collection_name or getattr(settings, "QDRANT_COLLECTION_NAME", "mmaip_knowledge_chunks")
   ```
3. **Registry Convenience Support**:
   In `backend/app/vectorstores/registry.py`:
   `VectorStoreRegistry.get_store` accepts `custom_collection_name` and forwards it or falls back to `settings.QDRANT_COLLECTION_NAME`.
4. **IngestionService Seamless Integration**:
   When `IngestionService.reindex_knowledge_base` calls `get_vector_store("qdrant")`, it dynamically resolves the collection configured in `settings.QDRANT_COLLECTION_NAME`.

## 3. Dedicated Disposable Drill Namespace & Strict Safety Guards

In `backend/app/commands/drill_qdrant_rebuild.py`:
1. **Namespace Isolation**:
   ```python
   DRILL_COLLECTION_PREFIX = "m05_drill_disposable"
   disposable_base, drill_collection_full = build_disposable_collection_name(run_tag, DRILL_DIMS)
   # e.g. "m05_drill_disposable_abcd1234_384"
   ```
2. **Strict Guard Functions**:
   ```python
   def assert_disposable_drill_collection(collection_name: str) -> None:
       if not collection_name.startswith(f"{DRILL_COLLECTION_PREFIX}_"):
           raise ValueError(f"SAFETY ABORT: Refusing collection '{collection_name}'...")
       if "mmaip_knowledge_chunks" in collection_name or "production" in collection_name.lower():
           raise ValueError(f"SAFETY ABORT: Refusing collection '{collection_name}'. Protected namespace.")
   ```
3. **Scoped Deletion**:
   `safe_delete_drill_collection` asserts the collection belongs to the disposable namespace before calling the Qdrant client. It strictly refuses broad deletions or unapproved names.
4. **Environment Isolation**:
   The drill sets `settings.QDRANT_COLLECTION_NAME = disposable_base` and restores the original value in a `finally` block.

## 4. Isolation Failure Unit Tests

In `backend/tests/test_m05_recovery_drills_unit.py`, the following failure scenarios were implemented and passed:
- `test_qdrant_drill_rejects_application_wide_collection_name`: Rejection of `mmaip_knowledge_chunks` and `mmaip_knowledge_chunks_384`. `PASS`.
- `test_qdrant_drill_rejects_production_like_collection_name`: Rejection of `production_chunks`. `PASS`.
- `test_qdrant_drill_rejects_collection_without_drill_prefix`: Rejection of random collection names. `PASS`.
- `test_qdrant_drill_build_disposable_collection_name`: Verified prefix format. `PASS`.
- `test_qdrant_drill_safe_delete_refuses_foreign_or_production_collection`: Verified mock client deletion is never called on unauthorized collections. `PASS`.
- `test_qdrant_drill_safe_delete_allows_verified_disposable_collection`: Verified deletion succeeds only for validated disposable collections. `PASS`.

## 5. Classification

**Result**: `QDRANT_DISPOSABLE_ISOLATION_PASS`.
