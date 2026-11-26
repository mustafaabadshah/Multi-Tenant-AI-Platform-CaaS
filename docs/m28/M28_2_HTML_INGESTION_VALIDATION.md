# M28.2 HTML Ingestion & Knowledge Base Validation

## 1. Problem Statement
In historical operator testing:
- Uploading `C___For_Loop.html` (268,553 bytes) resulted in MIME `application/octet-stream`, 0 extracted characters, a `ValueError`, and a 3x retry storm because generic `ValueError` was not classified as permanent.
- Blank HTML or unsupported document formats wasted compute cycles with repeated retries.

## 2. Technical Remediation

### 2.1 HTML Parser & Content Sniffing
In `backend/app/parsers/html.py`:
- Built an `HTMLParser` using `BeautifulSoup` with `lxml`/`html.parser` fallback.
- Explicitly strips script, style, nav, footer, iframe, and noscript tags.
- Preserves structure: headers (`h1`-`h6`), paragraphs (`p`), lists (`ul`/`ol`/`li`), tables (`table`), and code blocks (`pre`, `code`).
- Extracts `<title>` for document metadata.
- If extracted text contains no meaningful characters, raises typed `UnparseableDocumentError`.

In `backend/app/parsers/registry.py`:
- Registered `HTMLParser` for `.html`, `.htm`, `text/html`, and content-based sniff signatures (`<!doctype html`, `<html`, `<head`, `<body`).
- Files uploaded as `application/octet-stream` containing HTML markup are reliably dispatched to `HTMLParser`.
- When an unknown format is encountered, raises typed `UnsupportedFormatError` rather than generic `ValueError`.

### 2.2 Ingestion Exception Hierarchy
In `backend/app/services/ingestion/limits.py`:
- Defined `UnsupportedFormatError(ValueError)` and `UnparseableDocumentError(ValueError)`.
- Added both to `PERMANENT_INGESTION_ERRORS = (..., UnsupportedFormatError, UnparseableDocumentError)`.
- In `IngestionService._handle_pipeline_failure()`, typed format/parse errors immediately transition the document job to `FAILED` with no retry storm.
- Generic `ValueError` exceptions caused by transient data issues remain eligible for retry recovery.

## 3. Test Verification
- `test_html_parser_extracts_clean_content_and_code`: Successfully parses complex HTML with C++ code blocks, retaining headers and code formatting.
- `test_parser_registry_resolves_html_with_octet_stream_mime`: Correctly resolves HTML parser when MIME is generic octet-stream.
- `test_ingestion_permanent_error_classification`: Validates typed errors belong to `PERMANENT_INGESTION_ERRORS` and inherit from `ValueError`.
- `test_empty_html_raises_permanent_value_error`: Confirms whitespace-only HTML raises `UnparseableDocumentError` without retry storms.

## 4. Gate Assessment
**HTML_KB_INGESTION = PASS**
HTML ingestion reliably parses complex markup, sniffs MIME, indexes searchable chunks, and fails unparseable documents permanently without retry storms.
