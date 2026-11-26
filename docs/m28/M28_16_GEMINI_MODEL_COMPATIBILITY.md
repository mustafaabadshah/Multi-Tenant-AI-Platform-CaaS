# M28.16 — Gemini API Model Compatibility, Auto-Resolution & Discovery Engine

**Milestone:** M28.16  
**Component:** Backend LLM Provider (`backend/app/llm/providers/gemini_provider.py`, `capabilities.py`)  
**Status:** IMPLEMENTED & LOCAL TEST VERIFIED (`20/20 PASS`)  
**Target Trace:** `tr_e5eeae162b35455b`  

---

## 1. Incident Forensics & Error Diagnostics

### 1.1 Trace Failure Evidence (`tr_e5eeae162b35455b`)
When attempting to stream generation using the Gemini adapter, the provider span failed with HTTP 404:
```json
{
  "trace_id": "tr_e5eeae162b35455b",
  "provider": "gemini",
  "model": "auto",
  "status": "FAILED",
  "error": "Gemini streaming failed: HTTP 404 - {
    \"error\": {
      \"code\": 404,
      \"message\": \"models/gemini-1.5-flash is not found for API version v1beta, or is not supported for generateContent. Call ModelService.ListModels to see the list of available models and their supported methods.\",
      \"status\": \"NOT_FOUND\"
    }
  }"
}
```

### 1.2 Dissection of Failures
1. **Model Retirement / Discontinuation:**
   Google updated the `v1beta` endpoint to deprecate certain initial test designations of `gemini-1.5-flash`, replacing it with the production release `gemini-2.0-flash`.
2. **Model Name Duplication Path Bug:**
   If a user or caller specified `models/gemini-1.5-flash`, the URL constructor `f"{base_url.rstrip('/')}/models/{model}:streamGenerateContent"` resulted in:
   `https://generativelanguage.googleapis.com/v1beta/models/models/gemini-1.5-flash:streamGenerateContent`
   (a malformed double `/models/` path).
3. **Misleading Error Categorization:**
   The adapter caught HTTP 404 and wrapped it as `LLMConnectionError("Gemini streaming failed: HTTP 404 ...")`. This caused the observability layer to flag a transient network drop rather than an actionable configuration/model retirement error.

---

## 2. Engineering Solution

### 2.1 Model Path Normalization
In `GeminiProvider`:
```python
clean_model = model.strip()
if clean_model.lower().startswith("models/"):
    clean_model = clean_model[len("models/"):].strip()
```
This guarantees that regardless of whether the identifier is passed as `"gemini-2.0-flash"` or `"models/gemini-2.0-flash"`, the constructed URL is consistently:
`https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:streamGenerateContent`

### 2.2 Dynamic Auto-Resolution to `gemini-2.0-flash`
Resolved `auto` or empty model strings dynamically via `GEMINI_DEFAULT_MODEL` environment variable, defaulting to Google's current active stable production tier `gemini-2.0-flash`.

### 2.3 Distinct `LLMModelUnavailableError` Exception
When the Gemini API returns HTTP 404:
```python
if resp.status_code == 404:
    raise LLMModelUnavailableError(
        f"Gemini model '{clean_model}' is not available or retired: {resp.text}",
        model=clean_model,
        provider="gemini",
    )
```

### 2.4 Live Model Discovery Service (`list_available_models`)
Implemented `list_available_models(api_key)` in `GeminiProvider` querying:
`GET https://generativelanguage.googleapis.com/v1beta/models?key={api_key}`
Filters returned models for `supportedGenerationMethods` containing `"generateContent"`, stripping prefixes and providing real-time catalog discovery.

---

## 3. Verification Evidence

- `test_gemini_model_normalization_strips_prefix`: verifies `models/gemini-2.0-flash` is normalized to `gemini-2.0-flash`.
- `test_gemini_auto_resolves_to_2_0_flash`: verifies `auto` resolves to `gemini-2.0-flash`.
- `test_gemini_stream_404_raises_model_unavailable`: verifies HTTP 404 cleanly raises `LLMModelUnavailableError`.
- `test_gemini_list_models_filters_generate_content`: verifies model catalog discovery filters non-content models.
