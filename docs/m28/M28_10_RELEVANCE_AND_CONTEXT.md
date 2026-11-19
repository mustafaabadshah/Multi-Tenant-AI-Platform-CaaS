# M28.10 — Query Relevance & Context Selection

## 1. Problem Statement: Cross-Domain Citation Pollution
When testing queries such as:
`"Do you have knowledge of C++?"`
The assistant cited:
- `Solar_irradiance__TechScience.pdf`
- `C___For_Loop.html`
- `C++ For Loop`

Even though the solar irradiance research paper had zero relevance to C++ programming, the vector search returned it as one of the nearest semantic candidates, and the runtime blindly inserted it into the prompt context and citation payload.

---

## 2. Root Cause
1. **Blind Retrieval Ingestion**: `runtime.py` executed hybrid/semantic retrieval across all attached KBs without checking whether the user query was a general capability question or whether candidate chunks possessed substantive relevance to the query terms.
2. **Missing Stopword & Keyword Boundaries**: Prepositions (such as `"for"` in `"for solar irradiance forecasting"`) caused cross-domain false positives with `"for loop"` tutorial documents.

---

## 3. Substantive Relevance Filtering (`filter_substantive_relevance`)
Implemented deterministic query-aware relevance gating before context assembly in `backend/app/assistant_runtime/runtime.py`:
1. **Salient Keyword Extraction**:
   Extracts significant tokens from `user_query`, stripping English stopwords and common prepositions (`what`, `have`, `you`, `about`, `with`, `for`, `in`, `on`, `at`, `to`, `by`, `an`, `the`, `is`, `are`, `use`, `using`, etc.).
2. **Substantive Matching**:
   A candidate chunk is retained only if:
   - It possesses an exact lexical keyword match on salient terms in its content or document title; OR
   - Its semantic similarity is high (`>= 0.65`); OR
   - It is an explicitly requested web page or conversation attachment.
3. **Cross-Domain Isolation Verification**:
   - Query: `"Do you have knowledge of C++?"` -> Solar forecasting chunks have no C++ keyword match and low semantic score -> **Discarded**. Only C++ documents pass.
   - Query: `"Which model should I use next for solar irradiance forecasting?"` -> C++ tutorial chunks have no solar keywords -> **Discarded**. Only solar research documents pass.

---

## 4. Test Evidence
- `test_filter_substantive_relevance_cpp_query_rejects_solar_paper`: PASSED
- `test_filter_substantive_relevance_solar_query_rejects_cpp_chunks`: PASSED
