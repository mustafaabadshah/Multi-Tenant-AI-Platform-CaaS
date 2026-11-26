# M20.5 — Observability 2.0 Validation Report

| Probe | Target Endpoint | Key Checks | Live Staging Evidence | Status |
|---|---|---|---|---|
| **OBS-01** | Traces Listing | `GET /api/v1/observability/traces` | Persisted traces with latency and status | `id=tr_cc941cf38f934c10`, `status=COMPLETED`, `tokens=338` | **PASS** |
| **OBS-02** | Cost Accounting | `GET /api/v1/observability/traces` | Provider attribution & zero cost for mock | `cost=0.0`, `pricing_status=zero_cost` | **PASS** |
| **OBS-03** | Trace Detail | `GET /api/v1/observability/traces/{id}` | Span breakdown & metadata privacy | `has_preview=False`, raw prompts/keys omitted | **PASS** |
| **OBS-04** | Aggregate Metrics | `GET /api/v1/observability/metrics?period=all` | Request count, latency p50/p95, error rate | `error_rate=0.0`, `p50=1019.63ms`, `p95=1019.63ms` | **PASS** |
| **OBS-05** | Observability Dashboard UI | `https://mmaip-frontend.onrender.com/dashboard/observability` | Next.js route loads with HTTP 200 | `status=200 OK`, full visual console rendered | **PASS** |

---

## 1. Trace Telemetry Evidence

Live query returned:
```json
{
  "trace_id": "tr_cc941cf38f934c10",
  "status": "COMPLETED",
  "total_tokens": 338,
  "estimated_cost_usd": 0.0,
  "pricing_status": "zero_cost"
}
```

## 2. Privacy & Redaction Standard

- By default, traces operate in `METADATA_ONLY` mode.
- Plaintext passwords, bearer tokens, and external MCP credentials are never recorded in trace spans or audit tables.
