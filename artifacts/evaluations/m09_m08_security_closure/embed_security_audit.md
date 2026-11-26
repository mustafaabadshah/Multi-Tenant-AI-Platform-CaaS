# M08 Security Closure: Website Embed Widget Security Audit

**Milestone:** M09 — Stage 1 (M08 Security Closure)  
**Component:** `frontend/app/embed/[publicId]/page.tsx` & `backend/app/api/v1/public_chat.py`  
**Auditor:** Application Security Engineer & Principal Architect  

---

## 1. Iframe Sandboxing & Isolation Architecture

The website embed widget is delivered as an isolated iframe loaded from `/embed/[publicId]` via a lightweight loader script (`/api/v1/public/embed.js`).

### Security Boundaries Enforced
1. **Iframe Isolation:** The host page and the widget run in distinct execution contexts. The host page cannot inspect widget DOM memory, hijack chat streams, or access visitor session tokens stored in the widget's origin `localStorage`.
2. **Minimal Permissions:** The iframe is injected with strict, minimal sandbox permissions:
   ```html
   <iframe 
     src="https://platform.domain/embed/pub_..." 
     allow="clipboard-write"
     sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
     style="border: none; border-radius: 16px;">
   </iframe>
   ```
   Camera, microphone, geolocation, and payment access are completely prohibited.
3. **No Wildcard `postMessage`:** All cross-window communication between `embed.js` and the iframe validates `event.origin` against the configured backend URL. Wildcard dispatch (`postMessage('*')`) is prohibited to prevent malicious third-party scripts on the host page from eavesdropping on message contents.

---

## 2. Origin & Referer Validation Principles

### Critical Distinction: Origin is NOT Authentication
- HTTP `Origin` and `Referer` headers are browser-enforced security mechanisms designed to limit cross-site embedding.
- Non-browser HTTP clients (`curl`, Python `requests`, Postman) can spoof these headers arbitrarily.
- **Platform Policy:**
  - `Origin` and `Referer` filtering is used strictly as a **distribution restriction** for browser embeds to honor the tenant's `allowed_domains` configuration.
  - Programmatic developers who require authenticated backend integration must use **Developer API Keys** (`Bearer mmaip_live_...`), where authentication is cryptographically validated regardless of HTTP headers.

---

## 3. Preflight Checklist for Embed Deployment

Prior to allowing an assistant to be published or embedded:
1. System instructions must be non-empty.
2. Model must be explicitly selected and active in the capability registry.
3. At least one Knowledge Base must be attached.
4. `allowed_domains` must be explicitly defined (e.g. `["https://acme.corp"]` or `["*"]` for open access).
5. If `allowed_domains` excludes the request origin, the server rejects chat streaming with **HTTP 403 Forbidden**.
