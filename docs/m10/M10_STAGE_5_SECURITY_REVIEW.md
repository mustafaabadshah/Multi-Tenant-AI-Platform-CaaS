# Milestone M10 Stage 5 — Security Review & Vulnerability Audit

## 1. Executive Summary

Milestone M10 Stage 5 executes a rigorous security review across all platform layers of the **Multi-Tenant AI Platform (CaaS)**. This audit verifies adherence to the platform's prime directives: strict multi-tenant boundary isolation, cryptographic BYOK vault security, role-based access control (RBAC), and defenses against SSRF, credential enumeration, and data leakage.

---

## 2. Prime Directive: Multi-Tenant Isolation Enforcement

### 2.1 Identity & Context Binding
- **Never Trust Frontend Tenant IDs**: The platform strictly rejects tenant IDs supplied in request bodies or query parameters when asserting authority. Tenant scope is derived exclusively from the verified JWT payload (`active_tenant_id` claim) issued upon authenticated workspace selection.
- **Repository-Level Scoping**: Every database query on tenant-owned entities (Assistants, Knowledge Bases, Documents, Groups, Departments, Conversations, Traces) explicitly enforces:
  ```python
  stmt = select(Entity).where(
      Entity.id == entity_id,
      Entity.tenant_id == active_tenant_id,
  )
  ```
- **Relational Composite Foreign Keys**: Database tables utilize composite foreign keys `(tenant_id, parent_id)` to ensure an assistant or document cannot be cross-linked to a department or group belonging to another tenant.

### 2.2 Security Regression Suite Results
The security regression suite executes rigorous negative cross-tenant tests:
- **Cross-Tenant Document Read**: User in Tenant A attempts to read document metadata or download chunks belonging to Tenant B -> **Result: HTTP 404 Not Found (zero information disclosure)**.
- **Cross-Tenant Assistant Invocation**: User in Tenant A attempts to stream chat inference from private assistant belonging to Tenant B -> **Result: HTTP 404 Not Found**.
- **Cross-Tenant Provider Key Usage**: User in Tenant A attempts to reference a BYOK credential ID configured by Tenant B -> **Result: HTTP 404 Not Found**.
- **Cross-Tenant Role Escalation**: Member in Tenant A attempts to promote themselves or create an API key without admin scope -> **Result: HTTP 403 Forbidden**.

---

## 3. BYOK Credential Security & Encryption at Rest

### 3.1 Authenticated Fernet Vault Architecture
Provider credentials (Groq, Anthropic, Gemini, OpenAI, OmniRoute) entered through the Providers Studio are secured using authenticated Fernet encryption (`cryptography.fernet.Fernet`):
1. **Symmetric Encryption**: Plaintext keys are encrypted using a 256-bit AES cipher in CBC mode with PKCS7 padding and HMAC-SHA256 authentication.
2. **Key Storage**: The Fernet master key (`FERNET_SECRET_KEY`) is injected strictly via environment variables and never committed to source control or logged.
3. **Decryption Scope**: Decryption occurs strictly in-memory within the specific provider adapter module immediately prior to sending the outbound TLS request to the LLM gateway.
4. **Masked Secret Sanitization**: Pydantic serialization schemas explicitly omit plaintext keys. Frontend responses receive only `api_key_masked` (e.g. `gsk_...9aF2`), preventing secret leakage in browser devtools or HTTP traces.

### 3.2 Key Rotation Lifecycle
- Tenant administrators can rotate API keys at any time through the UI or API (`POST /api/v1/providers/credentials/{id}/rotate`).
- Upon rotation, the old ciphertext is overwritten with freshly encrypted ciphertext under the active master key, updating dependent assistant runtimes without downtime.

---

## 4. Ingestion Web Crawler & SSRF Defenses

The Knowledge Base web crawler accepts URLs for document ingestion. To prevent Server-Side Request Forgery (SSRF) into internal VPC resources or cloud metadata services, all requested URLs undergo pre-flight IP resolution and validation:
- **Loopback Blocking**: Resolving to `127.0.0.1`, `localhost`, `::1` is blocked.
- **Private RFC 1918 Blocking**: Resolving to `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` is blocked.
- **Cloud Metadata Blocking**: Resolving to `169.254.169.254` (AWS/GCP/Azure instance metadata service) is immediately rejected with a security violation alert.
- **Protocol Restriction**: Only `http://` and `https://` schemes are permitted; `file://`, `gopher://`, `ftp://` are rejected.

---

## 5. Password & Session Security

- **Argon2id Password Hashing**: User authentication relies on Argon2id (the winner of the Password Hashing Competition) with strict memory cost (64 MB), time cost (3 iterations), and parallelism (4 threads), providing resilience against GPU and ASIC brute-force attacks.
- **JWT Lifetimes & Rotation**:
  - Access Token: Short-lived (15 minutes), signed with HS256/RS256.
  - Refresh Token: Long-lived (7 days), stored in HTTP-only, SameSite=Lax secure cookies.
  - Revocation: Workspace context switches invalidate prior tenant session tokens.

---

## 6. Security Audit Verdict

The platform architecture satisfies all enterprise SaaS multi-tenant isolation, cryptographic protection, and least-privilege access criteria. All negative security test cases pass without regressions.
