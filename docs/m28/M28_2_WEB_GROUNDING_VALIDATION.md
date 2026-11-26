# M28.2 Web Grounding & Grounded Citations Validation

## 1. Problem Statement
When a user asked a question pointing to a specific webpage (e.g., "Read this webpage https://www.w3schools.com/cpp/cpp_for_loop.asp and explain the C++ for loop"), previous milestones suffered from two defects:
1. **Accidental Egress:** Code blocks and markdown blockquotes containing URLs triggered unneeded URL preflight fetches.
2. **Citation Contamination:** Unrelated Knowledge Base documents (e.g., Solar irradiance forecasting papers, HR policies) with lower scores were retrieved and mixed into the context window, causing irrelevant citations due to arbitrary score thresholds (0.70 / 0.75).

## 2. Technical Remediation

### 2.1 Sanitized Preflight Detection
In `backend/app/assistant_runtime/runtime.py`:
- Stripped multiline code blocks (```` ```...``` ````), inline code (`` `...` ``), and blockquotes (`> ...`) from user prompts before applying regex URL extraction.
- Validated that the prompt contains intent to read the URL or that a bare URL is provided.
- Avoids duplicate fetches if the LLM also invokes `web_read_url`.

### 2.2 Source-Aware Intent Grounding
In `backend/app/assistant_runtime/runtime.py`:
- Removed arbitrary numeric score cutoffs (which suffered from non-comparable vector vs lexical scales).
- Implemented intent-based source filtering:
  - If the user explicitly provided a webpage and asked a webpage-specific question (without asking for cross-document comparison), the runtime designates the retrieved webpage as the primary context and prunes unrelated Knowledge Base chunks.
  - If the user explicitly asks for comparison (e.g., "compare the webpage with my document"), both sources are preserved.

### 2.3 Citation Provenance & Anti-Refusal Safeguards
In `backend/app/assistant_runtime/context.py`:
- Web citations strictly include `url`, `title`, and retrieval timestamp.
- PDF documents strictly include page numbers when available; unknown pages are never falsified as page 1.
- Injected clear system notices instructing the model to ground answers in the supplied web context rather than asserting lack of internet access.

## 3. Test Verification
- `test_code_block_url_does_not_trigger_preflight`: URLs in backticks or code blocks are ignored.
- `test_citation_grounding_prunes_unrelated_pdf_chunks`: Asking about C++ loops with a webpage fixture completely prunes unrelated Solar/HR PDF chunks.
- `test_source_aware_grounding_retains_comparison_only_when_requested`: Preserves both sources when comparison intent is present; isolates webpage when single-source intent is detected.
- `test_build_rag_context_anti_refusal_notice`: Injects explicit grounding guidance to eliminate false refusal.

## 4. Gate Assessment
**WEB_GROUNDING_AND_CITATIONS = PASS**
Web context is deterministically extracted, grounded, and isolated from unrelated KB contamination.
