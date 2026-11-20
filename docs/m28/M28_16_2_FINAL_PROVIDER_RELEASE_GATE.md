# M28.16.2 — Final Provider, Per-Turn Model Selector & Token Accounting Release Gate

**Date:** 2026-11-20  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Base Deployed Commit:** `5cf20cbd99c194c7dffbb050491970f8d29210f4`  
**Branch:** `main`  
**Governing Standard:** Universal Antigravity Engineering System V2  

---

## 1. Git State & Integrity

- **Branch:** `main`
- **Baseline Remote HEAD:** `5cf20cbd99c194c7dffbb050491970f8d29210f4`
- **Local Working Tree:** Clean baseline tracking `origin/main`. Controlled release modifications are preserved locally.
- **Git Invariants Enforced:** Zero unapproved git commits, zero git pushes, zero Render deployments, and zero Neon schema migrations executed during this gate.

---

## 2. Groq Model Availability & Deprecation Audit

### Deprecation Findings
Official Groq platform notices confirmed that legacy models (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`) are phased out for Free/Developer tiers and reserved for contracted enterprise tiers.

### Active Free-Tier Evaluation
- **Evaluated Models:** `openai/gpt-oss-20b` vs `openai/gpt-oss-120b`.
- **`openai/gpt-oss-20b` Specs on Groq:**
  - Context window: 131,072 tokens (128K).
  - Max completion tokens: 8,192 (up to 65,536).
  - Native Tool Calling: Yes (function calling enabled).
  - JSON Mode: Yes (structured output support).
  - Rate-Limit Impact: Far lower token pressure on Groq Free TPM limits compared to the 120B variant, preventing premature 429 quota exhaustion.
- **`openai/gpt-oss-120b` Specs on Groq:**
  - Preserved in capability catalog as an optional high-capacity model, subject to 8K TPM rate limits.

---

## 3. Effective Groq Default Configuration

- **Default Model:** `openai/gpt-oss-20b` in [`backend/app/llm/providers/groq_provider.py`](file:///e:/MM%20Office/Multi-Tanant-CaaS/backend/app/llm/providers/groq_provider.py#L13).
- **Environment Override:** Configurable via `GROQ_DEFAULT_MODEL`.
- **Model Normalization:** When inbound `model="auto"`, Groq resolves cleanly to `openai/gpt-oss-20b`.
- **Capability Registry:** Added `openai/gpt-oss-20b` to [`backend/app/llm/capabilities.py`](file:///e:/MM%20Office/Multi-Tanant-CaaS/backend/app/llm/capabilities.py#L25-L40), and marked legacy Llama models as phased out on free tier.

---

## 4. Gemini Model Verification

- **Default Model:** `gemini-3.5-flash-lite` (Google AI Studio `v1beta` `generateContent` and `streamGenerateContent`).
- **Path Normalization:** Normalized by stripping redundant `models/` prefix.
- **Catalog Distinction:**
  - *Documented / Active:* `gemini-3.5-flash-lite`, `gemini-3.8-flash`.
  - *Documented / Retired:* `gemini-2.0-flash` (retired June 1, 2026), `gemini-1.5-flash`, `gemini-1.5-pro`.
  - *Generation Capability:* Validated via automated tests; mapped HTTP 404 to typed `LLMModelUnavailableError`.
  - *Live Generation:* Kept **NOT RUN** to prevent unapproved paid billing charges in staging preflight.

---

## 5. Per-Turn Model Selector Security & Authorization

Trace analysis from frontend selector to backend execution:
`Frontend Selector → Request Payload → Tenant Authorization → Assistant Config → Provider Resolution → BYOK Vault → Quota → Streaming → Observability`

1. **Multi-Tenant BYOK Isolation:** Key retrieval strictly scoped by `self.tenant_id`. User in Tenant A cannot access Tenant B's credentials.
2. **Capability Registry Boundary:** Model overrides validated against [`cap_reg.get_model()`](file:///e:/MM%20Office/Multi-Tanant-CaaS/backend/app/assistant_runtime/runtime.py#L235-L255). Unknown or hallucinated model IDs are rejected with friendly 400-level SSE errors.
3. **Retired Model Gate:** Rejects retired models with actionable error advice.
4. **Tool Capability Check:** Tool availability resolved from effective model (`cap_reg.get_model(effective_provider, effective_model)`), preventing tool calls on models lacking tool support.
5. **Persistent Default Preservation:** Per-turn overrides are strictly request-scoped; the assistant's saved database record remains unchanged.
6. **Backward Compatibility:** Public and developer API requests without `model` seamlessly use the assistant's default.

---

## 6. Truthful Token Usage Accounting

### Problem Addressed
Previously, streaming usage was estimated based on character length without differentiating actual provider-reported token usage.

### Solution Implemented
1. **Stream Usage Request:** Configured `"stream_options": {"include_usage": True}` in [`openai_provider.py`](file:///e:/MM%20Office/Multi-Tanant-CaaS/backend/app/llm/providers/openai_provider.py#L228).
2. **Usage Extraction:** Parsed `chunk_data.get("usage")` (OpenAI/Groq) and `usageMetadata` (Gemini), yielding them in [`LLMStreamChunk`](file:///e:/MM%20Office/Multi-Tanant-CaaS/backend/app/llm/base.py#L24).
3. **Estimation Flag:** Added `is_estimated: bool` to the SSE `usage` event:
   - When actual provider usage is present: `is_estimated = False` (exact input/output tokens recorded).
   - When provider omits usage: `is_estimated = True` (estimated token count recorded).
4. **Frontend Badge Transparency:**
   - Provider actual usage: `⚡ 276 tokens (182 in / 94 out) · 642ms` (emerald badge).
   - Estimated usage: `⚡ ~300 tokens (est.) · 810ms` (amber badge).
   - Pre-stream session fallback: `Session: 255 tokens (3 msgs)` (neutral gray badge).

---

## 7. Deterministic Research Quality Fixture

Automated verification of:
> *"Search recent solar irradiance forecasting papers and compare them with my uploaded paper."*

- **Preflight Academic Intent:** Verified `is_acad=True`, `acad_query="solar irradiance forecasting"`, `acad_comp=True`.
- **Candidate Ingestion:** Mocked top-2 arXiv preprints + top-2 internal PDF chunks.
- **Token Budget Ceiling:** Enforced 1,200 token combined KB budget cap.
- **Citation Provenance:** Clear separation of arXiv web sources and internal PDF page citations.
- **No Hallucinated Data:** Zero synthetic metrics generated; causal forecasting principles maintained.

---

## 8. Frontend Interaction Tests

New test suite in [`frontend/lib/__tests__/model-selector-and-usage.test.ts`](file:///e:/MM%20Office/Multi-Tanant-CaaS/frontend/lib/__tests__/model-selector-and-usage.test.ts):
- `✔ should resolve 'auto' to the assistant's default model when available`
- `✔ should preserve per-turn explicit model selection in payload`
- `✔ should reject uncataloged or hallucinated model IDs`
- `✔ should reject retired models with actionable guidance`
- `✔ should display exact provider-reported tokens with emerald styling`
- `✔ should explicitly mark estimated tokens with '~' and amber styling when provider usage is absent`
- `✔ should fall back to cumulative session tokens before first stream completes`
- `✔ should reset streaming state and retain last partial token count on abort`
- `✔ should parse SSE usage event payload without data corruption`

---

## 9. Full Regression Evidence

### Frontend Verification
```text
✔ Node Test Runner (lib/__tests__/*.test.ts): 52 passed across 17 suites (0 failed)
✔ TypeScript Typecheck (npx tsc --noEmit):    0 errors
✔ Next.js App Router (next build Turbopack):  24 / 24 routes prerendered cleanly in 8.2s
```

### Backend Verification
```text
✔ Core Runtime & Provider Suites (6 suites):   98 passed in 66.76s (0 failed, 100% pass)
  - test_m28_16_provider_limits_and_model_resolution.py [21 passed]
  - test_m28_12_groq_tool_choice_and_research_search.py [29 passed]
  - test_groq_and_api_hardening.py                     [10 passed]
  - test_m28_10_runtime_citations_and_search.py        [14 passed]
  - test_m05_provider_reliability.py                   [19 passed]
  - test_assistants_and_rag.py                         [5 passed]
✔ Full Pytest Regression Baseline:             846 passed, 18 skipped in 878.52s
```

---

## 10. Changed-File Inventory (Allowlist)

```text
README.md
backend/app/api/v1/conversations.py
backend/app/assistant_runtime/context.py
backend/app/assistant_runtime/runtime.py
backend/app/llm/base.py
backend/app/llm/capabilities.py
backend/app/llm/providers/gemini_provider.py
backend/app/llm/providers/groq_provider.py
backend/app/llm/providers/openai_provider.py
backend/app/observability/policy.py
backend/app/schemas/assistant.py
backend/app/services/research/academic_search.py
backend/tests/test_groq_and_api_hardening.py
backend/tests/test_m28_10_runtime_citations_and_search.py
backend/tests/test_m28_12_groq_tool_choice_and_research_search.py
backend/tests/test_m28_16_provider_limits_and_model_resolution.py
frontend/app/dashboard/assistants/AssistantCreationWizard.tsx
frontend/app/dashboard/conversations/page.tsx
frontend/app/dashboard/providers/page.tsx
frontend/lib/__tests__/model-selector-and-usage.test.ts
frontend/lib/__tests__/speech.test.ts
docs/m28/M28_16_1_PROVIDER_COMPATIBILITY_RELEASE_AUDIT.md
docs/m28/M28_16_2_FINAL_PROVIDER_RELEASE_GATE.md
```

---

## 11. Remaining Blockers & Next Actions

**Blockers:** Zero local blockers.  
**Release Readiness:** The platform is fully prepared for staged deployment.  
**Staging Status:** Stopped at the explicit staging approval gate.

---

## 12. Final Release Gate Verdict

**`M28_16_2_READY_FOR_STAGING_APPROVAL`**

The release candidate is verified. Provider defaults are active and free-tier compatible (`openai/gpt-oss-20b`, `gemini-3.5-flash-lite`). Per-turn model selection is secured against tenant crossing and unauthorized models. Token usage accounting is truthful. The working tree is intact and awaiting explicit operator instruction.
