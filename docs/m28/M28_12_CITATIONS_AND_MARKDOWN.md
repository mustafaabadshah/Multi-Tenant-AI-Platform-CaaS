# M28.12 Citation Provenance & Markdown Code Presentation

## 1. Citation Provenance & Evidence Hardening

Following M28.10/M28.10.1 citation hardening standards, citations are subject to strict multi-tier verification before persisting or displaying in the Sources tray:

1. **Substantive Query Relevance (`filter_substantive_relevance`):**
   - General capability queries (*"Do you have knowledge of C++?"*) discard unrelated document domains (e.g. solar forecasting).
2. **Distinct Source Identities:**
   - **Uploaded Document Chunks:**
     - `source_type`: `document`
     - Displayed with verified document title, page numbers (`Page {N}`), and genuine bounding boxes when available.
   - **Academic Literature (arXiv Preprints):**
     - `source_type`: `web`
     - `domain`: `arxiv.org`
     - Displayed with preprint title, authors, publication date, and canonical HTTPS link.
     - Labeled as preprint abstracts to avoid false peer-reviewed claims.
3. **No Citations on Generation Failure:**
   - If stream generation fails or is aborted, `trace.citation_count` is zeroed, and no phantom citation records are saved to the database.
4. **Interactive Numeric Badge Attribution:**
   - LLM responses use bracket markers (`[1]`, `[2]`). Only sources actively cited in the generated answer are retained as verified citations.

---

## 2. Markdown & Code Block Presentation

### Diagnostic Findings from Test E
In live staging Test E (*"Read https://www.w3schools.com/cpp/cpp_for_loop.asp and explain the for-loop examples"*), code snippets were sometimes presented as plain text with a language prefix rather than proper syntax-highlighted blocks.

### Remediation Applied:

1. **System Prompt Directive (`backend/app/assistant_runtime/context.py`):**
   ```
   "- FORMATTING: Use clean, standard Markdown (headings, bold, bullet points, numbered lists, tables, and fenced code blocks). DO NOT escape Markdown syntax characters with backslashes (e.g. write **bold text**, never \\*\\*bold text\\*\\*). When providing programming code examples, ALWAYS enclose code in fenced code blocks with the language identifier (e.g. ```cpp ... ```), never plain text with a language prefix."
   ```

2. **Fenced Code Block Protection in Normalization (`markdown_normalizer.py`):**
   - Updated `code_fence_re` to preserve both fully closed and trailing streaming code blocks:
     ```python
     code_fence_re = re.compile(r"```[\s\S]*?(?:```|$)", re.MULTILINE)
     ```
   - Code blocks, line breaks, angle brackets (`#include <iostream>`), and indentation are 100% preserved.

3. **Frontend Rendering (`frontend/components/chat/MarkdownRenderer.tsx`):**
   - Flexible code fence parsing handles indented backticks (e.g. `   ```cpp`).
   - Integrated a sleek, accessible `CodeBlockView` with:
     - Header bar displaying language identifier (`cpp`, `python`, etc.).
     - One-click **Copy** button with `Copied!` feedback.
     - Overflow horizontal scrolling (`overflow-x-auto`).
     - Distinct dark monospace styling preserving indentation and line breaks.
