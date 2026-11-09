# Product Capability Gap Matrix — Multi-Tenant AI Assistant Platform

**Audit Baseline Date:** 2026-11-08  
**Repository Baseline Commit:** `4f75f68`  
**Test Suite Verification:** 170 Passed, 18 Skipped, 0 Failed (`pytest backend/tests`)  

---

## 1. Capability Status Taxonomy

- `IMPLEMENTED_AND_VERIFIED`: Feature is fully built in backend & frontend, integrated, and verified by passing tests or live browser execution.
- `IMPLEMENTED_BUT_NOT_VERIFIED`: Code exists in both backend and frontend, but lacks end-to-end integration test coverage or live cloud verification.
- `PARTIALLY_IMPLEMENTED`: Core logic exists in backend and/or partial UI, but key user workflows or settings are missing.
- `BACKEND_ONLY`: API endpoints, models, and repositories exist, but there is no frontend interface for users.
- `UI_ONLY`: Frontend screen or form exists, but it uses hardcoded mock data or does not connect to backend endpoints.
- `MOCK_OR_PLACEHOLDER`: Feature only exists as a mock adapter, static card, or stub.
- `NOT_IMPLEMENTED`: Neither backend nor frontend code exists for this feature.
- `DEFERRED`: Explicitly postponed by architectural decision (e.g. Docker recovery drills).

---

## 2. Comprehensive Capability Matrix

### 2.1 Studio 1: Assistant Studio & Guided Lifecycle

| Capability | Status | User Expectation | What Currently Exists | Implementing Files & Services | What Is Missing | E2E Tested? | Required Implementation Action |
|---|---|---|---|---|---|---|---|
| **Guided Assistant Wizard** | `PARTIALLY_IMPLEMENTED` | Step-by-step wizard to create an assistant with templates, audience, tone, and knowledge. | Side drawer in `assistants/page.tsx` with raw inputs: name, description, model, temperature, max tokens, KBs, retrieval mode, system prompt. | Frontend: `frontend/app/dashboard/assistants/page.tsx`<br>Backend: `backend/app/api/v1/assistants.py` | No step wizard; no purpose selector; technical jargon exposed immediately to beginners; no audience/tone presets. | Partial (CRUD tests pass) | Build `AssistantCreationWizard.tsx` with 5 steps: Purpose, Persona, Knowledge, Guardrails, Review. |
| **Purpose Templates (Education, HR, Support, Legal)** | `NOT_IMPLEMENTED` | Select from pre-configured blueprints (Exam Prep, MCQ Generator, Employee Handbook, Customer Support, etc.). | Only generic assistant creation with empty system prompt textarea. | None. (Only freeform `system_prompt` in `models/assistant.py`). | Template registry, template catalog UI, template schema, initial prompts, suggested retrieval parameters. | No | Create `app/templates/registry.py` with 12 extensible templates and template gallery modal in frontend. |
| **Dual-Mode Experience (Simple vs. Advanced)** | `NOT_IMPLEMENTED` | Beginners see simple choices (Tone, Knowledge); Engineers can expand to tune Top-K, similarity thresholds, RRF. | Single drawer showing both basic and technical parameters mixed together. | `frontend/app/dashboard/assistants/page.tsx` | Mode toggle switch; progressive disclosure of technical parameters; sensible defaults in simple mode. | No | Add `Simple/Advanced` toggle in assistant editor, hiding Top-K, temperature, and hybrid weights in Simple mode. |
| **Prompt Management & Guardrails** | `PARTIALLY_IMPLEMENTED` | Versioned prompts, prompt history diffing, immutable platform safety guardrails. | `AssistantVersion` and `AssistantPrompt` tables exist in DB; runtime wraps prompt in `assistant_runtime/runtime.py`. | Backend: `backend/app/models/assistant.py`, `backend/app/assistant_runtime/runtime.py` | No UI to view prompt versions, revert to previous prompt, or configure separate refusal/citation guardrails. | No | Create prompt version history inspector in frontend and 4-tier prompt composition in runtime. |
| **Assistant Listing & Filtering** | `IMPLEMENTED_AND_VERIFIED` | View, select, and manage all assistants in active workspace. | Left sidebar lists all assistants with badge for active model and KB count. | Frontend: `frontend/app/dashboard/assistants/page.tsx`<br>Backend: `backend/app/api/v1/assistants.py` | Search bar for filtering long lists of assistants; status filtering. | Yes (`test_assistants_and_rag.py`) | Add search/filter input to assistant sidebar. |

---

### 2.2 Studio 2: Knowledge & Retrieval Studio

| Capability | Status | User Expectation | What Currently Exists | Implementing Files & Services | What Is Missing | E2E Tested? | Required Implementation Action |
|---|---|---|---|---|---|---|---|
| **Multi-Format Document Parsing** | `IMPLEMENTED_AND_VERIFIED` | Ingest PDF, DOCX, XLSX, PPTX, CSV, JSON, SQL, TXT, Markdown. | Fully implemented parser registry with 10 format parsers, including AST parsing for SQL. | Backend: `backend/app/parsers/`<br>`pdf.py`, `docx.py`, `xlsx.py`, `pptx.py`, `csv_parser.py`, `sql_parser.py`, `markdown.py`, `txt.py` | None for core files. Web URL crawler is missing. | Yes (`test_parsers.py`) | Maintain parser security; add URL web crawler with SSRF protection. |
| **Web / URL Ingestion** | `NOT_IMPLEMENTED` | Ingest website or documentation URL with automated sanitization. | Not present. Only local file upload is implemented. | None | SSRF-safe URL fetcher, HTML-to-markdown extractor, DNS rebinding prevention. | No | Build `backend/app/parsers/web_parser.py` with strict RFC-1918 IP blocklist and rate limiter. |
| **Ingestion Lifecycle & Progress** | `IMPLEMENTED_AND_VERIFIED` | Real-time progress through Upload, Validation, Parsing, OCR, Chunking, Embedding, Indexing. | Document status transitions, `IngestionJob`, `IngestionEvent` tables, progress polling in UI. | Frontend: `frontend/app/dashboard/knowledge/page.tsx`<br>Backend: `backend/app/services/ingestion/service.py` | Durable worker (currently runs in background asyncio task; worker restarts not recovered). | Yes (`test_ingestion_pipeline.py`) | Add durable recovery on startup to resume unfinished jobs. |
| **Chunk Inspector & Chunking Preview** | `NOT_IMPLEMENTED` | Browse generated chunks, inspect token counts, heading breadcrumbs, and compare chunking settings. | Chunks are stored in `document_chunks` table, but UI only shows total chunk count. | Backend: `backend/app/models/knowledge.py`<br>`frontend/app/dashboard/knowledge/page.tsx` | Chunk inspector tab in frontend; chunking preview API endpoint; comparison slider. | No | Build `ChunkInspectorModal.tsx` and API `/api/v1/documents/{id}/chunks` with pagination. |
| **Retrieval Playground** | `PARTIALLY_IMPLEMENTED` | Test queries interactively and view scores (dense, BM25, RRF) and document ACL outcomes. | `RetrievalPreviewTab.tsx` exists and queries `/api/v1/retrieval/preview`. | Frontend: `frontend/app/dashboard/knowledge/RetrievalPreviewTab.tsx`<br>Backend: `backend/app/api/v1/retrieval.py` | UI is dense and lacks visual score breakdown (showing why chunk A scored higher than chunk B). | Yes (`test_hybrid_retrieval.py`) | Polish `RetrievalPreviewTab.tsx` with Linear-style score cards and query breakdown. |
| **Document-Level Access Permissions** | `BACKEND_ONLY` | Assign document read access to specific departments or employee groups. | `department_id` and `access_level` columns exist in `documents` table and are checked in retrieval SQL. | Backend: `backend/app/models/knowledge.py`, `backend/app/retrieval/authorization.py` | Frontend upload modal has no department or group selector; documents default to tenant-wide. | Yes (`test_retrieval_security.py`) | Add department/group permission selector in document upload and edit dialogs. |

---

### 2.3 Studio 3: Model & Integration Studio (BYOK & Quotas)

| Capability | Status | User Expectation | What Currently Exists | Implementing Files & Services | What Is Missing | E2E Tested? | Required Implementation Action |
|---|---|---|---|---|---|---|---|
| **Multi-Provider BYOK Registry** | `PARTIALLY_IMPLEMENTED` | Connect API keys for OpenAI, Anthropic, Gemini, Groq, OpenRouter, Mistral. | `OpenAIProvider` exists (handles OpenAI and OmniRoute) with encrypted BYOK key support on Assistant model. | Backend: `backend/app/llm/providers/openai_provider.py`, `migration 0005` | Native Anthropic, Gemini, and Groq provider adapters; model capability metadata catalog. | Yes (`test_assistants_and_rag.py`) | Add `AnthropicProvider`, `GeminiProvider`, `GroqProvider`, and provider metadata registry. |
| **Key Vault & Connection Testing** | `NOT_IMPLEMENTED` | Central workspace key vault to manage keys, test connection, and check validity. | Keys are passed into individual assistant settings or `.env`. Settings page is static. | Frontend: `frontend/app/dashboard/settings/page.tsx` | Central key vault UI; "Test Connection" API route; credential revocation; secret rotation. | No | Create `TenantKeyVault` table and UI in `/dashboard/settings/providers` with connection test button. |
| **Tenant Quotas & Usage Enforcement** | `UI_ONLY` | Enforce monthly token quotas, storage limits, and assistant caps. | `settings/page.tsx` displays static hardcoded cards ("10,000,000 Tokens", "50 Seats"). | Frontend: `frontend/app/dashboard/settings/page.tsx` | Backend usage tracking tables, token counters, quota enforcement interceptor in chat runtime. | No | Create `UsageQuota` model, track token consumption per turn, and return 429 when quota exceeded. |
| **Fallback Routing & Policy** | `NOT_IMPLEMENTED` | Automatically fallback to secondary model if primary provider is down or rates out. | Assistants have a single `default_model` and `llm_provider`. | `backend/app/models/assistant.py` | Fallback provider/model fields; circuit breaker; automatic retry with fallback in runtime. | No | Add `fallback_model` and `fallback_provider` to Assistant model and runtime execution loop. |

---

### 2.4 Studio 4: Complete Chat Experience

| Capability | Status | User Expectation | What Currently Exists | Implementing Files & Services | What Is Missing | E2E Tested? | Required Implementation Action |
|---|---|---|---|---|---|---|---|
| **Streaming SSE Chat** | `IMPLEMENTED_AND_VERIFIED` | Real-time token streaming with immediate markdown rendering. | Implemented via FastAPI SSE endpoint `/api/v1/assistants/{id}/chat` and frontend event reader. | Backend: `backend/app/api/v1/assistants.py`<br>Frontend: `frontend/app/dashboard/assistants/page.tsx` | Stop generation backend cancellation; message retry button. | Yes (`test_assistants_and_rag.py`) | Add abort signal listener in backend SSE generator and "Regenerate" button in UI. |
| **Interactive Visual Citations** | `IMPLEMENTED_AND_VERIFIED` | Verified citation badges opening PDF canvas with bounding box highlight overlay. | Fully built visual PDF canvas modal with Letter aspect ratio, bounding box overlay, and carousel navigation. | Frontend: `frontend/app/dashboard/assistants/page.tsx`<br>Backend: `backend/app/retrieval/citations.py` | Distinguishing exact geometry from synthetic position is done in code, but needs clear badge in UI. | Yes (`test_m05_citation_highlighting.py`) | Add explicit "Geometric Coordinate" vs. "Text Alignment" pill in citation viewer. |
| **Conversation History & Search** | `PARTIALLY_IMPLEMENTED` | Manage conversations: search, rename, archive, and delete. | Conversations list and switch working; delete working. | Frontend: `frontend/app/dashboard/assistants/page.tsx`<br>Backend: `backend/app/api/v1/conversations.py` | Conversation search bar; inline rename title; conversation archiving. | Yes (`test_assistants_and_rag.py`) | Add inline title edit and search filter in conversation list. |
| **Chat File Attachments** | `NOT_IMPLEMENTED` | Attach files directly to chat turn for temporary context without permanent KB ingestion. | `MessageAttachment` table exists in DB schema, but no API route or UI button to upload chat attachments. | Backend: `backend/app/models/conversation.py` | File upload button in chat input bar; ephemeral parser; attachment context injection into prompt. | No | Implement chat attachment endpoint `/conversations/{id}/messages/attach` and UI dropzone. |
| **Voice Input & Output** | `NOT_IMPLEMENTED` | Speech-to-text input (mic button) and text-to-speech voice playback. | No voice implementation. | None | Browser Web Speech API integration or Whisper/TTS provider adapter. | No | Implement client-side Web Speech API recorder with fallback to Whisper API. |

---

### 2.5 Studio 5: Publishing, Administration & Observability

| Capability | Status | User Expectation | What Currently Exists | Implementing Files & Services | What Is Missing | E2E Tested? | Required Implementation Action |
|---|---|---|---|---|---|---|---|
| **Public Share Link** | `NOT_IMPLEMENTED` | Generate a shareable public URL for an assistant with custom welcome message. | Only `visibility="workspace"` or `"private"` in DB. No public route. | None | Public chat page `/chat/[share_token]`, share link generator, allowed domains settings. | No | Add `share_token` column to Assistant model and public route `/chat/[share_token]`. |
| **Embeddable Web Widget** | `NOT_IMPLEMENTED` | Copy-paste `<script>` or `<iframe>` snippet to embed assistant on any external website. | Not present. | None | Widget bundle (`embed.js`), CORS verification for allowed origins, embed config dialog. | No | Create standalone embed script in Next.js public directory and embed code modal. |
| **Developer API Keys** | `NOT_IMPLEMENTED` | Generate tenant API keys to query assistants programmatically from external apps. | API authentication requires user JWT login token only. | Backend: `backend/app/api/deps.py` | API Key generation table (`api_keys`), header auth (`X-API-Key`), rate limiting. | No | Build `ApiKey` entity, middleware authentication dependency, and settings UI. |
| **Evaluation Studio** | `NOT_IMPLEMENTED` | Benchmark assistant quality: retrieval recall, faithfulness, citation precision, latency. | No evaluation runner in UI or backend. | None | Test question sets model, evaluation runner service, scoring metrics, evaluation dashboard UI. | No | Build `backend/app/evaluations/` service and `/dashboard/evaluations` frontend page. |
| **Observability & Request Tracing** | `PARTIALLY_IMPLEMENTED` | Inspect request traces, latency breakdown, token usage, and error events. | Phoenix tracing toggle in `core/config.py`; structured logs in backend. | Backend: `backend/app/core/config.py` | Integrated UI dashboard for traces, request history viewer, token charts. | No | Build `/dashboard/observability` page displaying recent request traces and latency breakdown. |
| **Multi-Tenant RBAC & Isolation** | `IMPLEMENTED_AND_VERIFIED` | Full tenant isolation, organization workspaces, departments, groups, audit logs. | Complete multi-tenant foundation: 4 system roles, department ACLs, group ACLs, audit events. | Backend: `backend/app/models/`, `backend/app/api/v1/`<br>Frontend: `/dashboard/workspace`, `/employees` | None for foundation. Granular assistant-level sharing needs UI wiring. | Yes (`test_rbac_permissions.py`, `test_tenant_isolation_security.py`) | Maintain strict tenant scoping across all new endpoints. |
| **PostgreSQL & Qdrant Recovery Drills** | `DEFERRED` | Live disaster recovery drills on running containers. | Unit tests pass (`test_m05_database_recovery.py`); live container drills deferred. | `artifacts/evaluations/m05_final_closure_20261108/recovery_drill_remediation/` | Execution against active production cluster. | Deferred (Docker memory limits) | Keep marked as `DEFERRED — NOT RUN` until cloud staging execution. |
