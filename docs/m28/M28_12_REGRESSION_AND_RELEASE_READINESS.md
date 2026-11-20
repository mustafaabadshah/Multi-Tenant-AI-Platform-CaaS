# M28.12 Regression & Staging Release Readiness

## 1. Summary of Changes

The following files have been updated for M28.12:

### Backend:
1. `backend/app/llm/base.py`:
   - Added `tool_choice: Optional[str] = None` to `LLMConfig`.
   - Added `tool_call_id: Optional[str] = None` and `tool_calls: Optional[list[dict[str, Any]]] = None` to `LLMMessage`.
2. `backend/app/llm/providers/groq_provider.py`:
   - Preserved `tools` and `tool_choice` in `_normalize_config`.
3. `backend/app/llm/providers/openai_provider.py`:
   - Formatted multi-turn tool message payloads (`tool_call_id`, `tool_calls`).
   - Added `payload["tool_choice"] = getattr(config, "tool_choice", None) or "auto"` when `config.tools` is non-empty.
   - Categorized mid-stream tool error events to typed `LLMToolCallUnsupportedError`.
   - Expanded `_handle_http_error` to catch tool choice mismatches.
4. `backend/app/assistant_runtime/context.py`:
   - Conditioned tool instruction in Tier 1 platform security on `tools_enabled`.
   - Added instruction to always wrap programming code in fenced code blocks with language identifiers.
   - Added fallback for `page_number` from chunk metadata.
5. `backend/app/assistant_runtime/markdown_normalizer.py`:
   - Protected trailing unclosed code blocks in `_unescape_markdown`.
6. `backend/app/services/web/search.py`:
   - Replaced placeholder arXiv User-Agent with truthful identifier and env-override support.
7. `backend/app/observability/policy.py`:
   - Added `TOOL_ERROR` and `GENERATION_FAILED` to `ErrorCategory`.
   - Standardized tool conflict error categorization.
8. `backend/app/services/research/academic_search.py` (New):
   - Deterministic academic intent classification, query extraction, and terms-compliant arXiv preflight.
9. `backend/app/services/research/__init__.py` (New):
   - Package exports.
10. `backend/app/assistant_runtime/runtime.py`:
    - Early tool resolution before context assembly.
    - Integrated deterministic academic search preflight.
    - Added execution ledger deduplication for academic searches.
    - Added single-pass safe fallback on `LLMToolCallUnsupportedError`.
    - Hardened tool execution against unregistered/unauthorized tools.
    - Formatted user-facing error for `LLMToolCallUnsupportedError`.
11. `backend/tests/test_m28_12_groq_tool_choice_and_research_search.py` (New):
    - Comprehensive test suite covering Scenarios A through F, tool choice, security, and markdown formatting.

### Frontend:
1. `frontend/components/chat/MarkdownRenderer.tsx`:
   - Added `CodeBlockView` with syntax header and interactive copy button.
   - Handled indented and trimmed code fences.

---

## 2. Infrastructure & Cost Boundaries

- **Database:** Neon Staging (`aged-heart-01771250`), revision `0018_m28_message_feedback`. No new database migration required.
- **Provider Costs:** $0.00 additional cost. Uses terms-compliant free arXiv API and existing configured Groq/BYOK endpoints.
- **Render Staging:**
  - Backend: `srv-dbrk57gn74is73fqo4k0` (`https://mmaip-backend.onrender.com`)
  - Frontend: `srv-dbrkthcipgvc739d6oh0` (`https://mmaip-frontend.onrender.com`)

---

## 3. Verification Evidence

### Backend Test Suites:
1. **Dedicated M28.12 Test Suite (`test_m28_12_groq_tool_choice_and_research_search.py`):**
   - 29/29 tests passed in 0.69s.
   - Covers: Groq normalization & tool-choice preservation, OpenAI provider tool formatting & mid-stream error handling, arXiv preflight & intent extraction, tool security & ledger deduplication, markdown & C++ code fence formatting, Scenarios A through F.
2. **Full Backend Pytest Regression:**
   - 817 passed, 18 skipped in full suite.

### Frontend Test & Build Suites:
1. **Jest Unit Tests (`npm test -- --watchAll=false`):**
   - 34/34 tests passed in 3.68s.
2. **TypeScript Typecheck (`npx tsc --noEmit`):**
   - Exit code 0 (clean).
3. **Next.js Production Build (`npm run build`):**
   - Exit code 0 (all 24 routes successfully compiled into production bundle).

---

## 4. Staging Deployment Release Gate

Per safety instructions, **NO commits, pushes, or Render deployments** are executed during this audit and repair phase.
The system stands at:
`M28_12_LOCAL_PASS_STAGING_APPROVAL_REQUIRED`
awaiting explicit operator authorization for staging release.
