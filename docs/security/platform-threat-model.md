# Platform Threat Model & Security Architecture

**Security Standard:** Enterprise Multi-Tenant Zero-Trust  
**Milestone:** M08 Comprehensive Threat Assessment  

---

## 1. Threat Vectors, Impact & Mitigations

| Threat Vector | Attack Mechanism | Impact | Architectural Mitigation |
|---|---|---|---|
| **Cross-Tenant Data Tampering** | Attacker modifies `tenant_id` in request body or passes Tenant B ID in URL. | High (Data breach) | All repository queries strictly scope `WHERE id = :id AND tenant_id = :active_tenant_id`. User membership in tenant is verified in JWT dependency. |
| **Public Knowledge Exfiltration** | Attacker prompts public assistant to reveal internal documents or employee PII. | High (Confidentiality loss) | 1. Only documents with `access_level="PUBLIC"` are searchable by public endpoints.<br>2. Tier 1 system guardrails enforce refusal on internal topics.<br>3. System prompts and internal IDs are stripped from public responses. |
| **API Key Secret Theft** | Attacker inspects database or logs to steal developer API keys. | High (Unauthorized inference) | Plaintext keys are never stored. Only SHA-256 hashes are persisted. Keys are masked in all logs and API responses. |
| **Resource Exhaustion & Quota Bypass** | Bot sends automated flood of requests to public assistant. | Medium (Denial of Service / Cost) | 1. Pre-invocation quota checks enforce monthly token limits.<br>2. IP-based rate limiting on public endpoints.<br>3. Immediate revocation switch deactivates endpoint in 0ms. |
| **Server-Side Request Forgery (SSRF)** | Attacker submits `http://169.254.169.254` or internal IP in URL Ingestion. | Critical (Cloud credential theft) | `url_ingestion.py` blocks RFC 1918, loopback, link-local, and cloud metadata. `follow_redirects=False` revalidates IP on every redirect hop. |
| **Prompt Injection Bypass** | Attacker embeds instructions inside an uploaded PDF to override guardrails. | Medium (Integrity compromise) | 4-tier prompt assembly encloses retrieved text inside XML data tags (`<context_document>`). Model is instructed that context contains untrusted data. |
| **Embed Domain Spoofing** | Attacker copies embed widget script to malicious site. | Low (Misuse of widget) | Backend validates `Origin` and `Referer` headers against publication's `allowed_domains`. Iframe isolation prevents host DOM tampering. |

---

## 2. Cryptographic Standards

- **Password Hashing:** Argon2id with random 16-byte salt, time cost 3, memory cost 64MB.
- **BYOK Encryption at Rest:** Fernet authenticated cryptography (AES-128-CBC + HMAC-SHA256).
- **API Key Hashes:** SHA-256 with constant-time comparison (`secrets.compare_digest`).
- **Session Tokens:** Cryptographically random 32-byte URL-safe strings (`secrets.token_urlsafe(32)`).
