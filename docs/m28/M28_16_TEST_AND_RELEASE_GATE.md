# M28.16 — Test Matrix & Staging Release Gate

**Milestone:** M28.16  
**Status:** `M28_16_LOCAL_PASS_STAGING_APPROVAL_REQUIRED`  
**Git Working Tree:** Clean baseline preserved; all new tests passing  

---

## 1. Automated Test Execution Evidence

### 1.1 Backend Test Suites
Executed in workspace virtual environment (`.\backend\.venv\Scripts\python.exe -m pytest`):
```text
backend/tests/test_m28_16_provider_limits_and_model_resolution.py: 20 passed in 1.42s
backend/tests/test_groq_and_api_hardening.py: 10 passed in 0.88s
backend/tests/test_m28_12_groq_tool_choice_and_research_search.py: 29 passed in 2.15s
```
**Total Targeted Backend Tests:** 59 passed, 0 failed.

### 1.2 Frontend Test Suites & Build
Executed in `frontend/` (`npm test`, `npx tsc --noEmit`, `npm run build`):
```text
▶ M28.10 Citation Grouping & Deduplication (3 tests) - PASS
▶ M28.13 Deterministic Destination Policy (4 tests) - PASS
▶ M28.13 Knowledge Navigation & URL Sync (2 tests) - PASS
▶ M28.13 Bounded Ingestion Polling Lifecycle (3 tests) - PASS
▶ Speech Sanitation & Chunking (3 tests) - PASS
▶ BrowserSpeechRecognizer (3 tests) - PASS
▶ BrowserSpeechSynthesizer (2 tests) - PASS
▶ VoiceSessionController (4 tests) - PASS
▶ Additional Voice Edge Cases (2 tests) - PASS
▶ M28.8.1 Secure Overview-to-Chat Handoff (6 tests) - PASS
▶ M28.8 Assistant Creation & Validation Interactions (3 tests) - PASS
▶ M28.8 Desktop Hybrid & Mobile Assistant Selection (2 tests) - PASS
▶ M28.8 Knowledge Base & Webpage Preflight Validation (2 tests) - PASS
▶ M28.8 Navigation Architecture & Role-Based Actions (4 tests) - PASS

Total Frontend Tests: 43 passed, 0 failed in 4.48s
TypeScript (tsc --noEmit): 0 errors
Next.js Production Build (next build): Compiled successfully, 24/24 static pages prerendered.
```

---

## 2. Release Gate Checklist

- [x] Zero unapproved git commits or remote pushes executed.
- [x] Zero Render deployments triggered during local implementation phase.
- [x] Zero live Neon database migrations executed (`0018_m28_message_feedback` remains head).
- [x] Rate limit retry-after parsing verified for Groq headers and body text.
- [x] Gemini 404 cleanly mapped to `LLMModelUnavailableError` and `auto` resolved to `gemini-2.0-flash`.
- [x] Token budget capped at 1,200 tokens for RAG candidate chunks.
- [x] Anti-hallucination constraint active when knowledge bases are detached.
- [x] Cross-turn URL retrieval retained across 25 messages.
- [x] All 4 accepted M28.15 workflows verified without regression.

**Verdict:** `M28_16_LOCAL_PASS_STAGING_APPROVAL_REQUIRED`
