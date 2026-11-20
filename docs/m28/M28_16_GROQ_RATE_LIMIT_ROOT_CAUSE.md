# M28.16 — Groq Free-Tier Rate-Limit Root Cause Analysis & Recovery Engine

**Milestone:** M28.16  
**Component:** Backend LLM Provider (`backend/app/llm/providers/groq_provider.py`, `openai_provider.py`, `base.py`)  
**Status:** IMPLEMENTED & LOCAL TEST VERIFIED (`20/20 PASS`)  
**Target Trace:** `tr_0c3983c22a024f37`  

---

## 1. Incident Forensics & Error Diagnostics

### 1.1 Trace Failure Evidence (`tr_0c3983c22a024f37`)
During an academic research workflow comparing an arXiv preprint with uploaded study materials, the provider generation span failed with HTTP 429:
```json
{
  "trace_id": "tr_0c3983c22a024f37",
  "provider": "groq",
  "model": "openai/gpt-oss-120b",
  "status": "FAILED",
  "error": "Groq streaming failed: HTTP 429 - {
    \"error\": {
      \"message\": \"Rate limit reached for model `openai/gpt-oss-120b` in organization `org_xxx` on tokens per minute (TPM): Limit 8000, Used 6216, Requested 4443. Please try again in 19.944s.\",
      \"type\": \"tokens\",
      \"code\": \"rate_limit_exceeded\"
    }
  }"
}
```

### 1.2 Quantitative Dissection
- **Model Assigned:** `openai/gpt-oss-120b` (Groq free tier default).
- **Per-Minute Token Limit:** 8,000 TPM (extremely narrow window).
- **Tokens Consumed in Sliding Window:** 6,216 TPM already used.
- **Tokens Requested in Single Call:** 4,443 tokens.
- **Available Balance:** $8,000 - 6,216 = 1,784$ tokens.
- **Deficit:** $4,443 - 1,784 = 2,659$ tokens over limit.
- **Provider Cooling Window:** `19.944s` before quota replenishment.

---

## 2. Root Cause Analysis

1. **Uncapped RAG Context Assembly:**
   When academic research mode activated, the runtime fetched 4 arXiv preprint candidate chunks and combined them with 5 knowledge base candidate chunks. All 9 chunks were injected into the system prompt without a token limit, inflating prompt token consumption to over 3,800 tokens alone.
2. **Suboptimal Default Model Configuration:**
   Groq free tier assigns only 8,000 TPM to large compound models like `openai/gpt-oss-120b`, whereas `llama-3.3-70b-versatile` offers higher throughput (12,000–30,000 TPM) and superior structured reasoning.
3. **Missing Typed Rate-Limit Exception Handling:**
   `_handle_http_error` in `openai_provider.py` raised a generic `LLMConnectionError` or `LLMProviderError` string, losing the critical `retry-after` header and body metadata needed for graceful UX recovery.

---

## 3. Engineering Implementation

### 3.1 Structured `LLMRateLimitError` Attributes (`backend/app/llm/base.py`)
```python
class LLMRateLimitError(LLMProviderError):
    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
        limit_type: str | None = None,
        model: str | None = None,
        provider: str | None = None,
    ):
        super().__init__(message)
        self.retry_after = retry_after
        self.limit_type = limit_type
        self.model = model
        self.provider = provider
```

### 3.2 Robust Retry-After Extraction (`backend/app/llm/providers/openai_provider.py`)
1. Checks response HTTP header `retry-after` (parsing integer or float seconds).
2. If absent from headers, executes regex pattern matching across Groq error response bodies:
   - `try again in ([\d\.]+)\s*s`
   - `try again in ([\d\.]+)\s*ms`
3. Classifies quota category (`TPM` for tokens per minute, `RPM` for requests per minute, or `general`).
4. Re-raises typed `LLMRateLimitError` populated with structured metadata.

### 3.3 Default Model Upgrade (`backend/app/llm/providers/groq_provider.py`)
- Changed `GROQ_DEFAULT_MODEL` default from `openai/gpt-oss-120b` to `llama-3.3-70b-versatile` (configurable via environment variable `GROQ_DEFAULT_MODEL`).
- Retained full fallback compatibility for explicit user overrides.

### 3.4 Bounded Context & Token Budgeting (`backend/app/assistant_runtime/context.py`)
- Implemented `max_knowledge_tokens: int = 1200` budget cap.
- Evaluates chunk candidates in descending relevance order; stops appending candidate chunks immediately once cumulative tokens exceed 1,200 tokens.
- Bounded academic research preprints to the top 2 papers (max 650 chars abstract each) and top 2 KB comparison chunks.
- Restricts total conversation history tokens to ~350 tokens (last 4 messages / 2 turns).

---

## 4. Verification Evidence

- `backend/tests/test_m28_16_provider_limits_and_model_resolution.py` verified:
  - Header `retry-after: 25` parsing: `retry_after == 25.0`, `limit_type == "TPM"`.
  - Body text `Please try again in 19.944s` parsing: `retry_after == 19.944`, `limit_type == "TPM"`.
  - `limit_type` accurately differentiates `RPM` (requests per minute) from `TPM`.
  - Token budget strictly drops 3rd and 4th chunks when cumulative tokens exceed 1,200 tokens.
  - Total prompt payload fits comfortably within Groq free-tier limits ($< 2,200$ tokens total).
