# M28.10 — LLM Provider Failure Audit & Recovery

## 1. Executive Summary & Root Cause Investigation
During production operation on traces `tr_c3cb4e5f`, `tr_479738de`, `tr_129a070a`, and `tr_f19822f5`, users encountered runtime crashes displaying:
`LLM generation failed: 'choices'`
These failures left the user turn in an uncompleted, failed state with 0 Time-To-First-Token (TTFT), 0 token accounting, but prematurely surfaced retrieved citations.

### Root Cause Analysis
1. **Unsafe Schema Access in OpenAI-Compatible Provider Adapter**:
   In `backend/app/llm/providers/openai_provider.py`:
   - Non-streaming: `choice = data["choices"][0]`
   - Streaming: `choice = chunk_data["choices"][0]`
2. **Provider Response Incompatibility**:
   Modern OpenAI-compatible inference endpoints (Groq, vLLM, Ollama, OpenAI) emit asynchronous Server-Sent Event (SSE) frames for token usage statistics, e.g.:
   ```json
   {"usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14}}
   ```
   Such frames deliberately omit the `choices` array. When `chunk_data["choices"][0]` was executed without structural validation, Python raised `KeyError: 'choices'`. Because the exception handler only caught `json.JSONDecodeError`, the KeyError bubbled up uncaught through `stream_chat`, terminating the generation stream.
3. **Mid-Stream Error Payloads**:
   If an inference worker or GPU terminated mid-stream, providers emit `{"error": {"message": "..."}}`. Direct index access threw `KeyError: 'choices'` rather than surfacing the typed provider error.

---

## 2. Failure Matrix

| Trace Prefix | Provider | Stage | Error Category | Root Cause | Evidence |
|---|---|---|---|---|---|
| `tr_c3cb4e5f` | OpenAI-compatible | Streaming | `PROVIDER_RESPONSE_INVALID` | Unhandled usage-only SSE frame lacking `choices` | SSE payload `{"usage": {...}}` raised `KeyError: 'choices'` |
| `tr_479738de` | OpenAI-compatible | Streaming | `PROVIDER_STREAM_INTERRUPTED` | Provider error frame `{"error": {...}}` indexed for `choices` | Raw KeyError bubbled to client as `LLM generation failed: 'choices'` |
| `tr_129a070a` | OpenAI-compatible | Completion | `PROVIDER_RESPONSE_INVALID` | Response JSON returned empty `choices: []` | Raised `IndexError` / `KeyError` |
| `tr_f19822f5` | OpenAI-compatible | Pre-flight | `PROVIDER_AUTHENTICATION_FAILED` | Endpoint returned HTTP 200 with JSON error object | Bypassed HTTP status check; failed on choices lookup |

---

## 3. Engineering Fixes Implemented

### 3.1 Typed Provider Error Hierarchy (`backend/app/llm/base.py`)
Introduced typed exception classes:
- `LLMResponseInvalidError(LLMProviderError)`: For malformed JSON, missing/empty choices, non-dict payloads.
- `LLMStreamInterruptedError(LLMProviderError)`: For mid-stream provider error frames and socket terminations.
- `LLMModelUnavailableError(LLMConfigurationError)`: For unavailable/unsupported model IDs.
- `LLMToolCallUnsupportedError(LLMProviderError)`: For invalid or unsupported tool calling.

### 3.2 Schema-Aware Non-Streaming Parsing (`backend/app/llm/providers/openai_provider.py`)
- Verified `data` is a valid dictionary.
- Inspected for provider `error` payloads and raised `LLMResponseInvalidError` with sanitized provider details.
- Validated `choices` is a non-empty list and `choices[0]` is a valid dictionary.
- Safely extracted content, role, finish_reason, tool_calls, and token usage with fallback defaults.

### 3.3 Schema-Aware Streaming Parsing (`backend/app/llm/providers/openai_provider.py`)
- Correctly parsed `[DONE]` terminator frames.
- Handled mid-stream error payloads by raising `LLMStreamInterruptedError`.
- Validated `choices` in streaming frames: if `choices` is missing or empty (e.g. usage-only or keepalive metadata frames), the adapter cleanly records usage or skips the frame (`continue`) without crashing.
- Safely extracted delta content and multiple tool-call argument fragments.

---

## 4. Verification Evidence
- `test_openai_provider_missing_choices_raises_typed_error`: PASSED
- `test_openai_provider_empty_choices_raises_typed_error`: PASSED
- `test_openai_provider_http200_error_payload_raises_typed_error`: PASSED
- `test_openai_provider_streaming_usage_only_chunk_does_not_crash`: PASSED
- `test_openai_provider_streaming_error_frame_raises_stream_interrupted`: PASSED
