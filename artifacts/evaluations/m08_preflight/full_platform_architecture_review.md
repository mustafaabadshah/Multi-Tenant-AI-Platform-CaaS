# Stage 1 Exit Gate: Full Platform Architecture Review & Preflight Assessment
**Milestone:** M08 — Public Assistant Publishing, Secure Embeds, Developer API, SDKs & Full-System Architecture Reassessment  
**Repository:** `mustafaabadshah/Multi-Tenant-AI-Platform-CaaS`  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Branch:** `main` | **Verified HEAD:** `ad46a440684bf749c45e799f127d229df8b7b4d7`  
**Date:** November 9, 2026  
**Auditor:** Principal Software Architect, Security Engineer & Product Lead  

---

## 1. Executive Summary & Exit Gate Decision

The Multi-Tenant AI Platform (Chatbot-as-a-Service / CaaS) has completed Milestones M01 through M07. Prior to implementing M08 (Public Assistant Publishing, Secure Embeds, Developer API, and SDKs), this full-system architectural review was conducted to evaluate platform coherence, security boundaries, tenant isolation, ordinary-user experience, and specific M07 reconciliation issues.

### Stage 1 Exit Gate Decision: **PROCEED TO M08 WITH TARGETED PREREQUISITES**
- **Data Integrity & Tenant Isolation:** VERIFIED. No cross-tenant data leaks or critical flaws found in core repository scoping.
- **Baseline Test Suite:** VERIFIED. 189 tests passed, 18 skipped, 0 failures.
- **Frontend Health:** VERIFIED. TypeScript clean (`0 errors`), 16 routes compiled cleanly via Next.js production build.
- **Specific M07 Issues:** Reconciled with concrete remediation actions detailed in Section 7.
- **M08 Architecture & Threat Model:** Formulated to enforce server-side public access boundaries, hashed API key secrets, and strict public/private knowledge separation.

---

## 2. Repository & Milestone Baseline Verification

| Verification Item | Expected Baseline | Actual Verified State | Evidence & Notes |
|---|---|---|---|
| **Git Branch** | `main` | `main` | `git branch --show-current` confirmed |
| **Git Commit HEAD** | `ad46a44` | `ad46a440684bf749c45e799f127d229df8b7b4d7` | Clean working tree; 35 files committed in M07 |
| **M06 Baseline Commit** | `9595339` | `95953392b7c85bc9170da587cd2e4e38575b5b0f` | Reconciled in `artifacts/evaluations/m07_preflight/` |
| **M05 Recovery Status** | `CONDITIONAL_PASS` | `CONDITIONAL_PASS` | Backup/restore & Qdrant rebuild drills remain `DEFERRED — NOT RUN` on local single-node dev |
| **Backend Test Suite** | 189 pass / 18 skip | **189 passed, 18 skipped, 0 failures** | Verified via `.venv\Scripts\pytest.exe -q` (188.43s) |
| **Frontend Compilation** | 0 errors | **0 errors (16 routes)** | `npx tsc --noEmit` & `npm run build` succeeded |
| **Alembic Migration Chain** | Head: 0007 | `0007_provider_credentials_and_usage` | Migrations 0001–0007 intact; next is `0008` |

---

## 3. Complete Platform Capability Inventory (39 Capabilities)

Each platform capability was inspected across the database schema, backend services, API endpoints, frontend interface, and test coverage, classified into the required standardized categories:

| # | Capability Area | Classification | User Value & Current Status | Evidence & Known Limitations | Recommended Action for M08/M09 |
|---|---|---|---|---|---|
| **1** | **Authentication** | `IMPLEMENTED_AND_VERIFIED` | Argon2id hashing, JWT bearer tokens, tenant membership resolution. | `/auth/login`, `/auth/me`, test coverage in `test_auth.py`. | Maintain as-is. |
| **2** | **Individuals & Organizations** | `IMPLEMENTED_AND_VERIFIED` | Solo individuals and enterprise multi-user organizations supported. | Tenant models, workspace switcher. | Ensure public publishing belongs to tenant. |
| **3** | **Workspaces** | `IMPLEMENTED_AND_VERIFIED` | Tenant-scoped data partitioning with `X-Tenant-ID` header validation. | Validated in all repository queries. | Maintain composite scoping. |
| **4** | **Departments & Groups** | `IMPLEMENTED_AND_VERIFIED` | Access control boundaries for employee groups and departments. | `administration.py`, ACL checks on document retrieval. | Retain department isolation during public checks. |
| **5** | **RBAC & Permissions** | `IMPLEMENTED_AND_VERIFIED` | Role hierarchy (Owner, Admin, Member, Viewer) with granular permissions. | `require_permission` dependency across all endpoints. | Add `ASSISTANT_PUBLISH` & `API_KEY_MANAGE` permissions. |
| **6** | **Assistant Templates** | `IMPLEMENTED_AND_VERIFIED` | 12 data-driven templates across education, business, personal, and domain. | `backend/app/templates/registry.py`. | Keep extensible; do not hardcode wizards. |
| **7** | **Assistant Creation** | `IMPLEMENTED_AND_VERIFIED` | 5-step guided wizard (Template -> Identity -> Knowledge -> Model -> Review). | `AssistantCreationWizard.tsx`, `POST /assistants`. | Add publishing step option post-creation. |
| **8** | **Assistant Configuration** | `IMPLEMENTED_AND_VERIFIED` | Dual Simple/Advanced modes modifying unified underlying schema. | `AssistantWorkspaceView.tsx`, tested in M06. | Add Publish tab in workspace. |
| **9** | **Prompt Trust Hierarchy** | `IMPLEMENTED_AND_VERIFIED` | 4-tier assembly isolating guardrails, assistant instructions, context, and input. | `prompt_assembly.py`, injection regression tests. | Enforce prompt isolation in public endpoints. |
| **10** | **Configuration Versioning** | `IMPLEMENTED_AND_VERIFIED` | Snapshotting each config change with forward-only rollback. | `AssistantVersion`, tested in `test_m06_assistant_studio.py`. | Bind publication to specific version. |
| **11** | **Conversations** | `IMPLEMENTED_AND_VERIFIED` | Persistent multi-turn dialogs scoped to tenant and assistant. | `Conversation`, `Message` tables. | Separate authenticated from public sessions. |
| **12** | **Chat Streaming** | `IMPLEMENTED_AND_VERIFIED` | Real-time SSE streaming (`message_start`, `token`, `citation`, `complete`). | `stream_chat` in `runtime.py`. | Reuse `stream_chat` for public & developer APIs. |
| **13** | **Citations** | `IMPLEMENTED_AND_VERIFIED` | Verified document snippets, page numbers, heading paths, and citation numbers. | `MessageCitation`, Markdown renderer. | Filter private citations in public chat. |
| **14** | **Document Ingestion** | `IMPLEMENTED_AND_VERIFIED` | Ingestion pipeline for PDF, DOCX, TXT, MD with status stages. | Ingestion job tracker, disk/storage providers. | Maintain file upload safety. |
| **15** | **OCR** | `PARTIALLY_IMPLEMENTED` | Tesseract OCR adapter with automatic text extraction fallback. | Graceful fallback if Tesseract binary missing. | Keep local CPU-friendly; do not require external OCR. |
| **16** | **Chunking Engine** | `IMPLEMENTED_AND_VERIFIED` | Sentence-boundary, fixed-size, and Markdown-structure chunkers. | `backend/app/chunking/`, token count tracking. | Maintain chunk provenance metadata. |
| **17** | **Chunk Inspection** | `PARTIALLY_IMPLEMENTED` | Detailed inspection of text chunks with index, token count, page number. | Backend API `GET /documents/{id}/chunks` verified; Knowledge UI missing drawer. | Add Chunk Inspector drawer in Knowledge UI. |
| **18** | **Embeddings** | `IMPLEMENTED_AND_VERIFIED` | FastEmbed CPU embeddings & OpenAI-compatible embeddings. | Tested in `test_embedding_providers.py`. | Preserve local CPU capability. |
| **19** | **Vector Stores** | `IMPLEMENTED_AND_VERIFIED` | PostgreSQL FTS, pgvector, and Qdrant vector store adapters. | Abstracted in `vectorstores/registry.py`. | Retain multi-store flexibility. |
| **20** | **Retrieval Engine** | `IMPLEMENTED_AND_VERIFIED` | Lexical (`ts_rank_cd`), Semantic, Hybrid (RRF), department filtering. | `retrieval/service.py`, tested in M04 & M07. | Ensure public retrieval enforces public KB check. |
| **21** | **Retrieval Playground** | `IMPLEMENTED_AND_VERIFIED` | Interactive query tester with score breakdowns, latency ms, ranks. | `POST /retrieval/playground`, verified in M07. | Keep in Knowledge Studio as advanced tool. |
| **22** | **URL Ingestion** | `IMPLEMENTED_AND_VERIFIED` | Safe web page fetcher with SSRF defense (RFC 1918, loopback, metadata). | `url_ingestion.py`, tested in `test_m07_knowledge_and_providers.py`. | Report DNS rebinding nuance honestly. |
| **23** | **Provider Registry** | `IMPLEMENTED_AND_VERIFIED` | 6 providers: Groq, Anthropic, Gemini, OpenAI, OmniRoute, Mock. | Catalog in `capabilities.py`. | Remove mandatory OmniRoute defaults. |
| **24** | **BYOK Vault** | `IMPLEMENTED_AND_VERIFIED` | Fernet encrypted key storage, masking, rotation, revocation. | `byok_vault.py`, tested in M07. | Make BYOK the standard credential path. |
| **25** | **Provider/Model Selection** | `IMPLEMENTED_AND_VERIFIED` | Dynamic model picker populated from capability registry. | Tested in M06/M07. | Ensure assistant stores valid provider/model. |
| **26** | **Usage Accounting** | `IMPLEMENTED_AND_VERIFIED` | Atomic token & request logging in `provider_usage_logs`. | Summary endpoints verified. | Add `credential_source` & `traffic_type` columns. |
| **27** | **Quota Enforcement** | `IMPLEMENTED_AND_VERIFIED` | Pre-invocation checks against daily requests & monthly tokens (HTTP 429). | `quota_service.py`, tested in M07. | Add publication-specific quota rate limits. |
| **28** | **Assistant Testing** | `IMPLEMENTED_AND_VERIFIED` | Live zero-persistence preview mode in Studio workspace. | `/preview` endpoint streaming tokens without DB writes. | Maintain zero-persistence in preview. |
| **29** | **Assistant Publishing** | `NOT_IMPLEMENTED` | Visibility control (Private, Workspace, Public), opaque public IDs. | Target M08 Feature A. | Implement in M08. |
| **30** | **Embed Integration** | `NOT_IMPLEMENTED` | Website embed widget with theme customization and allowed domains. | Target M08 Feature C. | Implement in M08. |
| **31** | **Developer APIs** | `NOT_IMPLEMENTED` | Scoped API credentials and versioned external endpoints. | Target M08 Feature E & F. | Implement in M08. |
| **32** | **SDKs** | `NOT_IMPLEMENTED` | Lightweight TypeScript & Python SDKs. | Target M08 Feature G. | Implement in M08. |
| **33** | **Audit Logging** | `IMPLEMENTED_AND_VERIFIED` | Immutable audit trail for administrative actions. | `AuditLog` table, `/audit` endpoints. | Audit publish, unpublish, and key revocation. |
| **34** | **Settings** | `IMPLEMENTED_AND_VERIFIED` | Tenant profile, member management, quota viewing. | Settings page in dashboard. | Add API Keys & Embed settings tab. |
| **35** | **Error Handling** | `IMPLEMENTED_AND_VERIFIED` | Structured HTTP exceptions with clear error messages. | Tested across test suites. | Standardize public API error contracts. |
| **36** | **Observability** | `PARTIALLY_IMPLEMENTED` | Structured logger, `/health` endpoint, timing metrics. | Advanced tracing & OpenTelemetry deferred to M09. | Keep lightweight; avoid extra daemons. |
| **37** | **Background Jobs** | `PARTIALLY_IMPLEMENTED` | In-process `asyncio.create_task` worker for document ingestion. | Celery/Redis queue deferred to M09. | Keep in-process for 8GB RAM constraint. |
| **38** | **Data Recovery** | `DEFERRED` | Postgres backup/restore & Qdrant snapshot scripts present. | Live recovery drills deferred (`CONDITIONAL_PASS`). | Maintain honest deferred status. |
| **39** | **Deployment Readiness** | `IMPLEMENTED_AND_VERIFIED` | Render & Vercel blueprints, production builds passing. | Tested in M05. | Maintain local test priority. |

---

## 4. Architecture Reassessment

### 4.1 Frontend Architecture
- **Structure:** Clean Next.js 16 App Router hierarchy under `frontend/app/`. Navigation is organized around `/dashboard/assistants`, `/dashboard/knowledge`, `/dashboard/providers`, `/dashboard/employees`, and `/dashboard/settings`.
- **Finding:** Currently, Assistant Studio, Knowledge Studio, and Provider Vault operate as distinct operational silos. When configuring an assistant, an ordinary user must first know to visit "Providers & Keys" to set up credentials, then "Knowledge" to upload files, and only then return to "Assistants".
- **Remediation for M08:** Maintain the **Linear × Apple Notes** design aesthetic. Inside `AssistantWorkspaceView.tsx`, integrate a clear **Readiness Checklist** and direct action links ("Configure Key", "Attach Knowledge", "Test Assistant", "Publish"). Add a dedicated **Publish Tab** allowing immediate configuration of Public Web Link, Embed Code, and Developer API snippets in one cohesive interface.

### 4.2 Backend Architecture (Modular Monolith)
- **Boundaries:** Clear separation across `api/v1/`, `services/`, `repositories/`, `models/`, and `llm/`. No microservices or RPC overhead.
- **Finding:** All LLM streaming logic is centralized in `backend/app/assistant_runtime/runtime.py`. This is an architectural strength.
- **Architectural Directive for M08:** The public chat endpoint, embed widget endpoint, and developer API MUST ALL call the single underlying `AssistantRuntime.stream_chat()` pipeline. There will NOT be separate public inference implementations. Public authorization and quota throttling will wrap the runtime call.

### 4.3 Data Architecture & Scoping
- **Integrity:** `TenantScopedMixin` enforces `tenant_id` on all entities.
- **Finding:** The migration sequence is currently at revision `0007_provider_credentials_and_usage`.
- **Database Plan for M08:** Add forward migration `0008_assistant_publishing_and_api_keys.py`:
  1. `assistant_publications` table: Stores public UUID slug, visibility (`PRIVATE`, `WORKSPACE`, `PUBLIC`), published configuration version ID, allowed domains, custom greeting, and active status.
  2. `api_keys` table: Stores SHA-256 hashed secret key, key prefix (`mmaip_...`), name, scopes (`assistant:read`, `assistant:chat`), expiration timestamp, and revocation status.
  3. `public_chat_sessions` table: Unguessable session identifiers for public and embed chat visitors with expiration and rate limiting.
  4. Extend `provider_usage_logs` with `credential_source` (`byok`, `platform_funded`) and `traffic_type` (`internal`, `public`, `developer_api`).

### 4.4 AI/RAG Architecture & Trust Boundaries
- **Pipeline:** Document Upload -> Text Extraction -> Normalization -> Chunking -> Vector Indexing -> Authorized Retrieval -> 4-Tier Context Assembly -> Provider Ingestion -> Streaming SSE Response.
- **Critical Security Finding for M08 Public Assistants:** If an assistant is connected to a Knowledge Base containing internal corporate policies, making the assistant "Public" could inadvertently expose internal documents via RAG.
- **Remediation Rule:** Knowledge bases connected to a published assistant must be explicitly flagged as `is_public_eligible=True` or confirmed during the publish review step. The retrieval authorizer will enforce that public callers cannot retrieve chunks from documents marked `access_level != "PUBLIC"`.

---

## 5. Security Architecture & Threat Model for M08

| Threat Vector | Attack Scenario | Defense Implementation in M08 |
|---|---|---|
| **Public Knowledge Exfiltration** | Attacker prompts a public assistant to dump private employee salaries or credentials. | 1. Retrieval authorizer enforces public-only chunks.<br>2. Tier 1 system guardrails enforce citation boundaries.<br>3. Internal system prompts and tenant metadata are stripped from public responses. |
| **API Key Secret Theft** | Database compromise or employee shoulder-surfing reveals plain developer API keys. | 1. Secrets are generated cryptographically (`secrets.token_urlsafe(32)`).<br>2. Full key is shown ONCE to user upon creation.<br>3. Database stores ONLY the SHA-256 hash.<br>4. Authentication checks `hashlib.sha256(provided_key).hexdigest()`. |
| **Public Endpoint Flooding & DoS** | Malicious bot sends 50,000 queries to `/p/{public_id}/chat` to exhaust tenant token quota. | 1. In-memory & DB rate limiter per IP / session (e.g. 20 requests/min).<br>2. Publication-level daily request and token ceilings.<br>3. Immediate revocation switch deactivates public endpoint in 0ms. |
| **Embed Origin Spoofing** | Attacker copies embed snippet and mounts it on a phishing website `phishingsite.com`. | 1. Server validates `Origin` and `Referer` headers against configured allowed domains.<br>2. Clear disclaimer: Origin headers protect browser contexts; backend quotas protect server resources.<br>3. Iframe sandbox attributes restrict host DOM interference. |
| **Public Session Enumeration (IDOR)** | Attacker guesses sequential conversation IDs (`?conv=1`, `?conv=2`) to read other visitors' chats. | 1. Session IDs are cryptographically random UUIDv4.<br>2. Public sessions are isolated in `public_chat_sessions` and tied to a unique session token.<br>3. Visitors cannot query or list other session histories. |

---

## 6. UX Persona Journey Evaluations

### Persona 1: Student (Personal Study & Exam Prep)
- **Goal:** Upload lecture PDF notes, create "Biology Exam Prep" assistant, test knowledge, get a shareable link.
- **Current Friction:** Needs to know what "RRF Constant" or "pgvector" means if looking at advanced settings; needs an easy 1-click way to test and share.
- **M08 Improvement:** Simple mode defaults to balanced settings. "Share Link" provides a clean, mobile-friendly `/p/{public_id}` web page where the student can quiz themselves or share with classmates without requiring them to create platform accounts.

### Persona 2: Teacher / Professor (MCQ & Exam Generation)
- **Goal:** Create an assistant from course syllabus to generate multiple-choice questions with strict citation grounding.
- **Current Friction:** Needs assurance that generated MCQs do not hallucinate outside the provided textbook.
- **M08 Improvement:** Template "MCQ & Exam Generator" with strict citation verification. Publish modal allows restricting access to "Workspace Members" (students enrolled in the tenant).

### Persona 3: Company Administrator (Internal HR Handbook)
- **Goal:** Create employee policy assistant accessible to all staff, restricted from external internet access.
- **Current Friction:** Fears that publishing an assistant makes it public to the world.
- **M08 Improvement:** Clear publishing visibility options:
  - **Private** (Only creator & admins)
  - **Workspace** (Authenticated members of the organization)
  - **Public** (Open to external web / embed)
  Explicit confirmation step with visual badge indicators.

### Persona 4: Customer Support Lead (External Website Assistant)
- **Goal:** Ingest company help desk articles, test accuracy in Playground, embed widget onto `https://company.com/support`.
- **Current Friction:** Cannot currently embed or publish; must keep assistant inside dashboard.
- **M08 Improvement:** Embed Widget generator providing a drop-in `<script>` or `<iframe>` snippet with domain restriction to `company.com` and custom brand color.

### Persona 5: Professional Researcher (Source Grounding & Chunk Provenance)
- **Goal:** Upload whitepapers, inspect chunks to verify equations and citations are preserved, test retrieval accuracy.
- **Current Friction:** Backend has `/chunks` endpoint, but Knowledge UI lacked the drawer to inspect chunk boundaries visually.
- **M08 Improvement:** Add Chunk Inspector drawer in Knowledge Studio.

### Persona 6: Software Developer (API Integration)
- **Goal:** Generate API key, call assistant from Next.js or Python backend, stream responses into existing product.
- **Current Friction:** No developer API or SDK exists in M07.
- **M08 Improvement:** Developer API key management with granular scopes, documented `/api/v1/developer/` endpoints, and lightweight official TypeScript & Python SDKs.

---

## 7. Investigation of Specific M07 Issues

### 7.1 OmniRoute Conflict & Gateway Independence
- **Investigation:** Found multiple references defaulting `llm_provider` to `"omniroute"` (e.g. `runtime.py`, `assistant.py`, `registry.py`, `config.py`), pointing to `localhost:20128`.
- **Resolution for M08:**
  1. Direct provider integrations (Groq, Anthropic, Gemini, OpenAI) must operate 100% standalone via direct BYOK credentials.
  2. OmniRoute is classified as an **optional** OpenAI-compatible gateway adapter, NOT the mandatory default.
  3. Default provider in new assistants should be the tenant's configured default BYOK provider or `mock` during offline development.
  4. No silent routing through OmniRoute; no automatic paid fallback.

### 7.2 Model Catalog Accuracy
- **Investigation:** The capabilities matrix lists models across 6 providers.
- **Resolution for M08:** Model capabilities in `backend/app/llm/capabilities.py` are explicitly documented as capability metadata (context window, tool support, vision). Provider adapters communicate via standard API endpoints without hardcoding ephemeral tier assumptions.

### 7.3 Platform API-Key Fallback & Expenditure Guard
- **Investigation:** In `byok_vault.py` and `openai_provider.py`, if a BYOK key is missing, code could look for platform environment variables (`OPENAI_API_KEY`).
- **Resolution for M08:**
  1. BYOK is the primary, standard credential path.
  2. If an assistant uses a provider without a valid BYOK key and no tenant default exists, the system will return a clear, actionable error: `"No valid BYOK credential configured for provider '{provider}'."`
  3. Platform environment keys are treated strictly as an explicit administrative opt-in policy, never a silent fallback.
  4. Every provider invocation records `credential_source="byok"` vs `credential_source="platform_funded"`.

### 7.4 Chunk Inspector Completeness
- **Investigation:** Backend endpoint `GET /api/v1/documents/{document_id}/chunks` was fully implemented and tested, but the frontend Knowledge Studio page did not provide a drawer/modal to inspect them.
- **Resolution for M08:** Add the Chunk Inspector drawer in `frontend/app/dashboard/knowledge/page.tsx`, allowing users to click any document and view chunk boundaries, token lengths, page numbers, and headings.

### 7.5 Retrieval Score Correctness & Mislabeled Algorithms
- **Investigation:** Lexical retrieval uses PostgreSQL native `ts_rank_cd` (Cover Density ranking), and hybrid retrieval uses Reciprocal Rank Fusion ($RRF = \sum \frac{1}{k + rank}$).
- **Resolution for M08:** Documentation and UI explicitly designate `ts_rank_cd` as PostgreSQL lexical rank (NOT BM25, which requires third-party C extensions). RRF scores and latency measurements remain truthful without manufactured metrics.

### 7.6 URL Ingestion Security & DNS Rebinding Nuance
- **Investigation:** `url_ingestion.py` pre-validates resolved IPs against RFC 1918, loopback, and cloud metadata (`169.254.169.254`), and enforces `follow_redirects=False` with per-hop revalidation.
- **Nuance Documented:** In Python `httpx`, the subsequent connection performs its own DNS resolution. While pre-resolution blocks standard attacks, true zero-window DNS rebinding mitigation requires socket pinning or transport overriding. This limitation is honestly documented in `docs/security/url-ingestion-ssrf.md`.

### 7.7 Quota Correctness & Concurrency
- **Investigation:** `QuotaService` enforces monthly token limits and daily request limits *before* calling downstream providers, raising HTTP 429 when exhausted.
- **Resolution for M08:** Quotas are checked pre-invocation and logged atomically post-invocation. M08 adds publication-level rate throttling to protect public endpoints from abusive concurrency.

---

## 8. M08 Implementation Blueprint

```
                                 ┌─────────────────────────────────────────────────────────────┐
                                 │                   Assistant Publishing                      │
                                 │       Visibility: PRIVATE | WORKSPACE | PUBLIC              │
                                 └──────────────────────────────┬──────────────────────────────┘
                                                                │
                                ┌───────────────────────────────┴──────────────────────────────┐
                                │                                                              │
                                ▼                                                              ▼
               ┌─────────────────────────────────┐                           ┌──────────────────────────────────┐
               │    Public Web Page & Embed      │                           │          Developer API           │
               │   GET /p/{public_id}            │                           │   Header: Authorization:         │
               │   POST /api/v1/public/.../chat  │                           │   Bearer mmaip_...               │
               └────────────────┬────────────────┘                           └─────────────────┬────────────────┘
                                │                                                              │
                                │   ┌──────────────────────────────────────────────────────┐   │
                                └──►│            Public Security & Policy Layer            │◄──┘
                                    │  - Rate Limiting (IP & Key)                          │
                                    │  - Quota Pre-Check (HTTP 429)                        │
                                    │  - Public Knowledge Eligibility Check                │
                                    │  - Secret Hash Verification (SHA-256)                │
                                    └──────────────────────────┬───────────────────────────┘
                                                               │
                                                               ▼
                                    ┌──────────────────────────────────────────────────────┐
                                    │              Assistant Runtime Engine                │
                                    │            (Single Unified Pipeline)                 │
                                    │  - 4-Tier Prompt Assembly                            │
                                    │  - Authorized Vector/FTS Retrieval                   │
                                    │  - BYOK Plaintext Secret Resolution                  │
                                    │  - Provider Streaming SSE Dispatch                   │
                                    │  - Atomic Usage Accounting Logging                   │
                                    └──────────────────────────────────────────────────────┘
```

### Planned Deliverables
1. **Database Migration `0008_assistant_publishing_and_api_keys.py`**:
   - `assistant_publications`
   - `api_keys`
   - `public_chat_sessions`
   - Columns on `provider_usage_logs` (`credential_source`, `traffic_type`)
2. **Backend Services & Endpoints**:
   - `backend/app/services/publishing_service.py`: Publication lifecycle, domain validation, public access checks.
   - `backend/app/services/api_key_service.py`: Cryptographic key generation, SHA-256 hashing, scope enforcement.
   - `backend/app/api/v1/public_chat.py`: Mounted at `/api/v1/public/assistants/{public_id}/...`.
   - `backend/app/api/v1/developer.py`: Mounted at `/api/v1/developer/...`.
3. **Frontend Publishing & Embed UI**:
   - Public chat page: `frontend/app/p/[publicId]/page.tsx`.
   - Embed widget iframe target: `frontend/app/embed/[publicId]/page.tsx`.
   - Assistant Workspace "Publish" tab: Visibility toggle, domain restrictions, embed snippet generator, API key creation drawer.
   - Knowledge Studio Chunk Inspector drawer.
4. **Official Lightweight SDKs**:
   - TypeScript SDK: `sdk/typescript/` (`@mmaip/client` thin client with streaming).
   - Python SDK: `sdk/python/` (`mmaip` async/sync client with streaming).
5. **Comprehensive Acceptance & Security Tests**:
   - `backend/tests/test_m08_publishing_and_api_keys.py`.

---

## 9. Test & Acceptance Plan

| Test Category | Target Scenarios | Verification Standard |
|---|---|---|
| **Publication Lifecycle** | Publish, update settings, change visibility, unpublish, revoke. | Unpublish immediately returns 404/410 on public endpoints. |
| **Public Chat Security** | Public visitor chats with public assistant; receives streaming tokens and safe citations. | System prompts, tenant IDs, and private documents are never leaked. |
| **Private Knowledge Defense** | Public assistant attached to KB with `access_level="INTERNAL"` attempts retrieval. | Private chunks are excluded from retrieval results. |
| **Embed Domain Validation** | Request with `Origin: https://allowed.com` vs `Origin: https://evil.com`. | Disallowed origin rejected; iframe headers validated. |
| **API Key Scopes** | Key with `assistant:read` attempts `POST /chat`. | HTTP 403 Forbidden with stable error code. |
| **Key Hashing & Revocation** | Raw key tested, revoked key tested, hash verified in DB. | Plaintext never saved; revoked key fails in 0ms. |
| **SDK Integration** | TypeScript & Python SDKs execute chat & stream tokens. | Validated in local integration test runner. |
| **Regression Suite** | Existing 189 backend tests. | 100% pass rate preserved. |
| **Frontend Health** | TypeScript & Next.js production build. | 0 errors across all routes. |

---

## 10. Stage 1 Exit Approval

All criteria for Stage 1 Exit Gate have been satisfied. The architecture is sound, tenant boundaries are verified, previous milestone integrity is intact, and M08 design directly fulfills the product vision for individuals, educators, enterprises, and developers without introducing unnecessary complexity or external cost.
