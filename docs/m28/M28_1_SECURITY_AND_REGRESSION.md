# M28.1 — Security & Regression Verification

## 1. Multi-Tenant Isolation & SSRF Security Boundaries
- **Tenant Scoping:** All database queries for attachments, assistants, knowledge bases, and feedback explicitly filter by `tenant_id == self.tenant_id`.
- **SSRF Policy:** Web URL reading enforces `validate_web_url()`:
  - Private IP subnets (RFC 1918, link-local, loopback 127.0.0.1, AWS/GCP metadata `169.254.169.254`) are blocked at DNS resolution.
  - Non-HTTP/HTTPS protocols (`file://`, `gopher://`, `ftp://`) are rejected.
  - Response size is capped at 10 MB and streaming timeout at 15s.
- **HTML Document Sanitization:** HTML parser strips all executable code, JavaScript `<script>` blocks, inline event handlers (`onload`, `onerror`), and avoids all local filesystem references or remote stylesheet fetching.

## 2. Regression Test Matrix
- **Problem B (HTML Ingestion):**
  - Standard HTML structure parsing: `PASS`
  - Octet-stream MIME with HTML content: `PASS`
  - Unparseable / empty HTML raising `ValueError`: `PASS`
  - `ValueError` classification as permanent non-retryable: `PASS`
- **Problem A (Web Reading):**
  - URL pattern extraction: `PASS`
  - Anti-refusal system prompt injection with `web_notice`: `PASS`
  - Web reading SSE events: `PASS`
- **Problem C (Citation Grounding):**
  - Unrelated low-scoring KB chunks pruned when explicit web URL retrieved: `PASS`
  - Provenance source type preserved without fake page 1 defaults: `PASS`
- **M28 Subsystems:**
  - Thumbs up/down message feedback API & telemetry: `PASS`
  - Admin feedback stream & status lifecycle: `PASS`
  - Quota service usage summaries: `PASS`
  - Beta operations cohort endpoints: `PASS`
  - Document parsers (PDF, DOCX, XLSX, PPTX, CSV, JSON, SQL, Markdown, TXT, HTML): `PASS`
