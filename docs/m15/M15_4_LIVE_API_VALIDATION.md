# M15.4 — Live Staging API & Observability Validation Report

## 1. Test Methodology

All live integration checks were executed against the actual deployed staging infrastructure:
- **Backend:** `https://mmaip-backend.onrender.com`
- **Database:** Neon PostgreSQL 16 (`mmaip_staging`)
- **Identity:** Synthetic operator account (`m14.operator@example.com`)
- **Provider:** Zero-cost Mock provider (`mock/mock-chat-v1`)

---

## 2. Authenticated End-to-End Journey Verification

### Step 1: Authentication & Token Acquisition
- **Endpoint:** `POST https://mmaip-backend.onrender.com/api/v1/auth/login`
- **Response:** `HTTP 200 OK`
- **Verification:** Access token issued and decoded with active tenant context.

### Step 2: Policy & Pre-Chat Baseline
- **Endpoint:** `GET https://mmaip-backend.onrender.com/api/v1/observability/policy`
- **Response:** `HTTP 200 OK`
- **Payload Verified:**
  ```json
  {
    "capture_mode": "METADATA_ONLY",
    "max_preview_length": 250,
    "retention_days": 30
  }
  ```
- **Initial Traces Count:** `0`
- **Initial Metrics:** `total_requests: 0`, `error_rate: 0.0`

### Step 3: Conversation Creation
- **Endpoint:** `POST https://mmaip-backend.onrender.com/api/v1/conversations`
- **Assistant Used:** `M14 Mock Assistant` (ID: `4d2f9f38-6e04-4cfe-b592-52079ed182b0`)
- **Conversation Created:** ID `7647ffb0-603e-49f1-8efb-04b96b003583`

### Step 4: Live Server-Sent Events (SSE) Streaming
- **Endpoint:** `POST https://mmaip-backend.onrender.com/api/v1/conversations/7647ffb0-603e-49f1-8efb-04b96b003583/messages/stream`
- **Payload:** `{"content": "Hello from M15.3 release verification test!"}`
- **SSE Events Received:** 33 events
  - `event: message_start`
  - `event: retrieval_start`
  - `event: retrieval_complete`
  - 28 individual streaming `event: token` deltas
  - `event: usage`
  - `event: message_complete`

### Step 5: Post-Generation Persistent Trace Inspection
- **Endpoint:** `GET https://mmaip-backend.onrender.com/api/v1/observability/traces`
- **Response:** `HTTP 200 OK`
- **Traces Count:** `1`
- **Latest Trace Record:**
  - `trace_id`: `tr_fa8349df047b4cd1`
  - `status`: `COMPLETED`
  - `total_tokens`: 338
  - `estimated_cost_usd`: 0.0
  - `pricing_status`: `zero_cost`
  - `duration_ms`: 1019.63 ms

### Step 6: Trace Detail & Privacy Verification
- **Endpoint:** `GET https://mmaip-backend.onrender.com/api/v1/observability/traces/tr_fa8349df047b4cd1`
- **Response:** `HTTP 200 OK`
- **Privacy Policy Compliance:**
  - `has_preview`: `false`
  - `input_preview`: `null`
  - `output_preview`: `null`
- **Finding:** Under `METADATA_ONLY`, zero raw prompt or response text was written to PostgreSQL, completely adhering to the zero-trust privacy requirement.

### Step 7: Aggregated Metrics Verification
- **Endpoint:** `GET https://mmaip-backend.onrender.com/api/v1/observability/metrics?period=all`
- **Response:** `HTTP 200 OK`
- **Metrics Observed:**
  - `total_requests`: 1
  - `error_rate`: 0.0
  - `p50_latency_ms`: 1019.63
  - `p95_latency_ms`: 1019.63
  - `p99_latency_ms`: 1019.63
  - `by_status`: `{"COMPLETED": 1}`
  - `by_traffic_type`: `{"internal": 1}`
  - `by_provider`: `{"mock": 1}`
