# M08 Security Closure: Developer API Key Security Audit

**Milestone:** M09 — Stage 1 (M08 Security Closure)  
**Component:** `backend/app/services/api_key_service.py` & `backend/app/api/v1/developer.py`  
**Auditor:** Application Security Engineer & Principal Architect  

---

## 1. Cryptographic Key Management Lifecycle

```
[Key Generation]
 secrets.token_urlsafe(32) ──► raw_key = "mmaip_live_" + token (256 bits entropy)
                                    │
               ┌────────────────────┴────────────────────┐
               ▼                                         ▼
   Returned to Developer ONCE              SHA-256(raw_key.encode('utf-8'))
     (Never stored in DB)                                │
                                                         ▼
                                            Stored in api_keys.key_hash
```

### Cryptographic Properties
- **Key Prefix:** `mmaip_live_` enables automated secret scanning tools (GitHub Secret Scanning, TruffleHog) to identify leaked keys.
- **Entropy:** 32 cryptographically secure random bytes = 256 bits of entropy.
- **Storage:** Only the deterministic `SHA-256` hex digest is persisted. Even a full database dump yields zero plaintext developer keys.
- **One-Time Display:** The plaintext token is returned exclusively in the `APIKeyCreatedResponse` and is never retrievable again.

---

## 2. Granular Scoping & Resource-Level Permissions

### Expanded Scope Catalog (M09 Hardened)

| Scope | Allowed Operations | Endpoints Protected |
|---|---|---|
| `assistant:read` | Read assistant metadata, description, model, and capabilities. | `GET /api/v1/developer/assistants`, `GET /api/v1/developer/assistants/{id}` |
| `assistant:chat` | Stream chat completions with citations via SSE. | `POST /api/v1/developer/assistants/{id}/chat` |
| `assistant:eval` | Execute evaluation benchmarks programmatically. | `POST /api/v1/developer/assistants/{id}/evaluate` |
| `knowledge:read`| Query knowledge bases and document chunk metadata. | `GET /api/v1/developer/knowledge-bases` |

### Per-Key Assistant Scoping
In addition to global tenant scopes, keys now support an optional `assistant_id` parameter:
- **Tenant-Wide Key (`assistant_id = None`):** Can access any assistant within the tenant that matches granted scopes.
- **Restricted Key (`assistant_id = <UUID>`):** Access is strictly confined to that specific assistant. Requests targeting any other assistant return `403 Forbidden` (`"API key is restricted to assistant ..."`).

---

## 3. Negative Security Tests & Escalation Defenses

1. **Missing Key:** Returns `401 Unauthorized` (`WWW-Authenticate: Bearer`).
2. **Malformed Key Format:** Returns `401 Unauthorized` (`"Invalid API key format"`).
3. **Revoked Key:** Setting `api_key.is_active = False` causes immediate `401 Unauthorized` rejection.
4. **Expired Key:** Requests after `api_key.expires_at` return `401 Unauthorized` (`"API key has expired"`).
5. **Insufficient Scope:** A key with only `assistant:read` calling `POST .../chat` returns `403 Forbidden`.
6. **Cross-Tenant Key Usage:** A key generated in Tenant A attempting to access an assistant in Tenant B returns `404 Not Found` (never leaks existence).
7. **Wrong Restricted Assistant:** A key restricted to Assistant A attempting to invoke Assistant B returns `403 Forbidden`.
