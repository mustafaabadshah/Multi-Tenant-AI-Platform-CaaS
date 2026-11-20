# M28.4 Security & Resource Validation

## 1. Prime Directive: Multi-Tenant Boundary Enforcement

All document and web intelligence capabilities strictly enforce tenant isolation:
1. **Tenant-Scoped Authorization:** Every interaction with a Knowledge Base checks that `knowledge_base.tenant_id == active_tenant_id`. Cross-tenant reads, saves, or searches are strictly rejected.
2. **Ephemeral Context Isolation:** Temporary conversation-scoped web reading stores fetched content in the active conversation session cache only. Other tenants or conversations cannot read cached web text.
3. **Database Constraints:** Composite foreign keys and explicit `WHERE tenant_id = :tenant_id` clauses prevent cross-tenant data leaks.

## 2. Web Reader Security & SSRF Defense

The universal reader integrates hardened SSRF protection:
- **Private IP Address Blocking:** Rejects `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `0.0.0.0/8`, `169.254.0.0/16`, `[::1]`.
- **Cloud Metadata Defense:** Blocks `169.254.169.254` (AWS/GCP/Azure metadata) and internal DNS hostnames (`metadata.google.internal`, `instance-data`).
- **Dangerous Scheme Blocking:** Rejects `file://`, `gopher://`, `ftp://`, `data:`, `javascript:`.
- **Payload Caps:** Enforces 2MB maximum content download ceiling with a 10s socket timeout.

## 3. Resource Bounds & Free-Tier Guardrails

To prevent denial-of-service (DoS) or out-of-memory (OOM) crashes on constrained compute instances:
- **Decompression Bomb Protection:** `PIL.Image.MAX_IMAGE_PIXELS = 25_000_000` prevents malicious decompression attacks.
- **Image Dimension Clamping:** Images exceeding 3,000px width or height are downsampled with `LANCZOS` resampling before OCR execution.
- **Scanned PDF Page Cap:** Selective OCR processes a maximum of 5 scanned pages per PDF document.
- **Graceful Tesseract Handling:** If Tesseract OCR binary is missing from the container, processing gracefully completes with `OCR_UNAVAILABLE` without crashing or throwing 500 errors.
- **No Paid APIs:** Zero third-party paid API consumption.
