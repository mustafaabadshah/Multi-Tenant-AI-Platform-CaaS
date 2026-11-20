# M28.12 Root Cause Analysis: Groq Tool-Choice Mismatch & Provider Stream Failures

## Executive Summary

During live staging verification under M28.11, Test D (*"Search recent solar irradiance forecasting papers and compare them with my uploaded paper."*) failed repeatedly with:
```
Provider 'groq' stream error: Tool choice is none, but model called a tool
```
This headline defect surfaced as a user-facing generation interruption:
```
"LLM generation failed: The response stream was interrupted by the AI provider. Please retry."
```
Investigation across trace `tr_2ecdbce83b5a4294` confirmed this was **not** a generic network or transport interruption, but an exact provider API conflict between the assistant prompt instructions, model capabilities, and request payload schema.

---

## 1. Trace Evidence & Reproduction

- **Trace ID:** `tr_2ecdbce83b5a4294`
- **Provider:** `groq`
- **Default Production Model:** `openai/gpt-oss-120b` (fallback / versatile)
- **User Prompt:** *"Search recent solar irradiance forecasting papers and compare them with my uploaded paper."*
- **Exact Upstream Error:** `Tool choice is none, but model called a tool` (HTTP 400 or SSE mid-stream error event).

---

## 2. Root Cause Breakdown

### A. Missing `tools` and `tool_choice` in Groq Normalization
In `backend/app/llm/providers/groq_provider.py`, the `_normalize_config(config)` method stripped `tools` from the incoming `LLMConfig`:
```python
# PREVIOUS DEFECTIVE CODE:
return LLMConfig(
    provider=config.provider,
    model=model,
    temperature=config.temperature,
    max_tokens=config.max_tokens,
    api_key=config.api_key,
    base_url=config.base_url,
    timeout_seconds=config.timeout_seconds,
    extra_headers=extra_h,
    # 'tools' was omitted!
)
```
Consequently, when `super().generate_stream(...)` was called on `OpenAICompatibleLLMProvider`, `config.tools` was `None`. No `tools` schemas were advertised in the HTTP POST body.

### B. Omission of `tool_choice="auto"` in OpenAI-Compatible Provider
In `backend/app/llm/providers/openai_provider.py`, even when `config.tools` was populated, the JSON payload did not specify `"tool_choice": "auto"`:
```python
# PREVIOUS CODE:
if config.tools:
    payload["tools"] = [...]
    # 'tool_choice' was omitted!
```
On Groq and certain OpenAI-compatible gateways, omitting `tool_choice` or allowing it to default to `none` while the model emits tool-call tokens creates a fatal contract mismatch:
`Tool choice is none, but model called a tool`.

### C. Prompt Conflict When Tools Are Not Configured
In `backend/app/assistant_runtime/context.py`, the Tier 1 immutable platform security prompt previously included:
```
"- WEB BROWSING & TOOLS: You have access to real-time web reading tools (web_read_url, web_search)..."
```
regardless of whether tools were actually enabled for the assistant or supported by the model. When the user issued an explicit paper search command, the model followed the system prompt directive to invoke tools; but because no tools were defined in the API request, Groq immediately aborted the stream.

### D. Misclassification as Generic Transport Disruption
In `OpenAICompatibleLLMProvider.generate_stream`, any mid-stream `error` event was captured and raised as `LLMStreamInterruptedError(f"Provider '{self._name}' stream error: {err_msg}")`. This caused the error handling layer to report it as a network interruption rather than a typed `LLMToolCallUnsupportedError`.

---

## 3. Implemented Fixes

1. **Config Normalization (`groq_provider.py`):**
   - Retained `tools=config.tools` and `tool_choice=getattr(config, "tool_choice", None)` in `_normalize_config`.
2. **Explicit `tool_choice: "auto"` (`openai_provider.py`):**
   - Whenever `config.tools` is non-empty, `payload["tool_choice"] = getattr(config, "tool_choice", None) or "auto"`.
3. **Structured Role & Multi-Turn Message Payloads:**
   - Implemented `_format_messages_payload` mapping `tool_call_id` on tool messages and `tool_calls` on assistant messages to maintain sequence integrity.
4. **Conditional Tool Prompting (`context.py`):**
   - System prompt instructions now check `tools_enabled`. When tools are absent, the prompt explicitly instructs:
     `"Ground your answers strictly in the provided Knowledge Base and Web Context below. Do not attempt to invoke external tool calls or functions."`
5. **Typed Error Classification & Recovery (`openai_provider.py` & `runtime.py`):**
   - Mid-stream tool conflicts are classified into `LLMToolCallUnsupportedError` and categorized as `ErrorCategory.TOOL_ERROR`.
   - The runtime implements a single-pass safe fallback: if tools were active and conflict occurs, it retries with tools disabled so the model completes text generation using verified preflight context.
