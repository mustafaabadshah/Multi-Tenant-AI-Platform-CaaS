# M28.5 OCR Deployment & Runtime Environment Audit

## 1. Container & Packaging Verification

Milestone M28.4 introduced selective OCR capabilities (`OCRService`, `ImageParser`, scanned page detection in `PDFParser`). This audit evaluates the container packaging and runtime behavior on Render Free tier:

### 1.1 Backend Dockerfile Audit (`infrastructure/docker/backend.Dockerfile`)
The backend Docker image installs Tesseract OCR natively:
```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
```
- **Binary Installed:** `/usr/bin/tesseract`
- **Language Data:** `tesseract-ocr-eng` (English trained data package)
- **Container Footprint:** Adds $\sim 45\text{MB}$ uncompressed to the image, well within Render's build and image transfer limits.

### 1.2 Render Blueprint Configuration (`render.yaml`)
`render.yaml` points the backend service to the Docker runtime:
```yaml
  - type: web
    name: mmaip-backend
    runtime: docker
    plan: free
    dockerfilePath: infrastructure/docker/backend.Dockerfile
    dockerContext: backend
```

## 2. Resource Envelope & Free-Tier Guardrails

Render Free instances provide 512MB RAM and shared 0.1 CPU cores. To prevent OOM crashes or compute exhaustion:

| Guardrail | Value | Implementation Location | Purpose |
| :--- | :--- | :--- | :--- |
| **Max Image Dimension** | 3,000 px | `OCRService._preprocess_image` | Downscales large images with `LANCZOS` before OCR |
| **Decompression Bomb Limit** | 25,000,000 px | `PIL.Image.MAX_IMAGE_PIXELS` | Prevents malicious memory exhaustion bombs |
| **Scanned Pages Cap** | 5 pages/doc | `PDFParser.parse` | Limits PDF OCR to at most 5 scanned pages |
| **Execution Threading** | `asyncio.to_thread` | `OCRService.extract_text` | Prevents blocking the async event loop |
| **Graceful Fallback** | `OCR_UNAVAILABLE` | `OCRService.extract_text` | Returns non-fatal status if binary is missing |
| **Temporary File Cleanup** | In-memory `io.BytesIO` | `OCRService` | Zero persistent temp disk writes |

## 3. Graceful Degradation Test Evidence

When running in an environment without Tesseract (such as default local Windows without Tesseract in `PATH`), `OCRService` gracefully returns:
```python
{
    "success": False,
    "text": "",
    "pages": [],
    "error": "OCR_UNAVAILABLE",
    "ocr_provider": "tesseract",
    "pages_processed": 0
}
```
Normal digital PDF extraction and HTML extraction remain 100% operational regardless of OCR availability.
