# M28.4 Universal Web Reader & Multi-Format Dispatcher

## 1. Architectural Overview

The Web Reader service (`backend/app/services/web/reader.py`) functions as an intelligent dispatcher capable of fetching and parsing diverse internet resources while enforcing strict multi-tenant isolation, enterprise network safety, and accurate provenance.

## 2. Dispatch Pipeline

When an authenticated assistant or user initiates a `web_reader` tool call with a URL:

1. **SSRF & Network Boundary Validation:**
   - Validates URL schema (`http`, `https`).
   - Resolves target IP addresses and pins against RFC 1918 / RFC 4193 private ranges, loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`), and cloud metadata services (`169.254.169.254`).
   - Blocks internal hostnames (`localhost`, `*.internal`, etc.).

2. **HTTP Retrieval & Content Negotiation:**
   - Fetches target resource with 2MB ceiling, standard User-Agent header, and strict 10s socket timeout.
   - Inspects `Content-Type` response header and URL extension.

3. **Multi-Format Format Routing:**
   - **PDF Resource (`application/pdf` or `.pdf` extension):**
     Dispatched to `PDFParser().parse(content, filename=...)`.
     Returns page-structured text with `source_type="pdf"` and `ocr_derived` flag set if scanned pages underwent OCR.
   - **Raster Image Resource (`image/png`, `image/jpeg`, `image/webp`):**
     Dispatched to `ImageParser().parse(content, filename=...)`.
     Validates magic bytes, invokes `OCRService.extract_text()`, and returns `source_type="image"` with `ocr_derived=True`.
   - **Plain Text / Code (`text/plain`, `.txt`, `.md`, `.py`):**
     Decodes UTF-8 with fallback; returns `source_type="text"`.
   - **HTML Document (`text/html`):**
     Dispatched to `WebContentExtractor` (Trafilatura article extractor with BeautifulSoup fallback); returns cleaned body text, page title, and meta description with `source_type="html"`.

## 3. Data Contract & Provenance

The unified return structure from `read_webpage`:
```python
{
    "url": url,
    "title": page_title,
    "text": extracted_text,
    "word_count": len(extracted_text.split()),
    "source_type": "html" | "pdf" | "image" | "text",
    "ocr_derived": bool,
    "cached": bool,
    "status": "success"
}
```

This guarantees downstream agents receive uniform metadata regardless of whether the source URL pointed to an HTML blog, a research PDF, or a technical diagram.
