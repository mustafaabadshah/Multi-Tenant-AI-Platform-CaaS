# M28.1 — Citation Grounding & Elimination of Cross-Topic Contamination (Problem C Fix)

## 1. Problem Statement
When asking an assistant a query about an external webpage (such as a C++ tutorial), the response previously returned citations to completely unrelated workspace documents (e.g. a solar irradiance PDF).

## 2. Root Cause Analysis
1. **Unfiltered Hybrid Vector Retrieval:** When an assistant has connected Knowledge Bases, the user's message is embedded and searched across all KB chunks. Words like "for", "loop", "read", "knowledge", and "syntax" matched random chunks from documents that happened to contain those terms.
2. **Missing Grounding Precedence:** If web page retrieval failed or was slow, only the low-scoring unrelated KB chunks were in `retrieved_results`, and `build_rag_context` assigned citations [1], [2] to those unrelated documents.
3. **Frontend Page Default:** The UI defaulted `page_number || 1`, showing `p.1` for all sources even when the source had no page number.

## 3. Engineering Fix
1. **Web Precedence & Grounding Filter (`backend/app/assistant_runtime/runtime.py`):**
   - When explicit web chunks are retrieved from an explicit URL preflight:
     - The explicit web chunk is placed at position 0 (`explicit_web_chunks`).
     - Connected KB chunks are strictly filtered to keep only high-relevance matches (`score >= 0.70`). Low-scoring peripheral chunks (e.g. solar PDF with score 0.48) are pruned before context assembly.
   - When an explicit web fetch fails:
     - Low-scoring peripheral KB chunks (`score < 0.75`) are discarded so unrelated documents are never cited for a failed web lookup.
2. **Provenance Preservation:**
   - Web citations explicitly preserve `source_type: "web"`, `source_url`, and `domain`.
   - Document citations preserve `source_type: "document"` and only display page numbers when `page_number != null`.
3. **Frontend Precision (`ConversationsWorkspacePage`):**
   - Replaced `p.{c.page_number || 1}` with conditional rendering `{!isWeb && c.page_number != null && <span>p.{c.page_number}</span>}`.
   - Clean badges distinguish web sources (emerald globe badge) from document sources (gray file badge).
