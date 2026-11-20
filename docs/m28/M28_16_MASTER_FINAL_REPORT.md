# M28.16 Master Final Report — Provider Rate Limits, Model Compatibility, Token Economy & Citation Integrity

**Milestone:** M28.16  
**Status:** `M28_16_LOCAL_PASS_STAGING_APPROVAL_REQUIRED`  
**Execution Authority:** Operator Authorized Investigation & Implementation  
**Baseline Git Commit:** `5cf20cbd99c194c7dffbb050491970f8d29210f4`  

---

## 1. Executive Summary

Milestone M28.16 successfully resolved the critical provider infrastructure, token quota, and conversational fidelity issues uncovered during M28.15 live staging acceptance:

1. **Groq Free-Tier Rate-Limit Recovery (`tr_0c3983c22a024f37`):**
   - Eliminated token starvation by establishing a strict 1,200 token budget for RAG candidate chunks and bounding academic preprints.
   - Upgraded default Groq model from the 8,000 TPM `openai/gpt-oss-120b` to high-throughput `llama-3.3-70b-versatile`.
   - Engineered header and body regex extraction for `retry-after` seconds, raising structured `LLMRateLimitError` and displaying actionable user countdown guidance.
2. **Gemini Streaming HTTP 404 Resolution (`tr_e5eeae162b35455b`):**
   - Corrected model normalization to eliminate double `/models/models/` prefix path bugs.
   - Migrated default model resolution from deprecated `gemini-1.5-flash` to production-grade `gemini-2.0-flash`.
   - Mapped HTTP 404 to typed `LLMModelUnavailableError` (differentiating retirement from connection drops) and implemented live model discovery via `list_available_models`.
3. **Empty KB / Anti-Hallucination Guardrails (`tr_44b83ef2dc85405d`):**
   - Removed hardcoded domain-specific "solar irradiance" text from generic behavioral templates.
   - Injected strict negative system prompt instructions when 0 knowledge bases are connected: assistants explicitly disclaim document access and are strictly forbidden from emitting bracket citations `[1]`, `[2]`.
4. **Conversational URL Retention:**
   - Extended message history window to 25 messages and added URL harvesting regex to retain user-shared reference links across multiple dialogue turns.
5. **Educational Assessment & Quiz Formatting Standards:**
   - Standardized structured formatting for quizzes and exams (separate indented lines for options A–D, dedicated Answer Key & Explanations, eliminating cramped horizontal tables).

---

## 2. Quantitative Verification

| Component | Test Suite | Tests Passed | Status |
|---|---|---|---|
| Provider Limits & Models | `test_m28_16_provider_limits_and_model_resolution.py` | 20 / 20 | PASS |
| Groq & API Hardening | `test_groq_and_api_hardening.py` | 10 / 10 | PASS |
| Groq Tool Choice & Research | `test_m28_12_groq_tool_choice_and_research_search.py` | 29 / 29 | PASS |
| Frontend UX & Citations | `frontend/lib/__tests__/*.test.ts` | 43 / 43 | PASS |
| Frontend Typecheck | `npx tsc --noEmit` | 0 errors | PASS |
| Frontend Production Build | `npm run build` (Turbopack) | 24 / 24 routes | PASS |

---

## 3. Preservation of Approved Features

- **Upload & Save to PF:** Preserved.
- **Ingestion & RAG:** Preserved.
- **Back, Forward & Refresh Navigation:** Preserved.
- **Historical Cricket Document:** Preserved in Neon PostgreSQL database.

---

## 4. Next Step & Release Recommendation

In accordance with Global Antigravity Invariant #13 (Safety & Cost Control), no git commits, git pushes, or Render deployments have been triggered. The code is fully tested and verified locally.

**Next Action:** Awaiting explicit operator staging approval (`M28_16_LOCAL_PASS_STAGING_APPROVAL_REQUIRED`).
