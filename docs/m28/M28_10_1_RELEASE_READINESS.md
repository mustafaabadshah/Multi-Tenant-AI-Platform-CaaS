# M28.10.1 — Release Readiness & Gate Audit

## Release Checklist & Governance Gate

| Item | Requirement | Verification Evidence | Status |
|---|---|---|---|
| Git State | Clean working tree; origin aligned | Local `main` at `70e5491e...`, remote `origin/main` at `70e5491e...` | PASS |
| Provider Reliability | 20 test scenarios pass | `test_m28_10_1_provider_contract.py` (20 passed) | PASS |
| Citation Integrity | Verified citations, genuine provenance | `test_m28_10_1_citation_lifecycle.py` (10 passed) | PASS |
| arXiv Search | HTTPS, 3s pacing, XML safety, Preprints | Live smoke test 200 OK + unit tests pass | PASS |
| Frontend UX | Linear × Apple Notes workspace intact | 24 routes built (`npm run build`), 34 unit tests pass | PASS |
| TypeScript | Zero compilation errors | `npx tsc --noEmit` exit code 0 | PASS |
| Backend Regression | Full pytest regression suite | 786 passed, 18 skipped | PASS |
| Frontend Regression | Full node test suite | 34 passed, 0 failed | PASS |
| Secret Scan | Zero secrets, keys, or tokens in diff | Sanitizer confirmed, no credentials committed | PASS |
| Database Migration | Zero unauthorized live migrations | Revision remains `0018_m28_message_feedback` | PASS |
| Cost Incurred | $0.00 budget ceiling | Free-tier open arXiv API & local mocks | PASS ($0.00) |

---

## Changed Files Allowlist (M28.10 + M28.10.1)

### Backend
1. `backend/app/api/v1/conversations.py` — Real provenance reload, correct `is_web` check.
2. `backend/app/assistant_runtime/context.py` — Causal forecasting system prompt, genuine page/bbox logic.
3. `backend/app/assistant_runtime/runtime.py` — Substantive relevance filter with acronyms, deferred citation verification, typed error handling.
4. `backend/app/llm/base.py` — Typed exceptions (`LLMModelUnavailableError`, `LLMToolCallUnsupportedError`, `LLMResponseInvalidError`, `LLMStreamInterruptedError`).
5. `backend/app/llm/providers/openai_provider.py` — Schema-aware non-streaming/streaming, usage-only tolerance, 3s arXiv rate-limiting.
6. `backend/app/services/web/__init__.py` — Exports for web search.
7. `backend/app/services/web/search.py` — Hardened `ArxivSearchProvider` (HTTPS, 3s pacing lock, XML bounded parser, preprint label).
8. `backend/tests/test_m05_citation_highlighting.py` — Provenance alignment.
9. `backend/tests/test_m28_10_runtime_citations_and_search.py` — Core M28.10 test suite.
10. `backend/tests/test_m28_10_1_provider_contract.py` — Comprehensive 20-scenario provider test suite.
11. `backend/tests/test_m28_10_1_citation_lifecycle.py` — Citation lifecycle and acronym relevance test suite.

### Frontend
1. `frontend/app/dashboard/conversations/page.tsx` — Grouped citation display, error clearing.
2. `frontend/lib/citations.ts` — `groupCitationsBySource` implementation.
3. `frontend/lib/__tests__/citations.test.ts` — Unit test suite for citation grouping & deduplication.

### Documentation
1. `docs/m28/M28_10_*.md` (10 documents)
2. `docs/m28/M28_10_1_*.md` (6 documents)
