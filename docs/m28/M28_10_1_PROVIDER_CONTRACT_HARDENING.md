# M28.10.1 — Provider Contract Hardening & 20-Scenario Failure Suite

## Executive Summary

This audit verified and hardened the LLM provider contract boundaries across `OpenAICompatibleLLMProvider`, `GroqLLMProvider`, and `AssistantRuntime`. All 20 edge-case and failure scenarios were executed using deterministic mocks and schema-aware SSE parsers, confirming zero unhandled exceptions, zero raw `KeyError: 'choices'` leaks, and atomic quota/trace cleanup on failure.

---

## 20-Scenario Provider Matrix & Test Evidence

All 20 scenarios are implemented and verified in `backend/tests/test_m28_10_1_provider_contract.py` (20 passed):

| # | Scenario | Mechanism Tested | Expected Result | Verified Result |
|---|---|---|---|---|
| 1 | Normal Streaming | Multi-chunk SSE with `content_delta` | Accumulated full text without loss | PASS (`Hello world!`) |
| 2 | Normal Non-Streaming | Standard HTTP JSON payload | `LLMResponse` with correct tokens | PASS (`tokens_used: 15`) |
| 3 | Usage-Only SSE Event | OpenAI/vLLM trailing `{"usage": {...}}` frame | Parsed safely, no crash on missing `choices` | PASS (Chunk skipped safely) |
| 4 | Metadata-Only SSE Event | Heartbeat `: ping` & empty `choices: []` | Skipped gracefully without terminating stream | PASS (`Valid` emitted) |
| 5 | Empty Choices | Non-streaming `{"choices": []}` | Raises `LLMResponseInvalidError` | PASS (Typed exception) |
| 6 | Missing Choices | Non-streaming JSON without `choices` | Raises `LLMResponseInvalidError` | PASS (Typed exception) |
| 7 | Provider Error Payload | HTTP 200 containing `{"error": {"message": ...}}` | Raises `LLMResponseInvalidError` with message | PASS (Extracted diagnostic) |
| 8 | Mid-Stream Error Event | SSE `data: {"error": {"message": ...}}` | Raises `LLMStreamInterruptedError` | PASS (Interruption typed) |
| 9 | HTTP 401 Unauthorized | Invalid API key or expired token | Raises `LLMAuthenticationError` | PASS (Actionable credential message) |
| 10 | HTTP 429 Rate Limit | Upstream token/request quota reached | Raises `LLMRateLimitError` | PASS (Retry backoff suggested) |
| 11 | Unsupported Model | HTTP 404 / `model_not_found` | Raises `LLMModelUnavailableError` | PASS (Dual-subclass compatibility) |
| 12 | Unsupported Tools | HTTP 400 `tools are not supported` | Raises `LLMToolCallUnsupportedError` | PASS (Actionable tool error) |
| 13 | Partial/Compact SSE Frame | `data:{"choices"...}` without space | Strips prefix, parses valid JSON | PASS (`ChunkAChunkB`) |
| 14 | Multiple Tool Calls | Two distinct tool calls in stream | Aggregates calls by `index` key | PASS (`weather_lookup` & `web_search`) |
| 15 | Tool JSON Fragmentation | Fragmented argument string across 3 chunks | Concatenates `arguments_str`, parses JSON | PASS (`{"expression": "2+2"}`) |
| 16 | Network Interruption | Socket drop (`RemoteProtocolError`) mid-stream | Raises `LLMStreamInterruptedError` | PASS (Trace failed, quota released) |
| 17 | Timeout | `httpx.ReadTimeout` after timeout_seconds | Raises `LLMTimeoutError` | PASS (Formatted message) |
| 18 | Client Cancellation | Generator closed early (`GeneratorExit`) | Closes stream generator cleanly | PASS (`aclose()` handles cleanup) |
| 19 | Empty Successful Stream | Only `[DONE]` with zero tokens | Handled safely, runtime marks empty stream | PASS (`content == ""`) |
| 20 | Missing Final Event | Connection terminates without `[DONE]` | Yields available chunks, no crash | PASS (`Final sentence.`) |

---

## Quota Reservation and Observability Lifecycle

1. **Pre-flight Quota Reservation:**
   - Before calling the LLM stream, `QuotaService.reserve_quota()` reserves maximum token allocation.
2. **On Stream Failure / Exception:**
   - The exception handler executes:
     ```python
     quota_svc.release_reservation(reservation_id)
     await quota_svc.release_reservation_async(reservation_id)
     ```
   - Trace status transitions to `FAILED` with sanitized error message (API keys redacted).
   - Zero citations are persisted to the database.
   - An SSE error frame (`message_error`) is emitted to the client, preventing broken UI states.
3. **On Client Abort (`GeneratorExit`):**
   - Quota reservation is released immediately.
   - Trace is marked `CANCELLED`.
