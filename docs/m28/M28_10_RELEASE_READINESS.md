# M28.10 — Release Readiness & Local-to-Staging Acceptance Plan

## 1. Release Inventory & Changed Files Allowlist

| File | Subsystem | Nature of Change |
|---|---|---|
| `backend/app/llm/base.py` | LLM Architecture | Added typed provider exceptions |
| `backend/app/llm/providers/openai_provider.py` | Provider Adapter | Schema-aware non-streaming & streaming parser |
| `backend/app/assistant_runtime/runtime.py` | RAG Runtime | Substantive relevance filter, citation verification, safe error presentation |
| `backend/app/assistant_runtime/context.py` | Context Builder | Removed fake bounding boxes/p.1; added causal forecasting & citation rules |
| `backend/app/api/v1/conversations.py` | Conversations API | Resolved real chunk page numbers and genuine bounding boxes without fake defaults |
| `backend/app/services/web/search.py` | Web Intelligence | Implemented `ArxivSearchProvider` and honest `NOT_CONFIGURED` status |
| `backend/app/services/web/__init__.py` | Web Intelligence | Exported `ArxivSearchProvider` |
| `backend/tests/test_m05_citation_highlighting.py` | Test Regression | Aligned legacy assertions with M28.10 Phase 4.5 real provenance requirements |
| `backend/tests/test_m28_10_runtime_citations_and_search.py` | Test Suite | 14 automated verification tests |
| `frontend/lib/citations.ts` | Frontend Citations | Added `groupCitationsBySource` and robust deduplication |
| `frontend/app/dashboard/conversations/page.tsx` | Chat Workspace | Rendered grouped source badges; cleared citations on `message_error` |
| `frontend/lib/__tests__/citations.test.ts` | Frontend Test | Grouping and deduplication unit tests |

---

## 2. Operator Staging Acceptance Checklist

- [ ] **Check A — General Conversation**:
  - Ask: `"Do you have knowledge of C++?"`
  - Expected: Clear, helpful response on C++ capabilities; zero solar research citations.
- [ ] **Check B — Uploaded PDF Query**:
  - Ask: `"Based on my solar forecasting document, which model performed best in the reported experiment?"`
  - Expected: Accurate factual extraction from uploaded PDF; authentic page number (or null if absent); zero C++ references.
- [ ] **Check C — Scientific Recommendation**:
  - Ask: `"Which models should I test next for solar irradiance forecasting, and why?"`
  - Expected: Recommends baselines first; discusses causal constraints of Bi-LSTM (no future target leakage); does not invent experimental metrics.
- [ ] **Check D — Academic Web Search**:
  - Ask: `"Search for recent solar irradiance forecasting research and compare applicable models with my uploaded paper."`
  - Expected: Real papers retrieved from ArXiv REST API with title, abstract, and `arxiv.org` URL; clear distinction between online literature and uploaded documents.
- [ ] **Check E — Direct Webpage Reading**:
  - Ask: `"Read https://www.w3schools.com/cpp/cpp_for_loop.asp and explain the for-loop examples."`
  - Expected: Webpage extracted; tutorial content explained; web citation displayed; zero PDF citations.
- [ ] **Check F — Provider Error Simulation**:
  - Trigger malformed response.
  - Expected: Actionable error message (`"Couldn't generate a response because the AI provider returned an invalid response..."`); no raw KeyError; no precomputed citations.
- [ ] **Check G — Historical Conversation Reload**:
  - Reload existing chats.
  - Expected: All messages preserved; authentic page numbers loaded; zero fabricated bounding boxes.
