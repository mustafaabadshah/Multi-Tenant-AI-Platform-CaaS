# Critical Audit C — Real Application Reindex Evidence & Telemetry

## 1. Audit Finding on Snapshot V2 Telemetry

In Snapshot V2, `drill_qdrant_rebuild.py` emitted:
```python
print("APPLICATION_REINDEX_ENTRYPOINT_INVOKED")
async with session_maker() as rebuild_session:
    rebuild_service = IngestionService(rebuild_session, drill_tenant_id)
    rebuild_job = await rebuild_service.reindex_knowledge_base(drill_kb_id)
```
The marker `APPLICATION_REINDEX_ENTRYPOINT_INVOKED` was printed *before* the application method call. Printing a string before an async call does not prove the method was executed, that it succeeded, or that it retrieved persisted PostgreSQL source data.

## 2. Refactored Multi-Stage Telemetry Architecture

The drill and shell runner were updated to emit and enforce five distinct execution states:

1. `APPLICATION_REINDEX_ENTRYPOINT_INVOKED`: Entrypoint reached.
2. `APPLICATION_REINDEX_CALL_STARTED`: Emitted immediately prior to invoking `rebuild_service.reindex_knowledge_base(drill_kb_id)`.
3. `APPLICATION_REINDEX_CALL_RETURNED`: Emitted immediately upon method return with timestamps recorded.
4. `APPLICATION_REINDEX_COMPLETED`: Emitted only after verifying `rebuild_job.status == 'COMPLETED'` and `rebuild_job.processed_chunks == 2`.
5. `POSTGRES_SOURCE_RELOAD_VERIFIED`: Emitted after a fresh database session loads and validates persisted source chunks.
6. `QDRANT_REBUILD_VERIFIED`: Emitted after independent verification of reconstructed Qdrant collection point count, content payload, and foreign tenant rejection.

## 3. Persisted PostgreSQL Source Data Verification

The drill enforces that source data is genuinely persisted:
1. Chunks are committed to PostgreSQL in Step 1.
2. In Step 1b, a fresh, separate `AsyncSession` queries PostgreSQL for the chunks.
3. Chunks are counted and SHA-256 content hashes are recorded in telemetry.
4. Emits `SOURCE_DATA_PERSISTED_PASS` and `POSTGRES_SOURCE_RELOAD_VERIFIED`.

## 4. Idempotency Verification

In Step 7, `reindex_knowledge_base` is invoked a second consecutive time:
- Points count is verified to remain exactly 2 (zero duplicate points created).
- Emits `IDEMPOTENT_REINDEX_PASS`.

## 5. Structured JSON Evidence Output

The drill records structured telemetry to `qdrant_rebuild_evidence.json`:
- `drill_run_id`
- `disposable_tenant_id`
- `disposable_knowledge_base_id`
- `disposable_collection_base`
- `disposable_collection_full`
- `rebuild_invocation_start`
- `rebuild_invocation_end`
- `rebuild_job_id`
- `rebuild_job_status`
- `expected_point_count`
- `actual_point_count`
- `verification_result`: "PASS"
- `idempotency_result`: "PASS"

Secrets and raw document contents are strictly excluded.

## 6. Classification

**Result**: `APPLICATION_REINDEX_EVIDENCE_PASS`.
