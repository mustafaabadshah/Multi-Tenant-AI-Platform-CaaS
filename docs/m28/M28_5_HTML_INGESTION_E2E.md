# M28.5 HTML Ingestion End-to-End Pipeline & Verification

## 1. Pipeline Architecture

The document ingestion pipeline processes HTML documents through deterministic validation, extraction, chunking, and embedding stages:

```
[Document Upload or Reprocess]
              │
   (filename, content, mime)
              │
              ▼
  [ParserRegistry.resolve_parser]
  • Content magic sniffing (strips BOM, checks HTML signatures)
  • Extension check (.html, .htm)
  • Rejection of deceptive binaries (MZ, ELF, PDF, ZIP)
              │
              ▼
        [HTMLParser]
  • WebContentExtractor (Trafilatura + BeautifulSoup fallback)
  • Strips scripts, styles, analytics, ads, tracking
  • Preserves headings (H1-H6), code blocks, tables, lists
              │
              ▼
      [ExtractedDocument]
  • Extracted sections, pages, code snippets
              │
              ▼
     [Ingestion Limits]
  • Byte budget truncation (UTF-8 boundary preservation)
              │
              ▼
      [Chunking Service]
  • Paragraph-aware hierarchical chunking
              │
              ▼
  [Vectorstore / FTS Indexing]
              │
              ▼
 [Document Status: COMPLETED / READY]
  • metadata_json: {"detected_format": "HTML", "detected_mime": "text/html"}
```

## 2. Dual Case Compatibility Matrix

| Scenario | Input Filename | Declared / Stored MIME | Ingestion Dispatch Result | Final Status |
| :--- | :--- | :--- | :--- | :--- |
| **Case A (New Upload)** | `C___For_Loop.html` | `text/html` | Routed to `HTMLParser` via extension and MIME | `READY` / `COMPLETED` |
| **Case B (Existing Upload)** | `C___For_Loop.html` | `application/octet-stream` | Routed to `HTMLParser` via content sniffing & validated extension | `READY` / `COMPLETED` |
| **Case C (Unextended Blob)** | `unnamed_blob` | `application/octet-stream` | Routed to `HTMLParser` via HTML tag structure sniffing | `READY` / `COMPLETED` |
| **Case D (Deceptive Payload)**| `malicious.html` | `application/octet-stream` | Rejected with `UnsupportedFormatError` (MZ executable detected) | `FAILED` (no retries) |

## 3. End-to-End Integration Verification

The integration test suite (`backend/tests/test_m28_5_production_html_recovery.py`) executes this exact worker lifecycle with a synthetic 268,553-byte fixture:

- **Fixture Details:** Exactly 268,553 bytes, valid HTML5, containing analytics script tags, C++ code blocks, benchmark tables, and structured nested sections.
- **Worker Execution:** Uses `IngestionService.upload_document` followed by `IngestionService.execute_job`.
- **Verified Outcomes:**
  - Script tags (`trackPageView`) cleanly stripped.
  - Extracted text $> 500$ chars with code snippets preserved.
  - Chunk count $> 0$ with `page_number=None` (no false page 1 numbering for web/HTML).
  - Stored MIME remains `application/octet-stream` while `detected_format` records `HTML`.
