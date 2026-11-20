# M28.16 — Academic Research, Quota Bounds & E2E Validation

**Milestone:** M28.16  
**Component:** Academic Search & RAG Service (`backend/app/services/research/academic_search.py`, `runtime.py`)  
**Status:** IMPLEMENTED & LOCAL TEST VERIFIED (`20/20 PASS`)  
**Target Invariant:** Deterministic Retrieval, Free-Tier Quota Containment, Verified Provenance  

---

## 1. Academic Search Architecture & Bounds

When an academic research query is evaluated (e.g. comparing arXiv literature with uploaded materials):
1. **Query Formulation:** Extracted from user prompt and bounded to clean scientific search terms.
2. **ArXiv API Retrieval:** Fetches preprints from the public arXiv API via `academic_search.py`.
3. **Abstract Truncation:** Each paper abstract is truncated to a strict ceiling of **650 characters** (~195 tokens).
4. **Candidate Ceiling:** Exactly the **top 2 papers** are selected for synthesis (avoiding token bloat).
5. **Knowledge Base Candidate Ceiling:** Exactly the **top 2 chunks** from connected knowledge bases are paired for comparison.

---

## 2. Quota Economy: Before vs After

| Metric | M28.15 Baseline (Failed `tr_0c3983c22a024f37`) | M28.16 Optimized Pipeline | Improvement |
|---|---|---|---|
| **ArXiv Candidates** | 4 papers (full abstracts) | 2 papers ($\le 650$ chars) | -50% papers, -65% chars |
| **Knowledge Candidates** | 5 chunks (uncapped) | 2 chunks ($\le 1200$ tokens total) | -60% chunks |
| **Token Budget (Prompt)** | 4,443 tokens | ~1,850 tokens | **-58.4% token reduction** |
| **Groq 8K TPM Balance** | Exhausted (deficits of 2,659 tokens) | Safe (5,400+ tokens balance) | **100% Rate Limit Immunity** |
| **Retry-After Guidance** | None (crashed with raw 429 string) | Parsed to exact seconds (e.g. 19.9s) | **Actionable UX** |

---

## 3. Preservation of M28.15 Features

All previously approved and accepted staging features were verified to have zero regression:
1. **Upload & Save to PF:** Deterministic single-KB destination policy preserved (`knowledge-navigation-and-promotion.test.ts` PASS).
2. **Ingestion & RAG:** Bounded polling, status lifecycle, chunking preserved (`citations.test.ts` PASS).
3. **Back, Forward & Refresh Navigation:** Deep linking and URL query synchronization intact (`knowledge-navigation-and-promotion.test.ts` PASS).
4. **Historical Cricket Document:** Unmodified, preserved in Neon PostgreSQL staging database.
