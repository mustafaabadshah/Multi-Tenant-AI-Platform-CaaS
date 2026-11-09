# Publishing and Public Access Architecture — M08 Specification

**Document Purpose:** Detail the publication data model, public chat endpoints, embed widget mechanics, and developer API authentication.  

---

## 1. Publishing Data Model & Relationships

```
┌─────────────────────────────────┐
│           Assistant             │
│ id: UUID                        │
│ tenant_id: UUID                 │
│ name: String                    │
└────────────────┬────────────────┘
                 │ 1:1
                 ▼
┌─────────────────────────────────┐
│     AssistantPublication        │
│ id: UUID                        │
│ tenant_id: UUID                 │
│ assistant_id: UUID (Unique)     │
│ public_id: String (Opaque UUID) │
│ visibility: PRIVATE |           │
│             WORKSPACE | PUBLIC  │
│ is_active: Boolean              │
│ allowed_domains: JSON/Array     │
│ custom_greeting: String         │
│ brand_color: String (#0284c7)   │
│ published_version_id: UUID      │
│ published_at: DateTime          │
└─────────────────────────────────┘
```

---

## 2. Public Chat & Embed Mechanics

### A. Public Web Chat Route (`/p/{publicId}`)
1. Visitor navigates to `https://platform.domain/p/{public_id}`.
2. Next.js server component fetches publication metadata via `GET /api/v1/public/assistants/{public_id}`.
3. If publication is inactive or visibility is not `PUBLIC`, returns 404/410.
4. Chat messages stream via `POST /api/v1/public/assistants/{public_id}/chat` using SSE.
5. Session state is managed via unguessable `session_id` stored in client `sessionStorage`.

### B. Embed Widget Iframe (`/embed/{publicId}`)
1. Host website embeds:
   ```html
   <script src="https://platform.domain/embed.js" data-assistant="{public_id}" async></script>
   ```
2. The script injects an isolated iframe pointing to `https://platform.domain/embed/{public_id}`.
3. The iframe communicates with host script via `postMessage` solely for expanding/collapsing the chat bubble.
4. Server validates `Origin` and `Referer` headers against `allowed_domains`.

---

## 3. Developer API & Scoped Authentication

1. **Authentication:** Bearer token in HTTP header:
   ```http
   Authorization: Bearer mmaip_sec_...
   ```
2. **Key Hashing:** Raw token `mmaip_sec_...` is generated once. The backend hashes it via `hashlib.sha256(raw_key.encode()).hexdigest()` and matches against `api_keys.key_hash`.
3. **Scope Enforcement:**
   - `assistant:read`: View assistant title, model, and metadata.
   - `assistant:chat`: Execute chat streaming invocations.
4. **Developer Endpoints:**
   - `GET /api/v1/developer/assistants`: List authorized assistants.
   - `POST /api/v1/developer/assistants/{assistant_id}/chat`: Stream chat tokens via SSE.
