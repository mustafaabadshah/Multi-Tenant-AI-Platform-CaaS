# M28.10 — Citation Integrity & Spatial Provenance

## 1. Separation of Three Critical RAG Concepts
To eliminate citation pollution and ungrounded badge display, M28.10 enforces strict boundaries between:
1. **Retrieved Candidates**: Chunks discovered across authorized knowledge bases and vector stores.
2. **Context Sources**: Candidates selected and bounded into `<KNOWLEDGE_BASE_CONTEXT>` for LLM generation.
3. **Cited Evidence**: Verified sources explicitly referenced via `[N]` citation markers or document identifiers in `final_content`.

---

## 2. Removal of Premature Citation Exposure
Previously, `runtime.py` emitted `citations: citations_data` in the `retrieval_complete` SSE event before generation even began. If generation crashed or if the LLM produced a general answer without using the retrieved knowledge, the frontend already had candidate badges rendered in the Sources tray.

**Remediation**:
- In `retrieval_complete`:
  ```json
  {"candidate_count": 4, "citation_count": 0, "citations": []}
  ```
  Unverified candidates are no longer exposed as evidence.
- Verified citations are only emitted upon successful completion via the `citation` SSE event after parsing `final_content` for citation markers.
- If generation fails or raises an error, `streamingCitations` is reset to `[]`, and zero citations are persisted.

---

## 3. Strict Citation Evidence Verification
Upon completion of the text stream:
1. All citation markers `[N]` in `final_content` are identified.
2. Only items in `citations_data` whose `citation_num` matches an active marker are retained.
3. If no markers exist, the runtime checks if specific document titles are explicitly referenced. If neither markers nor titles exist (e.g. for conversational queries), citations are cleanly set to `[]`.
4. Only verified citations are persisted to `message_citations`.

---

## 4. Elimination of Synthesized Bounding Boxes & Guessed Page 1
Previously, `context.py` and `conversations.py` synthesized standard US Letter bounding boxes (`612 x 792 pt`, `slot * 85.0`) and defaulted `page_number` to 1 whenever spatial coordinates were missing.

**Remediation**:
- Removed all synthetic bounding box formulas in `context.py` and `conversations.py`.
- If genuine spatial coordinates are not present in `item.metadata["bounding_box"]`, `bounding_box` is stored and rendered as `None`.
- If `page_number` is unknown, it remains `None`, never defaulting to `1`.
- On message reload in `list_messages`, the router joins `DocumentChunk` by `chunk_id` to retrieve authentic `page_number` and authentic `metadata_json["bounding_box"]`, preserving tenant authorization boundaries.

---

## 5. Duplicate Source Grouping
When multiple passages from the same document are cited (e.g. chunks 1, 2, and 3 from `Solar_irradiance__TechScience.pdf`):
- Internal chunk identities are preserved.
- The frontend Sources tray (`frontend/lib/citations.ts` + `frontend/app/dashboard/conversations/page.tsx`) uses `groupCitationsBySource` to render a single consolidated badge:
  `[1, 2, 3] Solar_irradiance__TechScience.pdf (p.2, 5)`
- This prevents visual flooding and duplicate badge spam.
