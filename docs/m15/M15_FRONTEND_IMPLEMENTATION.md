# M15 Frontend Implementation Report — Observability 2.0 Workspace

| Field | Value |
|---|---|
| Milestone | M15 — Observability 2.0, AI Request Intelligence & Platform Reliability |
| UI Framework | Next.js 16 (App Router), React 19, TypeScript 5, Tailwind CSS 4 |
| Design Archetype | Linear × Apple Notes / restrained Woice-inspired interface |
| Route | `/dashboard/observability` |

---

## 1. Overview of Frontend Upgrades

The observability workspace in `frontend/app/dashboard/observability/page.tsx` has been upgraded to a professional operations console for inspecting AI inferences, latencies, retrieval stages, and policy controls:

### 1.1 Summary Telemetry Bar
- **Requests Count:** Total queries recorded within the active interval.
- **Error Rate:** Real percentage of failed or cancelled requests with failure counts.
- **Latency Percentiles:** Displays `p50`, `p95`, and `p99` latency in milliseconds, revealing tail latency spikes.
- **Average TTFT:** Time to first token across streaming responses.
- **Token Accounting:** Prompt + completion tokens.
- **Estimated Cost:** Estimated USD spend calculated from published provider rates.

### 1.2 Time Window & Filtering Bar
- **Period Selector:** Fast toggles for `24 Hours`, `7 Days`, `30 Days`, and `All Time`.
- **Search Bar:** Real-time search across trace IDs, assistant names, models, and error categories.
- **Status Filter:** Filter by `COMPLETED`, `RUNNING`, `FAILED`, or `CANCELLED`.
- **Channel Filter:** Filter by `internal`, `developer`, `public`, `embed`, or `preview`.

### 1.3 Request Detail Inspector
A structured modal inspector featuring five dedicated tabs:
1. **Overview & Metrics:** Quick view of model, provider, channel, duration, TTFT, token breakdown, and cost.
2. **Execution Spans:** Visual execution waterfall displaying each phase (`retrieval`, `context_assembly`, `provider_generation`), latency, status, and custom span attributes.
3. **RAG Retrieval:** Deep dive into knowledge retrieval mode, candidate knowledge bases, authorized chunks, vector store, and exact stage latencies (FTS vs. vector vs. fusion vs. security filter).
4. **Input / Output Previews:** Privacy-safe view of user message and assistant output snippets. If previews are disabled, displays an explanatory privacy banner explaining the metadata-only policy.
5. **Error Diagnosis:** When a request fails, presents the standardized error category badge (`QUOTA_EXCEEDED`, `AUTH_ERROR`, `RATE_LIMITED`, `CANCELLED_STREAM`, etc.), sanitized message, and remediation guidance.

### 1.4 Workspace Policy & Retention Modal
- Allows workspace administrators to switch between `Metadata Only` (default) and `Redacted Preview` mode.
- Configurable preview length (50–500 characters).
- Configurable retention duration (7, 14, 30, 60, 90 days).
- Manual retention purge trigger with confirmation modal and feedback toast.

---

## 2. API Client Integration (`frontend/lib/api.ts`)

The typed API client was updated with:
- `AssistantTraceItem`: extended with `error_category`, `is_token_estimated`, `estimated_cost_usd`, `pricing_status`, `retrieval_metadata`, `input_preview`, `output_preview`, `has_preview`.
- `ObservabilityMetrics`: extended with `p50_latency_ms`, `p99_latency_ms`, `estimated_cost_usd`, `by_error_category`.
- `ObservabilityPolicy`: interface for tenant capture configuration.
- Methods: `listTraces()`, `getTraceDetail()`, `getObservabilityMetrics()`, `getObservabilityPolicy()`, `updateObservabilityPolicy()`, `purgeExpiredTraces()`.
