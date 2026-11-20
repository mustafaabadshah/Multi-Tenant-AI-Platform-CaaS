# Provider & Credential Architecture — BYOK Vault & Gateway Management

**Document Purpose:** Detail the Bring-Your-Own-Key (BYOK) encrypted vault, provider lifecycle, and gateway integration rules.  

---

## 1. Provider Independence & Freedom of Choice

The platform is strictly **provider-agnostic** and operates on a **free-first, BYOK-first** philosophy:
- **No Mandatory Gateway:** OmniRoute is supported as an optional OpenAI-compatible local router, but is NOT the default provider or a required dependency. Direct provider integrations work standalone.
- **Direct Native Adapters:**
  - **Groq:** Ultra-low-latency open-weights inference (`llama-3.3-70b-versatile`, `llama-3.1-8b-instant`).
  - **Anthropic:** Claude Messages API (`claude-3-5-sonnet`, `claude-3-5-haiku`, `claude-3-opus`).
  - **Google Gemini:** Generative Language API (`gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-2.0-flash`).
  - **OpenAI:** Direct API client (`gpt-4o`, `gpt-4o-mini`, `o3-mini`).
  - **Mock:** Zero-network offline provider for local unit tests and development.

---

## 2. BYOK Encryption & Key Lifecycle

```
[Plaintext Secret Key: sk-...]
       │
       ▼
Fernet Symmetric Authenticated Encryption (AES-128-CBC + HMAC-SHA256)
Key derived from APP_SECRET_KEY / BYOK_ENCRYPTION_KEY
       │
       ▼
[Encrypted Blob: gAAAAAB...] ──► Stored in provider_credentials table
[Masked Key: sk-...3d4f]    ──► Returned across REST APIs
```

### Lifecycle Rules:
1. **Creation:** Tenant admin adds key; secret is encrypted immediately in memory before SQL insertion.
2. **Connection Testing:** In-memory verification verifies authentication against provider `/models` or `/chat` endpoint.
3. **Rotation:** Updating a secret encrypts the new secret, updates the masked preview, marks status `HEALTHY`, and retains audit logs.
4. **Revocation:** Marking a key `REVOKED` immediately causes `resolve_plaintext_key` to exclude it, blocking subsequent calls in 0ms.
5. **No Silent Fallback:** If an assistant requires a provider without an active BYOK key, the system returns a clear error (`"No valid BYOK credential configured for provider '{provider}'"`). Platform environment variables are never silently billed without explicit administrative configuration.
