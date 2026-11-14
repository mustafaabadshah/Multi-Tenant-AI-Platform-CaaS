# M15 Backend Implementation Report — Observability 2.0 & Request Intelligence

| Field | Value |
|---|---|
| Milestone | M15 — Observability 2.0, AI Request Intelligence & Platform Reliability |
| Implementation Status | **COMPLETE** |
| Target Framework | FastAPI, SQLAlchemy 2.0 Async, Pydantic v2, Alembic |
| Database Target | PostgreSQL 16 (Neon Free) / SQLite (Local testing) |

---

## 1. Overview of Backend Components

M15 replaces the legacy in-memory and ephemeral disk JSON tracer with an enterprise-grade, privacy-first observability architecture:

1. **Durable Persistence (`backend/app/models/trace.py`):**
   - Introduced `RequestTrace` table inheriting `Base`, `UUIDPrimaryKeyMixin`, `TenantScopedMixin`.
   - Stores request IDs, tenant correlation, execution spans, retrieval diagnostics, token metrics, pricing, and error categories.
   - Introduced `ObservabilityPolicy` table for workspace-level capture mode (`METADATA_ONLY` vs. `REDACTED_PREVIEW`), preview length, and data retention duration.
2. **Deterministic Pricing Engine (`backend/app/observability/pricing.py`):**
   - Published rate table for OpenAI, Anthropic, Gemini, Groq, and Mock models.
   - Computes estimated cost without making external billing API calls.
   - Accurately tags costs as `zero_cost`, `known`, or `unknown`.
3. **Error Taxonomy & Redaction (`backend/app/observability/policy.py`):**
   - Standardized `ErrorCategory` taxonomy: `AUTH_ERROR`, `QUOTA_EXCEEDED`, `RATE_LIMITED`, `PROVIDER_UNAVAILABLE`, `PROVIDER_TIMEOUT`, `INVALID_CONFIG`, `CONTEXT_OVERFLOW`, `RETRIEVAL_ERROR`, `CANCELLED_STREAM`, `EMPTY_RESPONSE`, `INTERNAL_ERROR`.
   - Multi-pass secret scrub (`sk-`, `mmaip_`, JWTs, Bearers, passwords, private keys).
   - XSS protection: strips `<script>` tags and escapes HTML.
4. **Durable Collector & Percentiles (`backend/app/observability/tracer.py`):**
   - Non-blocking `persist_to_database()` method with automatic fallback to in-memory buffers.
   - Computes `p50`, `p95`, `p99` latency, average TTFT, error rate, token totals, and estimated cost sums.
5. **Runtime Lifecycle & Abort Instrumentation (`backend/app/assistant_runtime/runtime.py`):**
   - Catches `GeneratorExit` on client disconnection/abort and finalizes the trace as `CANCELLED`.
   - Ingests full `SearchResponse.diagnostics` (FTS, vector, fusion, security filter latencies, candidate counts) into the retrieval span and trace metadata.
   - Sets safe previews according to workspace policy.
6. **Alembic Schema Chain (`backend/alembic/versions/0011_m15_durable_request_traces.py`):**
   - Forward-compatible migration from revision `0010` to `0011`.
   - Adds indexed tables `request_traces` and `observability_policies`.
7. **Observability API (`backend/app/api/v1/observability.py`):**
   - `GET /traces`: Filterable by assistant, status, channel, provider, search query, with pagination.
   - `GET /traces/{trace_id}`: Full detail with role-gated preview access (non-admins receive masked null previews).
   - `GET /metrics`: Aggregates over selectable periods (`24h`, `7d`, `30d`, `all`).
   - `GET /policy` & `PUT /policy`: View and update workspace capture policy.
   - `POST /purge`: Purges expired traces beyond the retention window.

---

## 2. API Endpoints Specification

| Method | Path | Required Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/observability/traces` | `usage.read` | List recent traces with filters (`assistant_id`, `status`, `traffic_type`, `provider`, `search`). |
| `GET` | `/api/v1/observability/traces/{trace_id}` | `usage.read` | Retrieve full lifecycle spans and diagnostics. Previews are masked for non-admins. |
| `GET` | `/api/v1/observability/metrics` | `usage.read` | Latency percentiles (p50, p95, p99), TTFT, error rate, tokens, cost estimate over selectable period. |
| `GET` | `/api/v1/observability/policy` | `usage.read` | Fetch workspace capture mode, preview length, and retention days. |
| `PUT` | `/api/v1/observability/policy` | `usage.read` (Admin/Owner) | Update workspace observability policy. |
| `POST` | `/api/v1/observability/purge` | `usage.read` (Admin/Owner) | Purge traces older than the configured retention policy. |
