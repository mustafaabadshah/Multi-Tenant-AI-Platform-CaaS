# M28.10.1 — Research Answer Quality & Tool Validation

## 1. Research Quality Constraints

In scientific domains such as solar irradiance forecasting and machine learning architectures, responses must adhere to strict epistemological and causal principles:

1. **Temporal Causality & Data Leakage:**
   - Future data points must not leak into historical inputs (e.g. cloud cover, satellite observations, ambient temperature).
   - The runtime system prompt explicitly instructs assistants to enforce causal lag windows and proper train/test chronological splitting.
2. **Metric Integrity & Fair Comparison:**
   - Cross-dataset metric comparisons (e.g. comparing RMSE on Pakistan agricultural datasets directly against European desert datasets without normalizing for mean irradiance or capacity) are flagged as invalid.
   - Assistants are required to evaluate normalized metrics (nRMSE, MAE, skill scores against persistence baselines).
3. **Preprint vs Published Distinction:**
   - arXiv documents are identified as non-peer-reviewed preprints, avoiding unwarranted claims of formal peer validation.

---

## 2. Web Tools & Execution Matrix

| Scenario | Invoked Tool | Provider Used | Expected Outcome |
|---|---|---|---|
| A. Direct URL reading | `web_read_url` | `WebFetchService` (SSRF-protected) | Clean text extracted, dynamic citation added |
| B. Academic literature search | `web_search` | `ArxivSearchProvider` | Atom XML parsed, preprint cited |
| C. General web search (No Brave key) | `web_search` | `WebSearchService` | Honest `NOT_CONFIGURED` response |
| D. General web search (With Brave key) | `web_search` | `BraveSearchProvider` | Web results with domain & snippet |
| E. Search succeeds, LLM generation fails | `web_search` | Provider succeeds | Quota released, zero citations saved, error emitted |
| F. Comparison of PDF vs Literature | RAG + `web_search` | Hybrid RAG + Arxiv | Distinguishes internal PDF from external arXiv |

---

## 3. Observability & Trace Integrity

1. **Structured Traces:**
   - Every request records:
     - `retrieval_candidates_count`
     - `context_chunks_count`
     - `citation_count` (verified only)
     - `tokens_used`
     - `execution_status` (`COMPLETED`, `FAILED`, `CANCELLED`)
2. **Zero Citations on Failure:**
   - Verified across tests: if generation fails or stream drops, `trace.citation_count` is set to `0` and persisted.
