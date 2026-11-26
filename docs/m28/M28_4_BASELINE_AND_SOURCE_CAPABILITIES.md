# M28.4 Baseline and Source Capabilities

## 1. Executive Summary

Milestone M28.4 expands the Multi-Tenant AI Platform (CaaS) with Universal Web & Document Intelligence, selective CPU-friendly OCR, multi-mode Knowledge Base ingestion, accurate source provenance, and verified Voice Chat reliability. This document records the architectural baseline, source format matrix, resource constraints, and operational envelope established for M28.4.

## 2. Source Capability Matrix

The platform now natively supports the following input sources across both temporary "Read Now" conversation-scoped reading and persistent "Save to Knowledge Base" workflows:

| Source Category | Formats / MIME Types | Parser / Engine | OCR Behavior | Resource Caps |
| :--- | :--- | :--- | :--- | :--- |
| **Public Webpages** | `text/html`, `application/xhtml+xml` | `WebContentExtractor` (Trafilatura + BeautifulSoup fallback) | N/A | Max 2MB download, SSRF validation, DNS pinning |
| **Plain Text / Code** | `text/plain`, `text/markdown`, `.py`, `.js`, `.json`, etc. | `PlainTextParser` / Direct decode | N/A | Max 10MB file, 5MB web payload |
| **Standard PDF Documents** | `application/pdf` | `PDFParser` (pypdf text extraction) | None for digital text | Streaming page-by-page |
| **Scanned / Mixed PDFs** | `application/pdf` (pages with < 40 characters) | `PDFParser` + `OCRService` | Selective OCR on scanned pages only (`ocr_derived: True`) | Max 5 OCR pages per doc, 3000px cap |
| **Raster Images** | `image/png`, `image/jpeg`, `image/webp` | `ImageParser` + `OCRService` | Full image OCR (`ocr_derived: True`) | Max 3000px width/height, 25M pixel decompression bomb cap |
| **Structured Tables & Tutorials**| Markdown tables, HTML `<table>` | Structured text pipeline | Preserved markdown tables | Sanitized HTML, no inline script execution |

## 3. Computational Budget & Free-Tier Safety

All processing conforms to the platform's Free-Tier hosting profile (Render Free Backend 512MB RAM / 0.1 CPU, Neon PostgreSQL Free Tier):
- **CPU-Only Processing:** No CUDA or GPU runtime requirements.
- **Decompression Bomb Defense:** `PIL.Image.MAX_IMAGE_PIXELS = 25_000_000` enforced at module load.
- **Image Resizing / Downscaling:** Any image with dimension exceeding 3000px is downscaled with `LANCZOS` preserving aspect ratio before OCR execution.
- **Graceful Tesseract Degradation:** When Tesseract binary (`tesseract.exe` or `tesseract` on Linux) is absent, `OCRService` returns `success=False`, `error="OCR_UNAVAILABLE"`, without raising exceptions or breaking document ingestion pipelines.
- **Zero Paid APIs:** No external paid cognitive services, search APIs, or OCR clouds are called.
