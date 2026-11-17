# M27.2 — Secure Outbound Web Page Reader & SSRF Protection

## 1. Overview & Architectural Boundaries

Outbound HTTP fetching from an enterprise AI platform exposes acute security risks if unrestricted. The most critical threats are **Server-Side Request Forgery (SSRF)**, cloud metadata credential exfiltration (`169.254.169.254`), private network reconnaissance (RFC1918), infinite redirect loops, and denial-of-service via oversized responses or decompression bombs.

To safely enable web intelligence without exposing raw network access to the LLM or frontend users, M27 implements a **first-party outbound web-reading pipeline**:
`WebFetchService` and `validate_web_url` in [ssrf.py](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/services/web/ssrf.py) and [reader.py](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/services/web/reader.py).

---

## 2. SSRF Defense-in-Depth Specification

Every outbound URL requested by an assistant or user is passed through strict pre-flight validation and connection-level destination checks:

| Security Invariant | Enforcement Mechanism | Failure Action |
|---|---|---|
| **Protocol Restriction** | Only `https://` is permitted in production (HTTP permitted only in explicit local test mode) | `SSRFSecurityError: Protocol is forbidden. Only HTTPS public URLs are permitted.` |
| **Credential Stripping** | URLs containing userinfo (`http://user:pass@host`) are explicitly rejected | `SSRFSecurityError: URLs containing embedded username or password credentials are forbidden.` |
| **Port Allowlist** | Only standard web ports (80, 443) are accepted; high ports (22, 25, 3306, 5432, 8080) blocked | `SSRFSecurityError: Port is not permitted. Only standard web ports (80, 443) are allowed.` |
| **Hostname Blacklist** | Direct rejection of `localhost`, `127.0.0.1`, `::1`, `0.0.0.0`, `metadata.google.internal`, `instance-data`, `169.254.169.254` | `SSRFSecurityError: Host is a restricted local or cloud metadata address.` |
| **IP Obfuscation Neutralization** | Rejection of decimal (e.g. `2130706433`), hex (`0x7f000001`), and octal representations | `SSRFSecurityError: Integer or hex encoded IP addresses are forbidden.` |
| **DNS Resolution Validation** | All IPv4 (A) and IPv6 (AAAA) records resolved via `socket.getaddrinfo` are checked | If **any** returned IP resolves to loopback, RFC1918 private, link-local, multicast, or reserved, request is blocked |
| **Cloud Metadata Protection** | Immediate rejection if resolved IP equals `169.254.169.254` | Prevents AWS, GCP, Azure, and DigitalOcean metadata credential harvesting |
| **Redirect Re-Validation** | Redirects are handled manually (up to max 3 hops); every single redirect target URL is re-validated through the full SSRF pipeline | Prevents redirect-based SSRF bypass |
| **Domain Allowlists** | Configured via `WEB_ALLOWED_DOMAINS` setting (if set) | Rejects URLs outside tenant/workspace domain whitelist |

---

## 3. Web Fetch Resource Limits (Render Free Safe)

| Parameter | Limit | Rationale |
|---|---|---|
| **Max Response Size** | 2 MiB (`2 * 1024 * 1024` bytes) | Prevents memory exhaustion on 512 MB Free tier Render instances |
| **Max Redirects** | 3 hops | Prevents infinite redirect chains and redirect cycles |
| **Connect Timeout** | 10.0 seconds | Prevents slowloris and hung sockets |
| **Read Timeout** | 15.0 seconds | Caps latency to maintain interactive conversational responsiveness |
| **User-Agent** | `MultiTenantAIPlatform-Bot/1.0 (+https://mmaip-backend.onrender.com; Educational AI Research)` | Polite, transparent identification complying with web standards |
| **TTL Cache** | 3600 seconds (1 hour) per tenant & URL | Prevents repeated external network roundtrips for conversational follow-ups |

---

## 4. Operational Status & Error Responses

The `WebFetchService` returns strongly typed `WebFetchResult` objects:

```python
{
    "canonical_url": "https://www.w3schools.com/cpp/cpp_for_loop.asp",
    "url": "https://www.w3schools.com/cpp/cpp_for_loop.asp",
    "domain": "www.w3schools.com",
    "hostname": "www.w3schools.com",
    "title": "C++ For Loop - W3Schools",
    "content": "When you know exactly how many times...",
    "status": "SUCCESS",  # Or "BLOCKED_SSRF", "UNAVAILABLE", "EMPTY"
    "http_status": 200,
    "content_type": "text/html; charset=utf-8",
    "retrieved_at": "2026-11-17T07:45:00.000Z",
    "cached": False,
}
```

If SSRF validation fails, the service fails closed with `status="BLOCKED_SSRF"` and an explanatory message. It never executes the request, never leaks internal network details, and never fabricates mock page text.
