# M15 Security & Privacy Specification — AI Telemetry & Preview Policy

| Field | Value |
|---|---|
| Milestone | M15 — Observability 2.0, AI Request Intelligence & Platform Reliability |
| Document | Privacy Protection, Redaction Architecture, and Role Gating |
| Standards | Defense-in-Depth, Multi-Tenant Scoping, Zero Default Secret Exposure |

---

## 1. Threat Model & Security Principles

Telemetry and observability systems are frequent targets for credential leakage, prompt injection, and cross-tenant data harvesting. M15 applies five core security boundaries:

1. **Zero Secret Default:** By default, user prompts and assistant completions are never stored in telemetry records.
2. **Tenant Scoping:** All telemetry queries, updates, and purge operations strictly scope to `tenant_id == active_tenant_id`. No cross-tenant trace enumeration is possible.
3. **Multi-Pass Redaction:** Redaction occurs at ingest time before persistence, catching API keys, JWT bearer tokens, passwords, and private certificates.
4. **Role-Gated Previews:** Even when `REDACTED_PREVIEW` is enabled, viewing preview text requires `TENANT_OWNER` or `ORG_ADMIN` roles. Regular employees and viewers receive masked null previews.
5. **No Cross-Resource ACL Bypass:** Navigating from a trace to a source document or chunk enforces the existing document authorization check. A trace viewer cannot read documents outside their department.

---

## 2. Redaction Architecture

### 2.1 Pattern Coverage

The `sanitize_preview()` function applies recursive multi-pattern scrubbing:

| Pattern Type | Detection Regex / Rule | Replacement |
|---|---|---|
| **OpenAI / BYOK API Keys** | `sk-[a-zA-Z0-9_\-]{8,}` | `[REDACTED_API_KEY]` |
| **Platform API Keys** | `mmaip_(live|test)_[a-zA-Z0-9_\-]{8,}` | `[REDACTED_API_KEY]` |
| **Bearer / JWT Tokens** | `Bearer\s+[a-zA-Z0-9_\-\.]{15,}` | `Bearer [REDACTED_TOKEN]` |
| **Generic Passwords / Secrets**| `(password\|secret\|token\|key)\s*[:=]\s*['"]?[^'"\s]+` | `$1=[REDACTED]` |
| **Private Keys** | `-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----` | `[REDACTED_PRIVATE_KEY]` |
| **HTML / Script Injection** | `<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>` | `[SCRUBBED_TAG]` |

### 2.2 Preview Bounds
- Previews are strictly truncated to `max_preview_length` (default 250 characters, configurable up to 500 characters).
- Long inputs or attempts to exhaust storage with giant payloads are clamped at insertion.

---

## 3. Error Sanitization & Category Taxonomy

Raw provider exceptions often include URLs with API keys in query parameters or internal infrastructure paths. In M15, all exceptions are categorized into standardized operational codes:

| Error Category Code | Trigger Condition | Tenant-Visible Description |
|---|---|---|
| `AUTH_ERROR` | Missing or invalid BYOK credential / JWT expired | Credential or permission validation failed. |
| `QUOTA_EXCEEDED` | Tenant token or request quota exceeded | Workspace usage quota exceeded for this period. |
| `RATE_LIMITED` | Provider 429 response | Model provider rate limit encountered. |
| `PROVIDER_UNAVAILABLE`| Provider 500/503 or DNS/connection failure | Upstream model provider temporarily unavailable. |
| `PROVIDER_TIMEOUT` | Provider response stream timed out | Model provider did not respond within timeout limit. |
| `INVALID_CONFIG` | Unsupported model or malformed parameters | Assistant configuration or model parameters invalid. |
| `CONTEXT_OVERFLOW` | Combined prompt + retrieval exceeds window | Request context exceeds maximum provider context window. |
| `RETRIEVAL_ERROR` | Vector store or FTS query exception | Knowledge retrieval query failed. |
| `CANCELLED_STREAM` | Client aborted SSE connection (`GeneratorExit`) | Request was cancelled by the client. |
| `EMPTY_RESPONSE` | Provider stream closed with zero content | Provider returned an empty response. |
| `INTERNAL_ERROR` | Unexpected backend runtime exception | An internal processing error occurred. |

Stack traces and internal environment variables are **never** stored in `request_traces.error_message`.
