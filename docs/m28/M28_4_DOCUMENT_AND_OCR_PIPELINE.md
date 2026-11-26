# M28.4 Document & Selective OCR Pipeline

## 1. Selective OCR Architecture

The Document & OCR Pipeline integrates lightweight optical character recognition directly into document parsing workflows without degrading throughput or running out of memory on constrained container environments.

```
       [Uploaded File or Web Stream]
                     │
         Magic Byte / Extension Check
                     │
       ┌─────────────┴─────────────┐
       ▼                           ▼
  [PDF Parser]               [Image Parser]
       │                           │
  Page-by-page text           Image dimension check
  extraction (pypdf)          (< 3000px, 25M px limit)
       │                           │
  Is page scanned?                 ▼
  (chars < 40)              [OCRService.extract_text]
       │                           │
  ┌────┴────┐                      │
  ▼         ▼                      │
 [No]     [Yes]                    │
  │         │                      │
  │     OCR page                   │
  │     (max 5 pages/doc)          │
  │         │                      │
  └────┬────┘                      │
       ▼                           ▼
  Extracted Text              Extracted Text
  (ocr_derived: bool)         (ocr_derived: True)
```

## 2. Core Components

### 2.1 OCR Service (`backend/app/services/ocr_service.py`)
- **Tesseract Auto-Detection:** Queries system `PATH` and common platform paths (`/usr/bin/tesseract`, `/usr/local/bin/tesseract`, `C:\Program Files\Tesseract-OCR\tesseract.exe`).
- **Async Execution:** Wraps blocking pytesseract calls in `asyncio.to_thread` to maintain FastAPI event loop responsiveness.
- **Decompression Bomb Protection:** Sets `Image.MAX_IMAGE_PIXELS = 25_000_000`.
- **Downscaling:** Automatic resizing for images exceeding 3000px dimension using bilinear/lanczos resampling.
- **Graceful Fallback:** If Tesseract is unavailable, logs a warning and returns `success=False`, `error="OCR_UNAVAILABLE"` without raising unhandled exceptions.
- **Test Inversion Hook:** Provides `set_test_ocr_handler()` to enable deterministic unit and integration testing without requiring host Tesseract installations.

### 2.2 Image Parser (`backend/app/parsers/image.py`)
- Registered for MIME types: `image/png`, `image/jpeg`, `image/webp`.
- Extensions: `.png`, `.jpg`, `.jpeg`, `.webp`.
- Validates magic bytes (e.g., `\x89PNG`, `\xff\xd8\xff`, `RIFF...WEBP`) to block spoofed payloads.
- Extracts text via `OCRService` and marks document chunk metadata with `ocr_derived: True`.

### 2.3 Selective PDF OCR (`backend/app/parsers/pdf.py`)
- First attempts native digital text extraction via `pypdf`.
- If a page has fewer than 40 extracted characters, it is classified as a scanned page (`is_scanned = True`).
- Converts page to image and runs OCR only on scanned pages, with a strict safety cap of 5 scanned pages per document.
- Sets `ocr_derived: True` on the page chunk metadata, allowing downstream RAG context builders to display provenance indicators to users.
