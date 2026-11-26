# M28.1 — HTML Ingestion & Extraction Repair (Problem B Fix)

## 1. Problem Statement
Uploading an HTML document (`C___For_Loop.html`, size 268,553 bytes) failed during ingestion:
- Upload reported: `mime_type: application/octet-stream`
- Extraction reported: `0 characters extracted`, then `ValueError`
- Ingestion worker queued retry attempts: `attempt 1/3`, `attempt 2/3`, `attempt 3/3` before failing.

## 2. Root Cause Analysis
1. **Missing HTML Parser:** `ParserRegistry` in `app/parsers/registry.py` had parsers for PDF, DOCX, XLSX, PPTX, CSV, JSON, SQL, Markdown, and TXT, but completely lacked an `HTMLParser`.
2. **Missing MIME Extension Mapping:** `ext_to_mime` in `registry.py` did not map `.html` or `.htm`, causing `.html` files to default to generic `application/octet-stream`.
3. **Unnecessary Retries on Deterministic Errors:** `ValueError` was omitted from `PERMANENT_INGESTION_ERRORS` in `app/services/ingestion/limits.py`. The ingestion queue dispatcher treated unsupported format `ValueError` as an intermittent transient failure and executed 3 retry cycles.

## 3. Engineering Fix
1. **`HTMLParser` Implementation (`backend/app/parsers/html.py`):**
   - Implements `DocumentParser` interface supporting `.html` and `.htm`.
   - Uses `WebContentExtractor` for deterministic DOM sanitization and content extraction.
   - Extracts headings, structured sections, paragraphs, code blocks (`<pre><code>`), lists, and tables.
   - Completely strips `<script>`, `<style>`, navigation headers, footers, and advertisement blocks.
   - Emits structured `ExtractedDocument` with sections and page text.
   - Never executes JavaScript or makes external network calls during parsing.
2. **Registry Integration & MIME Sniffing (`app/parsers/registry.py`):**
   - Registered `HTMLParser()` in `ParserRegistry`.
   - Added `.html` and `.htm` mapping to `"text/html"` in `detect_mime_type`.
   - Implemented fallback content signature sniffing for files declared as `application/octet-stream` containing `<!doctype html` or `<html`.
3. **Permanent Error Classification (`app/services/ingestion/limits.py`):**
   - Added `ValueError` to `PERMANENT_INGESTION_ERRORS`.
   - Ingestion service immediately marks format errors and empty extractions as non-retryable failures, eliminating 3x retry storms.
4. **Frontend Support:**
   - Added `.html,.htm` to file input `accept` attribute in `ConversationsWorkspacePage`.
