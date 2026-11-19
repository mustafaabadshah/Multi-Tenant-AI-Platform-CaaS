# M28.10 — Observability & Trace Accounting

## 1. Accurate Stage Metric Separation
In M28.10, the Observability tracer explicitly distinguishes:
- `retrieved_chunk_count`: Candidates returned by vector search / hybrid search.
- `citation_count`: Verified sources explicitly referenced in `final_content`.
- On failed generations (e.g. provider exceptions), `trace.citation_count` is recorded as `0`. Failed traces no longer report precomputed citations as if evidence had been validated.

---

## 2. Token Accounting on Failure
When an inference stream encounters a provider exception or is interrupted:
- `trace.finish(status="FAILED", error=safe_diag_err)` records the sanitized diagnostic error.
- Quota reservation is released immediately, and tokens billed is zero.
- No phantom tokens are attributed to the user turn.

---

## 3. Secret Redaction Standard
The diagnostic sanitizer (`sanitize_error_message`):
- Redacts OpenAI/OmniRoute style API keys (`sk-...` -> `[REDACTED_API_KEY]`).
- Redacts Bearer tokens (`Bearer ...` -> `Bearer [REDACTED_TOKEN]`).
- Redacts database secrets and password keywords.
- Keeps low-cardinality telemetry metrics compatible with Render Free log bounds.
