# M15 Data Model & Retention Specification

| Field | Value |
|---|---|
| Milestone | M15 — Observability 2.0, AI Request Intelligence & Platform Reliability |
| Document | Data Model, Indexing Strategy, and Storage Retention Policy |
| Target DB | PostgreSQL 16 (Neon Free compatible) & SQLite (Local testing) |

---

## 1. Relational Schema (`request_traces`)

The primary persistence entity for AI telemetry is `request_traces`.

### 1.1 Column Definitions

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | UUID | No | UUIDv4 | Primary key. |
| `trace_id` | VARCHAR(36) | No | — | External trace correlation ID (e.g. `tr_9f81a7b...`), unique index. |
| `tenant_id` | UUID | No | — | Tenant foreign key (`tenants.id`, ON DELETE CASCADE), indexed. |
| `assistant_id` | UUID | Yes | NULL | Assistant foreign key (`assistants.id`, ON DELETE SET NULL), indexed. |
| `assistant_name` | VARCHAR(100) | No | 'Assistant' | Snapshot assistant display name. |
| `conversation_id` | UUID | Yes | NULL | Associated conversation ID if authenticated, indexed. |
| `traffic_type` | VARCHAR(50) | No | 'internal' | Traffic channel (`internal`, `developer`, `public`, `embed`), indexed. |
| `status` | VARCHAR(20) | No | 'RUNNING' | Execution status (`RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`), indexed. |
| `error_category` | VARCHAR(50) | Yes | NULL | Standard error category code, indexed. |
| `error_message` | TEXT | Yes | NULL | Sanitized, non-sensitive failure summary. |
| `provider` | VARCHAR(50) | Yes | NULL | AI provider name (`mock`, `omniroute`, `openai`, `anthropic`, etc.), indexed. |
| `model` | VARCHAR(100) | Yes | NULL | Model identifier (`mock-chat-v1`, `gpt-4o-mini`, `claude-3-5-sonnet`, etc.). |
| `credential_source` | VARCHAR(50) | No | 'byok' | Credential source (`byok`, `system`, `mock`). |
| `retrieval_mode` | VARCHAR(50) | Yes | NULL | Active retrieval mode (`hybrid`, `semantic`, `lexical`). |
| `retrieved_chunk_count`| INTEGER | No | 0 | Chunks authorized and supplied to prompt context. |
| `citation_count` | INTEGER | No | 0 | Provenance citations emitted in response. |
| `input_tokens` | INTEGER | No | 0 | Prompt token count. |
| `output_tokens` | INTEGER | No | 0 | Completion token count. |
| `total_tokens` | INTEGER | No | 0 | Combined tokens. |
| `is_token_estimated` | BOOLEAN | No | TRUE | True if tokens were estimated via heuristic. |
| `estimated_cost_usd` | DOUBLE PRECISION| Yes | NULL | Estimated provider cost in USD (null if unknown). |
| `pricing_status` | VARCHAR(20) | No | 'unknown' | Pricing status (`known`, `unknown`, `zero_cost`). |
| `total_duration_ms` | DOUBLE PRECISION| Yes | NULL | End-to-end execution duration in milliseconds. |
| `ttft_ms` | DOUBLE PRECISION| Yes | NULL | Time to first token in milliseconds. |
| `spans_data` | JSON | No | '[]' | Serialized lifecycle execution spans with timing and attributes. |
| `retrieval_metadata` | JSON | Yes | NULL | Retrieval diagnostics (vector/FTS/fusion latencies, candidates, KBs). |
| `input_preview` | TEXT | Yes | NULL | Sanitized prompt preview (null if policy is METADATA_ONLY). |
| `output_preview` | TEXT | Yes | NULL | Sanitized completion preview (null if policy is METADATA_ONLY). |
| `has_preview` | BOOLEAN | No | FALSE | Indicates whether redacted previews are available. |
| `created_at` | TIMESTAMPTZ | No | NOW() | Request initiation timestamp, indexed. |
| `completed_at` | TIMESTAMPTZ | Yes | NULL | Request completion or termination timestamp. |

### 1.2 Indexes

- `ix_request_traces_tenant_id` on `(tenant_id)`
- `ix_request_traces_tenant_created` on `(tenant_id, created_at DESC)` (for pagination)
- `ix_request_traces_tenant_status` on `(tenant_id, status)`
- `ix_request_traces_tenant_assistant` on `(tenant_id, assistant_id)`
- `ix_request_traces_tenant_traffic` on `(tenant_id, traffic_type)`
- `uq_request_traces_trace_id` UNIQUE on `(trace_id)`

---

## 2. Workspace Policy Entity (`observability_policies`)

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `tenant_id` | UUID | No | — | Primary Key & Foreign Key (`tenants.id`, ON DELETE CASCADE). |
| `capture_mode` | VARCHAR(20) | No | 'METADATA_ONLY' | `METADATA_ONLY` or `REDACTED_PREVIEW`. |
| `max_preview_length` | INTEGER | No | 250 | Maximum characters per preview snippet. |
| `retention_days` | INTEGER | No | 30 | Telemetry data retention period in days. |
| `created_at` | TIMESTAMPTZ | No | NOW() | Record creation. |
| `updated_at` | TIMESTAMPTZ | No | NOW() | Last policy update. |

---

## 3. Retention & Storage Budget for Neon Free

Neon Free provides up to 0.5 GiB of storage.
- Average raw `request_traces` row (with 4 spans in JSON and metadata): ~1.2 KB.
- 1,000 requests = ~1.2 MB.
- 10,000 requests = ~12 MB (< 2.5% of Neon Free quota).
- **Default Retention Policy:** 30 days. Traces older than `retention_days` can be purged safely without affecting conversation history or document chunks.
- **Purge Endpoint:** `POST /api/v1/observability/purge` executes tenant-scoped deletion:
  `DELETE FROM request_traces WHERE tenant_id = :tenant_id AND created_at < NOW() - INTERVAL '30 days'`
