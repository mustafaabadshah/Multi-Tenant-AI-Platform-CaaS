# M15.1 — Streaming Reliability, Failure Isolation & Telemetry Resilience

## 1. Core Architectural Principle: Non-Interference

Observability must **never degrade or break an otherwise healthy AI inference request**.

In M15.1, the telemetry subsystem was tested and hardened against the following adverse conditions:
1. Telemetry database connection timeouts or transaction failures.
2. Premature client disconnects (SSE stream termination by user).
3. Provider upstream exceptions and empty generation streams.
4. Quota check rejections and BYOK credential resolution failures.
5. Multiple finalization or retry executions.

---

## 2. Telemetry Database Failure Isolation

### Implementation in `backend/app/observability/tracer.py`:
`persist_to_database()` encapsulates all database interactions in a guarded try/except block:
```python
try:
    # Query existing trace to determine insert vs update
    stmt = select(RequestTrace).where(RequestTrace.trace_id == trace.trace_id)
    res = await session.execute(stmt)
    record = res.scalar_one_or_none()
    if record:
        # Update existing record in-place
        ...
    else:
        # Insert new record
        ...
    await session.commit()
except Exception as e:
    logger.warning(f"Failed to persist request trace {trace.trace_id} to database: {e}")
    try:
        await session.rollback()
    except Exception:
        pass
```

### Validation Evidence:
- **Test:** `backend/tests/test_observability_hardening.py::test_telemetry_database_failure_isolation`
- **Result:** PASSED. When a session raises `RuntimeError("Database connection timeout during telemetry persist")`, the exception is swallowed cleanly, warning logged, rollback invoked, and the inference workflow completes uninterrupted.

---

## 3. Client Cancellation and Disconnect Handling

### Implementation in `backend/app/assistant_runtime/runtime.py`:
Both `stream_response` (persistent conversations) and `stream_preview` (simulator) catch `GeneratorExit`:
```python
except GeneratorExit:
    quota_svc.release_reservation(reservation_id)
    logger.info(f"Stream connection closed by client for trace {trace.trace_id}")
    gen_span.finish(status="CANCELLED", error="Client connection aborted")
    trace.finish(status="CANCELLED", error="Client connection aborted")
    try:
        await tracer.persist_to_database(trace)
    except Exception:
        pass
    raise
```

### Guarantees:
- **Quota Protection:** In-flight token reservations are immediately released via `quota_svc.release_reservation()`.
- **Accurate Classification:** Categorized as `ErrorCategory.CANCELLED_STREAM` rather than an internal platform fault.
- **Trace Durability:** The trace is marked as `CANCELLED` with actual tokens generated up to disconnect, and saved to PostgreSQL.

---

## 4. Idempotent Upsert Durability

### Defect Addressed:
If a finalizer or retry mechanism triggered persistence more than once for a single request, naive `session.add(record)` would raise an `IntegrityError` due to the unique index on `trace_id`.

### Resolution:
`persist_to_database` executes an idempotent select-then-upsert check. If the trace already exists, it updates all mutable fields (`status`, `error_category`, `error_message`, `output_tokens`, `total_tokens`, `total_duration_ms`, `spans_data`, `output_preview`, `completed_at`).

### Validation Evidence:
- **Test:** `backend/tests/test_observability_hardening.py::test_idempotent_trace_upsert`
- **Result:** PASSED. Persisting a trace in `RUNNING` state followed by `COMPLETED` state updates the single record in-place without duplicate rows or database collisions.
