# M15 Initial Audit — Observability Architecture, Telemetry Gaps & Security Baseline

| Field | Value |
|---|---|
| Milestone | M15 — Observability 2.0, AI Request Intelligence & Platform Reliability |
| Audit Date | 2026-11-14 |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Baseline Commit | `37d69e4261c93ea67abb23e914bee2c640d2e17d` |
| Live Deployed SHA | `e4926014471f00695b2de3c046fe529f867955b0` |
| Scope | Telemetry pipeline, trace persistence, retrieval instrumentation, security, and Neon Free limits |

---

## 1. Executive Summary

This architecture audit evaluates the state of observability, tracing, and telemetry across the Multi-Tenant AI Platform (CaaS) as of Milestone M14.7. While M09 established the initial abstractions (`AssistantTrace`, `Span`, `ObservabilityTracer`), the implementation relies on process-memory ring buffers and disk-based JSON serialization. On cloud hosting (Render Free) and serverless databases (Neon Free), this structure suffers from ephemeral data loss on container restarts, multi-process isolation gaps, and lack of database indexing.

This document identifies the exact data collection, persistence, security, and retrieval gaps in the codebase and provides the foundation for the M15 Observability 2.0 upgrade.

---

## 2. Telemetry Pipeline & Data Collection Audit

### 2.1 Trace Lifecycle & Triggers

| Lifecycle Event | Location in Code | Current Behavior | Gap / Risk |
|---|---|---|---|
| **Trace Start** | `backend/app/assistant_runtime/runtime.py:97` | `tracer.start_trace()` is called at the start of authenticated `stream_chat`. | **Omission:** `stream_preview` (lines 435–570) does not initialize an `AssistantTrace`, leaving test previews uninstrumented. |
| **Trace Completion** | `backend/app/assistant_runtime/runtime.py:397` | `trace.finish(status="COMPLETED")` is called after successful SSE generation. | Success path is correctly recorded. |
| **Quota Rejection** | `backend/app/assistant_runtime/runtime.py:253` | `trace.finish(status="FAILED", error=err_msg)` | Quota failure is recorded, but no structured error category is assigned. |
| **BYOK Missing** | `backend/app/assistant_runtime/runtime.py:275` | `trace.finish(status="FAILED", error=err_msg)` | Handled as generic error string. |
| **LLM Provider Exception** | `backend/app/assistant_runtime/runtime.py:318` | `trace.finish(status="FAILED", error=safe_err)` | Handled with `sanitize_error_message(str(e))`. |
| **Client Abort / Disconnect** | `backend/app/assistant_runtime/runtime.py` (SSE generator) | **Unhandled.** If a client cancels the stream mid-flight, a `GeneratorExit` exception occurs. `trace.finish()` is **never reached**. | **Critical bug:** Aborted or cancelled requests remain permanently in `RUNNING` status in memory. |

### 2.2 Timings, Metrics, and Token Accuracy

1. **Time To First Token (TTFT):**
   - In `runtime.py:309`, `trace.mark_first_token()` records `(time.perf_counter() - self.start_time) * 1000`.
   - *Assessment:* This measures true end-to-end TTFT (including authorization, conversation history loading, retrieval, and provider time to first chunk).
2. **Token Accounting:**
   - In `runtime.py:378-396`, tokens are estimated via whitespace splitting:
     `input_token_estimate = sum(len(m.content.split()) for m in messages)`
     `output_token_estimate = len(final_content.split())`
   - *Assessment:* While acceptable as an approximation for mock models, true token accounting from LLM provider response objects is not stored on `AssistantTrace`. The `is_estimated` flag is missing from `AssistantTrace`.
3. **Provider Retries:**
   - Providers do not currently emit retry attempts into telemetry; exceptions fail immediately.

---

## 3. Storage & Persistence Audit

### 3.1 Ephemeral JSON Persistence (`backend/app/observability/tracer.py`)

The existing tracer maintains:
```python
self._tenant_traces: dict[str, deque[AssistantTrace]] = {}
self._trace_lookup: dict[str, AssistantTrace] = {}
```
On every trace finish, it invokes `save_state()`, which serializes up to 1,000 traces to `backend/data/observability_traces.json`.

### 3.2 Cloud & Production Constraints (Render Free + Neon Free)

1. **Ephemeral File System:** Render Free instances discard disk state on deployment, idle shutdown, or process restarts. All local JSON traces are lost.
2. **Multi-Worker Process Isolation:** If Uvicorn runs multiple worker processes, memory buffers are not shared, resulting in inconsistent trace lists and race conditions on `observability_traces.json`.
3. **Disk Serialization Overhead:** Serializing 1,000 JSON traces synchronously on every request completion blocks event-loop throughput.
4. **Lack of Indexing & Pagination:** In-memory traversal with `deque` does not support indexed SQL filtering across dates, error categories, or models.

**Verdict:** Ephemeral disk/memory storage is inadequate for multi-tenant cloud operations. A lightweight, indexed PostgreSQL table (`request_traces`) is required.

---

## 4. Security & Privacy Audit

### 4.1 Access Control & Isolation

1. **Authorization Guard:**
   - `backend/app/api/v1/observability.py` guards all endpoints with:
     `tenant_ctx: TenantContext = Depends(require_permission(PermissionName.USAGE_READ))`
   - In `backend/app/core/constants.py`, `USAGE_READ` is granted exclusively to `TENANT_OWNER`, `ORG_ADMIN`, and `PLATFORM_SUPERADMIN`.
2. **Tenant Scoping:**
   - Queries enforce `trace.tenant_id == str(tenant_ctx.tenant.id)`, returning `404` for cross-tenant lookups.

### 4.2 Raw Content Exposure vs. Privacy

1. **Current State:** `AssistantTrace` does not store user prompts or assistant responses, which prevents secret exposure but hinders operational debugging.
2. **Requirements for M15:**
   - Default mode must remain **Metadata Only** (no prompts or completions stored).
   - Opt-in **Redacted Preview Mode** must enforce:
     - Configurable max preview length (default 250 characters).
     - Multi-pattern secret redaction (API keys, JWT tokens, Bearer tokens, passwords, private keys).
     - Role-restricted access (restricted to tenant owners / org admins).
     - HTML/Markdown sanitization to prevent prompt injection or XSS.

---

## 5. Retrieval & RAG Observability Audit

In `backend/app/retrieval/service.py:206-228`, `RetrievalService.search()` computes rich execution telemetry:
- `timing_ms`: Lexical latency, embedding latency, vector search latency, fusion latency, security filter latency.
- `fusion`: Reciprocal Rank Fusion (RRF) metrics and candidate rankings.
- `candidates_found` vs. `authorized_count`.
- `fallback_to_lexical` flag and embedding error details.

**Current Failure:** In `runtime.py:212-215`, only `candidate_kbs` count and `results_count` are stored as span attributes. The detailed search diagnostics and latency breakdown are discarded!

**M15 Requirement:** Capture these existing diagnostics directly into the retrieval span and trace metadata.

---

## 6. Audit Action Matrix

| Area | Current Defect / Gap | M15 Required Action |
|---|---|---|
| **Persistence** | Ephemeral memory + JSON disk storage | Add durable PostgreSQL table `request_traces` with indexes and retention policy. |
| **Aborted Streams** | Client disconnect leaves traces in `RUNNING` | Wrap streaming in generator `try/finally` to catch `GeneratorExit` and mark `CANCELLED`. |
| **Error Intelligence** | Unstructured error strings | Introduce standardized `ErrorCategory` enum and sanitized error summaries. |
| **I/O Observability** | Zero request/response visibility | Implement configurable `ObservabilityPolicy` with metadata-only default and redacted previews. |
| **RAG Observability** | Rich `SearchResponse.diagnostics` discarded | Persist search diagnostics (lexical, vector, fusion latencies, candidate counts) in trace. |
| **Cost Accounting** | No pricing definitions | Implement transparent cost estimator with known provider rates, mock zero-cost, and "unknown" state. |
| **Frontend** | In-memory 100-trace table with client search | Upgrade to server-side filtering, pagination, timeline waterfall, and inspector drawer. |
