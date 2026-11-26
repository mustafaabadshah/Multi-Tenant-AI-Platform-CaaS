# M28.10 — Streaming and Quota Recovery

## 1. Pipeline Lifecycle Overview
The end-to-end inference request lifecycle executes sequentially:
`Authorization → Retrieval → Context Assembly → Quota Reservation → Provider Call → Streaming → Tool Execution → Citation Verification → Message Persistence → Quota Reconciliation → Observability Finalization`.

---

## 2. Quota Lifecycle & Atomic Reconciliation
Prior to generation, `QuotaService.reserve_quota(estimated_tokens)` holds an atomic reservation against tenant quotas.
In M28.10, the lifecycle is hardened across all failure and partial-stream modes:
1. **Failure Before First Token**:
   - `except Exception as e`: Quota reservation is released immediately via `quota_svc.release_reservation_async(reservation_id)`.
   - Message is recorded with `token_count=0`.
   - Zero net token usage is charged to the tenant.
2. **Midstream Failure / Interruption**:
   - `except GeneratorExit` / client disconnection: Quota reservation is released.
   - Provider interruption raises typed `LLMStreamInterruptedError`, reservation released.
3. **Empty Generation**:
   - If stream finishes with 0 substantive tokens, reservation is released and tenant is not billed.
4. **Successful Generation**:
   - Atomic usage is recorded via `quota_svc.record_usage(...)` and reservation is committed/cleared.

---

## 3. Safe Failure Presentation
Raw technical exceptions like `KeyError: 'choices'` have been eradicated from user-visible surfaces.
In `backend/app/assistant_runtime/runtime.py`:
- `format_user_facing_error(e, sanitized_diag)` maps typed exceptions into actionable, nontechnical messages:
  - `LLMResponseInvalidError`: "Couldn't generate a response because the AI provider returned an invalid response. Please retry or check the configured model."
  - `LLMStreamInterruptedError`: "The response stream was interrupted by the AI provider. Please retry."
  - `LLMAuthenticationError`: "AI provider authentication failed. Please verify provider credentials or API key in settings."
  - `LLMRateLimitError`: "AI provider rate limit reached. Please wait a moment before retrying."
  - `LLMTimeoutError`: "The request to the AI provider timed out. Please retry."
  - `LLMConnectionError`: "Could not connect to the AI provider. Please verify network connectivity or gateway status."
  - `KeyError('choices')`: "Couldn't generate a response because the AI provider returned an invalid response format. Please retry or check the configured model."
- Technical stack traces and diagnostics remain accessible to authorized administrators via Observability traces and server logs, with all sensitive credentials and API keys redacted by `sanitize_error_message`.
