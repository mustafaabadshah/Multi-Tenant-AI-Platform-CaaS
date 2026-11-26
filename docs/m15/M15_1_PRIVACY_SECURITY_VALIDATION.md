# M15.1 — Privacy, Security & Redaction Validation

## 1. Privacy Architecture: Secure by Default

The platform strictly implements a **zero-trust preview policy**:

1. **Default Mode:** `METADATA_ONLY` is the strict system default.
   - Initial workspace creation: defaults to `METADATA_ONLY`.
   - Missing or unconfigured tenant policy: falls back to `METADATA_ONLY`.
   - In `METADATA_ONLY` mode, `input_preview` and `output_preview` are stored as `None`, and `has_preview` is `False`.
2. **Opt-in Redacted Previews:**
   - Previews are only captured if a workspace Owner or Administrator explicitly sets `capture_mode="REDACTED_PREVIEW"`.
   - Bounded by `max_preview_length` (default: 250 characters; configurable between 50 and 2000).
   - Previews are **sanitized before persistence** in `tracer.set_previews()`. Truncation occurs after scrubbing so secrets near boundaries are never exposed.

---

## 2. Redaction Test Matrix Across Synthetic Secret Formats

Tested via `backend/tests/test_observability_hardening.py::test_comprehensive_synthetic_secret_redaction`:

| Secret Category | Synthetic Test Pattern | Redaction Output | Verified Status |
|---|---|---|---|
| **OpenAI API Key** | `sk-abcdef1234567890abcdef` | `[REDACTED_API_KEY]` | PASSED |
| **Anthropic API Key** | `sk-ant-api03-abcdef1234567890abcdef-ZZ` | `[REDACTED_API_KEY]` | PASSED |
| **Render API Key** | `rnd_1234567890abcdef` | `[REDACTED_API_KEY]` | PASSED |
| **Backblaze B2 Application Key** | `K001234567890123456789012` | `[REDACTED_B2_KEY]` | PASSED |
| **Platform Token** | `mmaip_live_abcdef1234567890` | `[REDACTED_API_KEY]` | PASSED |
| **JWT Access Token** | `eyJhbGciOiJIUzI1NiIsIn...` | `[REDACTED_JWT_TOKEN]` | PASSED |
| **Bearer Header** | `Bearer my-super-secret-oauth-token-12345678` | `Bearer [REDACTED_TOKEN]` | PASSED |
| **Authorization Header** | `Authorization: Bearer my-secret-token` | `Authorization: Bearer [REDACTED_AUTH]` | PASSED |
| **JSON Credentials** | `{"password": "super_secret_db_password_123"}` | `{"password": "[REDACTED]"}` | PASSED |
| **YAML / Env Key-Value** | `password: production_yaml_pass_999` | `password: [REDACTED]` | PASSED |
| **Private Key PEM Block** | `-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----` | `[REDACTED_PRIVATE_KEY]` | PASSED |
| **Database URL with Credentials** | `postgresql://neondb_owner:npg_s3cr3tP4ssw0rd@ep-cool-fog.neon.tech/neondb` | `postgresql://neondb_owner:[REDACTED_DB_CREDENTIALS]@ep-cool-fog.neon.tech` | PASSED |
| **Unicode & Multiline Secrets** | `パスワード password=s3cr3t_utf8_鍵 and key=sk-utf8secret123456` | `パスワード password=[REDACTED] and key=[REDACTED_API_KEY]` | PASSED |
| **Boundary Truncation** | 190 'A's + `password=my_boundary_password_99999999999999` | `password=[REDACTED] ... [truncated]` | PASSED |
| **XSS Injection** | `<script>alert('xss')</script>` | `[SCRUBBED_SCRIPT]` (and HTML-escaped) | PASSED |

---

## 3. Authorization & Role-Gated Inspection

### Multi-Tenant Isolation:
- Every query to `request_traces` includes `WHERE tenant_id == tenant_ctx.tenant.id`.
- Tenant A cannot access, query, or infer traces belonging to Tenant B (returns 404 Not Found on cross-tenant trace ID lookup).

### Role Separation:
1. **Unprivileged Member (`employee`):**
   - Lacks `usage:read` permission.
   - Endpoint responds with `HTTP 403 Forbidden`.
   - Verified via `test_non_admin_preview_masking_security`.
2. **Privileged Non-Admin (e.g., Member with `usage:read`):**
   - Permitted to view aggregate telemetry, latency metrics, and trace list.
   - In `backend/app/api/v1/observability.py`:
     ```python
     if not tenant_ctx.is_admin:
         item.input_preview = None
         item.output_preview = None
         item.has_preview = False
     ```
   - Raw user chat inputs and outputs are masked to `None`.
3. **Workspace Owner / Admin:**
   - Full access to inspection previews when `REDACTED_PREVIEW` is enabled.
   - Sole authority to change capture policy (`PUT /policy`) or trigger retention purge (`POST /purge`).
