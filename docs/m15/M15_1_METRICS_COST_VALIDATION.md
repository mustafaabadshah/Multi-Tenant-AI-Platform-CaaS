# M15.1 — Metrics, Token Accounting & Cost Estimation Validation

## 1. Token Accounting & Pricing Engine

### Pricing Catalog (`backend/app/observability/pricing.py`):
The engine maintains a catalog with effective dates, input token rates, and output token rates per 1,000,000 tokens:
- **Mock Provider:** Rate is $0.00 / 1M tokens. Returns `pricing_status="zero_cost"`, cost `$0.00`.
- **Known Models:**
  - `openai/gpt-4o-mini`: $0.15 in / $0.60 out per 1M.
  - `openai/gpt-4o`: $2.50 in / $10.00 out per 1M.
  - `anthropic/claude-3-5-sonnet`: $3.00 in / $15.00 out per 1M.
  - `anthropic/claude-3-5-haiku`: $0.80 in / $4.00 out per 1M.
  - `gemini/gemini-1.5-flash`: $0.075 in / $0.30 out per 1M.
  - `gemini/gemini-1.5-pro`: $1.25 in / $5.00 out per 1M.
  - `groq/llama-3.1-70b-versatile`: $0.59 in / $0.79 out per 1M.
  Returns `pricing_status="known"` and estimated cost in USD.
- **Unknown Models:** Returns `pricing_status="unknown"` and `estimated_cost_usd=None`.

### Governance & Truth in Billing:
- **BYOK Disclaimer:** Estimated cost reflects approximate upstream vendor API billing based on public rate cards. It is **never represented as platform billing, fee, or invoice**.
- **Qualification:** The UI and API explicitly tag costs as `ESTIMATED` with `pricing_status`. If pricing is unknown, the UI displays `Unknown`, never misleading `$0.00`.

---

## 2. Latency Percentiles Validation

### Percentile Formula Verification:
Using nearest-rank interpolation over ordered completed latencies:
$$\text{index} = \lceil P \times N \rceil - 1$$

Tested in `backend/tests/test_observability_hardening.py::test_percentile_latency_calculation_precision`:
- Evaluated against a synthetic sequential dataset of 100 duration samples ($1\text{ms}, 2\text{ms}, \dots, 100\text{ms}$).
- Verified exact results: $\text{p50} = 50\text{ms}$, $\text{p95} = 95\text{ms}$, $\text{p99} = 99\text{ms}$.

---

## 3. Retrieval & Citation Observability

In `runtime.py`, the retrieval span captures actual execution metrics from `RetrievalService.search()`:
- `vector_search_latency_ms`: Duration of pgvector cosine similarity lookup.
- `fusion_latency_ms`: Reciprocal Rank Fusion calculation duration.
- `candidate_chunks_found`: Initial search candidates returned.
- `authorized_kb_count`: Security-filtered active knowledge bases.
- `citation_count`: Number of distinct citations synthesized into context.

### Semantic Boundary:
Transport-level citation provenance (chunk ID matching) is recorded accurately. The UI and documentation explicitly distinguish chunk citation tracking from semantic factual correctness.

---

## 4. Neon Free Tier Capacity Planning

### Official Quota Update:
Neon officially updated its Free Tier capacity to **1 GB per project** (October 2026).

### Storage Sizing Model:
- Base PostgreSQL Row: ~300 bytes
- JSONB Spans Data (2–4 spans per trace): ~400–600 bytes
- Retrieval Metadata: ~150 bytes
- Bounded Preview (if REDACTED_PREVIEW enabled, $\le 250$ chars): ~250 bytes
- B-Tree Indexes (4 composite + 1 unique): ~300 bytes per entry
- **Total Storage per Trace:** $\approx 1.2\text{ KB}$

### Capacity Analysis:
| Request Volume | Storage Required | % of 1 GB Neon Free Tier |
|---|---|---|
| **1,000 traces** | 1.2 MB | 0.12% |
| **10,000 traces** | 12 MB | 1.20% |
| **50,000 traces** | 60 MB | 6.00% |
| **100,000 traces** | 120 MB | 12.00% |

With the default 30-day retention policy and periodic purges, telemetry storage will comfortably remain under **15% of the total 1 GB Neon Free tier budget**.
