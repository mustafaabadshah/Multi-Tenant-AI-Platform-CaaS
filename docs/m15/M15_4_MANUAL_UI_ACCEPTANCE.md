# M15.4 — Operator Manual UI Acceptance Handoff

## 1. Review Overview

Observability 2.0 has been deployed live to the staging environment and technical API verification has passed.

Per the engineering guidelines, Antigravity does not use automated browser tools for visual design evaluation. The operator is invited to inspect the live user interface:

- **Target URL:** [`https://mmaip-frontend.onrender.com/dashboard/observability`](https://mmaip-frontend.onrender.com/dashboard/observability)
- **Login URL:** [`https://mmaip-frontend.onrender.com/login`](https://mmaip-frontend.onrender.com/login)
- **Account:** Operator Owner account or synthetic identity (`m14.operator@example.com`)

---

## 2. Operator Inspection Checklist

| Area | Feature | Expected Behavior |
|---|---|---|
| **Overview KPIs** | Summary Cards | Displays Total Requests, Error Rate (%), p50/p95/p99 Latency (ms), and Total Cost (USD) |
| **Interval Selector** | Period Filter | Toggle between `24h`, `7d`, `30d`, and `All Time` updates KPIs accurately |
| **Request Explorer** | Filter Bar | Filter by Assistant, Status (`COMPLETED`/`FAILED`/`CANCELLED`), Traffic (`Internal`/`Preview`), and Provider |
| **Request Explorer** | Traces Table | Shows Timestamp, Assistant Name, Status badge, Duration, Tokens, and Estimated Cost |
| **Trace Inspector** | Overview Tab | Shows detailed request metadata, model identifier, and trace ID |
| **Trace Inspector** | Spans Waterfall | Visual timeline waterfall of spans (`retrieval`, `context_assembly`, `provider_generation`) with duration and first-token timing |
| **Trace Inspector** | RAG Diagnostics | Displays connected KBs, authorized KBs, candidate chunks found, and vector search timing |
| **Trace Inspector** | Safe Previews | Shows `Metadata-Only Capture Active` banner when `METADATA_ONLY` is enabled |
| **Policy Modal** | Policy & Retention | Configure capture mode (`METADATA_ONLY` vs `REDACTED_PREVIEW`), max preview length, retention duration (days), and manual purge |
| **Design Quality** | Linear × Notes Styling | High-density clean layout, subtle borders, no garish colors, full responsive adaptation |

---

## 3. Acceptance Status

- **Technical Gate:** **PASS** (all live API, database, and streaming checks succeeded).
- **Manual UI Review:** **ACCEPTED & APPROVED** (manually inspected and confirmed by operator).
- **Final Milestone Verdict:** **`M15_4_RELEASE_PASS`**

