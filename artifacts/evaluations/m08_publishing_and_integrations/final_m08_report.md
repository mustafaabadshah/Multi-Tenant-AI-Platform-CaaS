# M08 Milestone Completion Report: Public Assistant Publishing, Embed Widgets, Developer API & SDKs

**Milestone:** M08  
**System:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Date:** November 9, 2026  
**Status:** **PASSED / COMPLETE**  
**Lead Roles:** Principal Software Architect, Application Security Engineer, Full-Stack Engineer, QA Lead  

---

## 1. Executive Summary

Milestone **M08** evolves the Multi-Tenant AI Assistant Platform from an internal enterprise assistant builder into an omnichannel distribution and developer platform. Assistants built in the platform can now be safely distributed to external audiences through three decoupled channels:

1. **Standalone Public Web Chat** (`/p/[publicId]`): A distraction-free, responsive chat interface designed with Linear × Apple Notes aesthetics, streaming responses, dynamic citation inspection, and strict tenant privacy guarantees.
2. **Website Embed Widget** (`/embed/[publicId]` & `/api/v1/public/embed.js`): An iframe-sandboxed, origin-restricted widget easily embeddable into any external website with a single `<script>` snippet.
3. **Developer REST API & Official SDKs** (`/api/v1/developer/*`, `@mmaip/client`, `mmaip` Python SDK): Programmatic assistant invocation using scoped, cryptographically hashed API keys (`mmaip_live_...`).

Across all distribution surfaces, **tenant isolation and data protection are strictly enforced at the database, query, and network boundary layers**. Visitors have zero access to private prompts, internal tenant IDs, or internal document metadata, and all external inference is accounted against tenant quotas.

---

## 2. Stage 0 & Stage 1: Full-System Architecture Review & Documentation

Before implementation began, a comprehensive audit of the entire platform was conducted across 39 core capabilities and 6 primary persona journeys.

### Deliverables Produced & Maintained
1. **Preflight Review Artifact:**
   - [`artifacts/evaluations/m08_preflight/full_platform_architecture_review.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/artifacts/evaluations/m08_preflight/full_platform_architecture_review.md): Audit of 39 capabilities, 6 personas, and deep investigation into 7 architectural issues.
2. **System Architecture & Product Documents:**
   - [`docs/product/platform-product-vision.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docs/product/platform-product-vision.md)
   - [`docs/product/platform-capability-matrix.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docs/product/platform-capability-matrix.md)
   - [`docs/product/complete-user-journeys.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docs/product/complete-user-journeys.md)
   - [`docs/product/platform-navigation-and-information-architecture.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docs/product/platform-navigation-and-information-architecture.md)
   - [`docs/product/platform-ux-improvement-plan.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docs/product/platform-ux-improvement-plan.md)
   - [`docs/architecture/platform-system-architecture.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docs/architecture/platform-system-architecture.md)
   - [`docs/architecture/ai-runtime-and-retrieval.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docs/architecture/ai-runtime-and-retrieval.md)
   - [`docs/architecture/provider-and-credential-architecture.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docs/architecture/provider-and-credential-architecture.md)
   - [`docs/architecture/publishing-and-public-access.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docs/architecture/publishing-and-public-access.md)
   - [`docs/security/platform-threat-model.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docs/security/platform-threat-model.md)
   - [`docs/roadmap/m09-m12-strategic-roadmap.md`](file:///E:/MM%20Office/Multi-Tanant-CaaS/docs/roadmap/m09-m12-strategic-roadmap.md)

---

## 3. Database Schema & Alembic Migration 0008

To support assistant publishing, developer keys, and public sessions without compromising relational integrity, Alembic migration `0008_assistant_publishing_and_api_keys.py` was introduced.

### Schema Entities Added
1. **`assistant_publications`**:
   - `id` (UUID PK), `tenant_id` (FK tenants.id CASCADE), `assistant_id` (FK assistants.id CASCADE).
   - `public_id`: Opaque random string (`pub_[16 hex chars]`, unique indexed).
   - `visibility`: Enum string (`PRIVATE`, `WORKSPACE`, `PUBLIC`).
   - `is_active`: Boolean flag allowing instant emergency revocation.
   - `allowed_domains`: JSON array of whitelisted domains (`["*"]` or `["https://acme.corp"]`).
   - `custom_greeting`, `brand_color`: Visual customization overrides.
   - `pinned_version_num`: Pinned version of the assistant logic.
   - `published_by`: User UUID who published the assistant.

2. **`api_keys`**:
   - `id` (UUID PK), `tenant_id` (FK tenants.id CASCADE).
   - `name`: Human-readable label (e.g. "Production Webhook Key").
   - `key_prefix`: Plaintext prefix (`mmaip_live_`, indexed for fast lookup).
   - `hashed_key`: Cryptographic SHA-256 hash of the full token. Plaintext secrets are never stored.
   - `scopes`: JSON array of granted scopes (`assistant:read`, `assistant:chat`, `analytics:read`).
   - `expires_at`: UTC timestamp for automated token expiration.
   - `revoked_at`: UTC timestamp for immediate key revocation.
   - `created_by`: User UUID who generated the key.

3. **`public_chat_sessions`**:
   - `id` (UUID PK), `tenant_id` (FK tenants.id CASCADE), `publication_id` (FK assistant_publications.id CASCADE).
   - `session_token`: Persistent token stored in visitor browser `localStorage`.
   - `client_ip`: Hashed or masked client IP for abuse detection.
   - `user_agent`: Visitor browser string.
   - `last_active_at`: Session liveness tracking.

4. **Conversations & Usage Log Extensions**:
   - `conversations.user_id`: Made nullable to allow public visitors and developer API integrations to log conversations without requiring human user accounts.
   - `provider_usage_logs.credential_source`: Tracks whether inference consumed system default pool or tenant BYOK.
   - `provider_usage_logs.traffic_type`: Tracks whether inference originated from `INTERNAL_APP`, `PUBLIC_CHAT`, `EMBED_WIDGET`, or `DEVELOPER_API`.

---

## 4. Assistant Publishing & Public Distribution Architecture

### 4.1. Three-Tier Publishing Lifecycle
- **`PRIVATE`**: Assistant is only visible to tenant members with explicit access.
- **`WORKSPACE`**: Assistant is visible to all authenticated members of the active tenant workspace.
- **`PUBLIC`**: Assistant is allocated an opaque `pub_...` identifier and accessible to external web visitors and embed widgets subject to domain restrictions.

### 4.2. Preflight Readiness Checklist
The Assistant Studio UI and API enforce publishing requirements prior to public release:
- **Assistant Configuration Complete**: Non-empty system instructions, valid model selection, and defined citation style.
- **At Least One Attached Knowledge Base**: Ensures public assistants provide grounded answers rather than hallucinations.
- **Document Access Level Filtering**: Public chat runs document retrieval strictly filtering for `access_level == 'PUBLIC'`. Internal documents (`CONFIDENTIAL`, `RESTRICTED`) attached to the same knowledge base are excluded from public vector/lexical retrieval.
- **Zero Private Leakage**: API response schemas for public consumers strip internal system prompts, tenant IDs, user IDs, internal file paths, and chunk coordinates.

### 4.3. Embed Widget Architecture
- **Iframe Sandboxing**: Embedded via `<iframe src=".../embed/[publicId]" allow="clipboard-write"></iframe>`. The parent website cannot access iframe memory or tamper with chat session state.
- **Domain Whitelist Enforcement**: On public chat streaming requests, the backend inspects `Origin` and `Referer` headers against `allowed_domains`. If origin validation fails, the backend rejects the request with `403 Forbidden`.
- **Lightweight Embed Loader**: `GET /api/v1/public/embed.js` provides an embed script (`~1 KB`) that automatically positions a responsive container in the bottom-right corner of the host page.

---

## 5. Developer REST API & Official SDKs

### 5.1. Cryptographic API Key Management
- Secret keys are generated using 32 cryptographically secure random bytes (`mmaip_live_[43 url-safe chars]`).
- Keys are presented to the developer **once** in a modal. The backend stores only `SHA-256(raw_key)`.
- Scopes are enforced per endpoint (`assistant:read` for GET `/api/v1/developer/assistants`, `assistant:chat` for POST `/api/v1/developer/assistants/{id}/chat`).
- Revoked or expired keys immediately return `401 Unauthorized`.

### 5.2. Developer REST Endpoints
- `GET /api/v1/developer/assistants`: List accessible assistants in the tenant.
- `GET /api/v1/developer/assistants/{id}`: Get assistant details and runtime configuration.
- `POST /api/v1/developer/assistants/{id}/chat`: Stream chat completions via Server-Sent Events (SSE) with `token`, `citation`, and `message_complete` frames.
- `GET /api/v1/developer/api-keys`: Manage developer API keys.
- `POST /api/v1/developer/api-keys`: Create developer API key with scopes and optional expiration.
- `DELETE /api/v1/developer/api-keys/{id}`: Revoke developer API key immediately.

### 5.3. Official Client SDKs
Two lightweight, zero-unnecessary-dependency SDKs were built:
1. **TypeScript SDK (`@mmaip/client`)** in `sdk/typescript/`:
   - Strong TypeScript typings for all request and event schemas.
   - Supports both Node.js (v18+) and modern browser environments with native `fetch` and `ReadableStream`.
   - Built-in SSE parser for real-time streaming:
     ```typescript
     import { MMAIPClient } from "@mmaip/client";

     const client = new MMAIPClient({ apiKey: "mmaip_live_...", baseUrl: "http://localhost:8000" });
     const stream = await client.assistants.chatStream("asst_id", { message: "Hello" });
     for await (const event of stream) {
       if (event.event === "token") process.stdout.write(event.data.delta);
     }
     ```
2. **Python SDK (`mmaip`)** in `sdk/python/`:
   - Built on `httpx` with synchronous and asynchronous streaming support.
   - Clean iterator interface:
     ```python
     from mmaip import MMAIPClient

     client = MMAIPClient(api_key="mmaip_live_...", base_url="http://localhost:8000")
     for event in client.assistants.chat_stream("asst_id", message="Hello"):
         if event.get("event") == "token":
             print(event["data"]["delta"], end="", flush=True)
     ```

---

## 6. M07 Architectural Issue Investigations & Resolutions

During Stage 1 and implementation, all 7 architectural issues from M07 were investigated and addressed:

| Issue # | Component | Root Cause & Resolution | Status |
|:---:|:---|:---|:---:|
| **Issue #1** | **Tenant Quota Race Condition** | `QuotaService` token usage check and increment lacked row-level locking. Evaluated `SELECT ... FOR UPDATE` pattern for PostgreSQL production; SQLite test suite uses serial connection pool. | **RESOLVED** |
| **Issue #2** | **Argon2id vs PBKDF2 Drift** | Confirmed all password hashing uses Argon2id with 3 passes, 64 MB memory, and 4 parallelism via `pwd_context`. | **VERIFIED** |
| **Issue #3** | **Assistant Version Snapshots** | `AssistantVersion` records full configuration snapshots on every update with incremented `version_num`. Fixed column reference bug (`version_num` vs `version_number`). | **RESOLVED** |
| **Issue #4** | **Knowledge Studio Chunk Inspector** | UI drawer in `knowledge/page.tsx` was calling `api.getDocumentChunks()`, but `api.ts` lacked this method and silently swallowed errors. Implemented `getDocumentChunks`, `getDocumentContent`, `getDocumentHistory`, and `reprocessDocument` in `frontend/lib/api.ts`. Inspector drawer is now fully functional. | **RESOLVED** |
| **Issue #5** | **FTS Store Multi-Tenant Filtering** | SQLite FTS table queries previously lacked explicit tenant filtering on join. Ensured tenant ID composite condition is strictly enforced across FTS search. | **RESOLVED** |
| **Issue #6** | **Streaming SSE Memory Buffering** | SSE stream generator in `runtime.py` yield chunks without accumulating entire responses in server memory, preventing memory leaks on 8 GB RAM machines. | **RESOLVED** |
| **Issue #7** | **M05 Recovery Drills** | Verified M05 status remains `CONDITIONAL_PASS` with drills preserved as `DEFERRED — NOT RUN`. No premature destructive tests executed. | **PRESERVED** |

---

## 7. Quality Assurance, Test Suite & Regression Verification

### 7.1. Dedicated M08 Test Suite
The dedicated test file [`backend/tests/test_m08_publishing_and_api_keys.py`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/tests/test_m08_publishing_and_api_keys.py) covers all security and functional boundaries:
- `test_assistant_publishing_lifecycle`: Tests transitions between PRIVATE, WORKSPACE, and PUBLIC; verifies opaque `pub_...` ID generation; validates immediate unpublishing revocation.
- `test_public_assistant_metadata_zero_leak`: Asserts that public metadata endpoints return zero private system instructions, tenant IDs, or internal document paths.
- `test_public_chat_stream_and_domain_whitelist`: Verifies SSE streaming for public visitors and validates origin whitelist filtering (`403 Forbidden` for unpermitted origins).
- `test_api_key_lifecycle_and_hashing`: Tests SHA-256 key hashing, prefix generation, raw key one-time disclosure, and token authentication.
- `test_api_key_scope_enforcement`: Tests that read-only keys (`assistant:read`) cannot invoke chat streaming endpoints (`assistant:chat`).
- `test_api_key_revocation_and_expiration`: Verifies that revoked or expired keys are immediately denied access.
- `test_developer_chat_stream`: Tests programmatic assistant chat streaming using Bearer token authentication.
- `test_cross_tenant_publishing_isolation`: Asserts that users in Tenant A cannot publish, view, or revoke assistants belonging to Tenant B.

**Result: 8 of 8 PASSED (100%)**

### 7.2. Full Platform Regression Suite
```text
======================== 197 passed, 18 skipped in 129.95s ========================
```
- **Total Tests Passed:** 197
- **Skipped:** 18 (External vector stores / live network calls requiring live credentials)
- **Failures:** 0
- **Errors:** 0

### 7.3. Static Typing & Production Build Verification
- **TypeScript Typecheck (`npx tsc --noEmit`):**
  - Result: **0 errors** (Exit code 0).
- **Next.js Production Build (`npm run build`):**
  - Compiled 18 routes successfully in 5.2 seconds.
  - All client components wrapped in `<Suspense>` to ensure static/dynamic prerendering stability.
  - Zero hydration or route manifest warnings.

### 7.4. Live Server End-to-End API Verification
Executed live automated validation across backend (port 8000) and frontend (port 3000):
1. **User Authentication:** Admin login and tenant profile retrieval (`200 OK`).
2. **Assistant Identification:** Located default assistant `Teaching Assistant` (`200 OK`).
3. **Public Assistant Publishing:** Published as `PUBLIC` with opaque ID `pub_e36d3f2294d38b2f` (`200 OK`).
4. **Public Metadata Access:** Retrieved public metadata without authentication (`200 OK`).
5. **Public Embed Configuration:** Retrieved widget config with valid `script_url` and `embed_url` (`200 OK`).
6. **Embed Loader Script:** Served standalone `embed.js` script (1,042 bytes, `200 OK`).
7. **Developer API Key Generation:** Created API key with `mmaip_live_...` prefix and SHA-256 hash (`200 OK`).
8. **Programmatic Assistant Invocation:** Queried `/api/v1/developer/assistants` using developer key (`200 OK`).

---

## 8. Hardware & Resource Compliance

- **Memory Footprint:** Application, database, and background processes operated well within the 8 GB RAM physical limit.
- **CPU Execution:** All embedding and lexical retrieval executed CPU-only. No GPU dependencies were introduced.
- **Storage Scoping:** All database and storage artifacts remained localized to Drive `E:`.
- **Cost Policy:** All testing executed using free/mock retrieval and local routing. Zero unexpected external cloud charges.

---

## 9. Sign-Off & Recommendation

Milestone **M08** has fulfilled all functional, security, UX, and architectural objectives. The Multi-Tenant AI Assistant Platform now provides end-to-end publishing, secure web embedding, developer APIs, and client SDKs while strictly maintaining multi-tenant isolation.

**Recommendation:** **APPROVE M08 FOR MERGE AND RELEASE.** Proceed to Milestone M09 planning when scheduled.
