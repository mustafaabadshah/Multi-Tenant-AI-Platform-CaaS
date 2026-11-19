# M28.10.1 — Full Citation Lifecycle & Relevance Filter Audit

## Scope & Audit Methodology

This audit evaluated the complete lifecycle of citations:
Retrieval candidate → Selected context chunk → Model citation marker `[N]` → Marker validation → Database persistence (`MessageCitation`) → API serialization → Frontend badge grouping (`groupCitationsBySource`) → Message reload.

---

## 1. Prime Isolation & Provenance Invariants

1. **Candidates vs Verified Citations:**
   - Vector retrieval candidates are strictly internal. The assistant runtime no longer emits candidate chunks to the client during retrieval.
   - Only chunks explicitly cited via `[N]` in the final generated text are retained and persisted as verified evidence.
2. **Anti-Hallucination on Generation Failure:**
   - When an LLM call fails, the database transaction aborts any pending citations, ensuring zero synthetic or unverified citations appear in the conversation history.
3. **No Fabricated Page Numbers or Bounding Boxes:**
   - Page numbers are only populated if `DocumentChunk.page_number` exists and is non-null.
   - Bounding boxes are only constructed if `chk.metadata_json["bounding_box"]` contains genuine extracted coordinates (`page`, `x`, `y`, `width`, `height`).
   - Defaulting to US-letter fake page 1 bounding boxes is completely eliminated.

---

## 2. Relevance Filtering Audit Results

Audited via `backend/tests/test_m28_10_1_citation_lifecycle.py` and `test_m28_10_runtime_citations_and_search.py`:

| Test Query | Target Corpus | Expected Behavior | Result |
|---|---|---|---|
| "Do you have knowledge of C++?" | Solar paper vs C++ manual | Discards solar paper, retains C++ | PASS |
| "Which solar forecasting model to evaluate?" | C++ reference vs Solar paper | Discards C++ reference, retains Solar | PASS |
| "Compare Bi-LSTM with LightGBM" | Paper mentions "bidirectional LSTM" | Acronym synonym expansion matches | PASS |
| "What is the RMSE baseline?" | Paper mentions "root mean squared error" | Acronym synonym expansion matches | PASS |
| "GHI prediction curves" | Paper mentions "solar irradiance" | Metric abbreviation matches domain | PASS |
| "Hello, good morning!" | Unrelated solar paper | Discards unreferenced background chunk | PASS |
| "Explain for loop in C++" | C++ syntax with "for" vs Agriculture power | Retains C++ syntax, rejects power | PASS |
| Multiple chunks from same PDF | `Solar_Paper.pdf` (p. 2 & p. 5) | Both chunks preserved with unique IDs | PASS |

---

## 3. Backwards Compatibility & MessageCitation Reload

### Schema Analysis
The existing PostgreSQL/SQLite table `message_citations` contains:
- `id` (UUID)
- `message_id` (UUID)
- `chunk_id` (UUID, nullable)
- `document_name` (String(255))
- `citation_num` (Integer)
- `citation_text` (Text)

### Zero-Migration Reconstruction Strategy
1. **Document Citations (`chunk_id IS NOT NULL`):**
   - On reload, joins with `DocumentChunk` within the authenticated tenant scope.
   - Derives `actual_page = chk.page_number`.
   - Derives `bounding_box` from `chk.metadata_json.get("bounding_box")`.
   - Classifies `source_type = "document"`.
2. **Web Citations (`chunk_id IS NULL`):**
   - If `document_name` starts with `http://` or `https://`:
     - Classifies `source_type = "web"`.
     - Extracts `domain` using `urllib.parse.urlparse(web_url).hostname`.
   - Filenames with "http" in the middle (e.g. `http_protocol_rfc9110_spec.pdf`) having `chunk_id != None` are **not** misclassified as web citations.
3. **Verdict:**
   - **No Alembic migration required.** Existing database revision `0018_m28_message_feedback` remains 100% compatible. Historical citations reload cleanly with authentic document identities.
