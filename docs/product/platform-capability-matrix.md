# Platform Capability Matrix — Multi-Tenant AI Platform

**Reference:** Milestone M08 Baseline  
**Verified Baseline:** Commit `ad46a44` | Pytest: 189 Pass, 18 Skip, 0 Fail  

---

## 1. Capability Status Taxonomy
- `IMPLEMENTED_AND_VERIFIED`: Full database, backend service, API endpoint, and frontend UI implemented and verified through automated tests or interactive walkthroughs.
- `IMPLEMENTED_BUT_NOT_VERIFIED`: Code is present across the stack but lacks live external network verification (e.g. live cloud credentials).
- `PARTIALLY_IMPLEMENTED`: Substantial backend or frontend exists, but specific UI drawers or background processing integrations are incomplete.
- `UI_ONLY`: Interface exists without live API integration.
- `BACKEND_ONLY`: API endpoints and database services exist without corresponding user-facing UI controls.
- `MOCK_OR_PLACEHOLDER`: Test harness mock or static stub.
- `NOT_IMPLEMENTED`: Feature planned but not yet built.
- `DEFERRED`: Intentionally scheduled for future operational milestones (M09+).

---

## 2. Comprehensive Capability Matrix (39 Areas)

| # | Feature Area | Status | User Value | Frontend Path | Backend Endpoints | Security & Isolation |
|---|---|---|---|---|---|---|
| 1 | **Authentication** | `IMPLEMENTED_AND_VERIFIED` | Secure login, registration, JWT session management. | `/login`, `/register` | `/api/v1/auth/*` | Argon2id, JWT Bearer, tenant membership validation. |
| 2 | **Tenants & Organizations** | `IMPLEMENTED_AND_VERIFIED` | Partitioning of organizations and solo users. | `/dashboard/workspace` | `/api/v1/tenants/*` | Strictly enforced `tenant_id` foreign keys. |
| 3 | **Workspaces** | `IMPLEMENTED_AND_VERIFIED` | Multi-organization switcher and header scoping. | Topbar Workspace Switcher | Header `X-Tenant-ID` validation | Membership verification per tenant switch. |
| 4 | **Departments & Groups** | `IMPLEMENTED_AND_VERIFIED` | Granular internal organizational partitioning. | `/dashboard/departments`, `/groups` | `/api/v1/departments/*`, `/groups/*` | Document ACL restricted by user department. |
| 5 | **RBAC & Permissions** | `IMPLEMENTED_AND_VERIFIED` | Owner, Admin, Member, Viewer role enforcement. | Role badges, dynamic UI action hiding | `require_permission(...)` dependency | Server-side permission check on all mutations. |
| 6 | **Assistant Templates** | `IMPLEMENTED_AND_VERIFIED` | 12 starter templates with recommended settings. | Assistant Creation Step 1 | `/api/v1/assistants/templates` | In-memory registry; tenant-safe. |
| 7 | **Assistant Creation** | `IMPLEMENTED_AND_VERIFIED` | 5-step guided wizard for ordinary creators. | `/dashboard/assistants` (New Assistant Modal) | `POST /api/v1/assistants` | Tenant ownership assigned on creation. |
| 8 | **Assistant Configuration** | `IMPLEMENTED_AND_VERIFIED` | Dual Simple/Advanced modes modifying single schema. | `/dashboard/assistants` (Workspace Drawer) | `PATCH /api/v1/assistants/{id}` | Only tenant admins/owners can update. |
| 9 | **Prompt Trust Hierarchy** | `IMPLEMENTED_AND_VERIFIED` | 4-tier assembly preventing prompt injection leaks. | Configurable in Advanced Mode | `app/assistant_runtime/context.py` | Guardrails isolated from user input. |
| 10 | **Configuration Versioning** | `IMPLEMENTED_AND_VERIFIED` | Audit trail of config changes with forward rollback. | Version history dropdown & rollback button | `GET /assistants/{id}/versions`, `/rollback` | Immutable version records; tenant-scoped. |
| 11 | **Conversations** | `IMPLEMENTED_AND_VERIFIED` | Multi-turn dialog persistence. | Assistant Chat Workspace | `/api/v1/conversations/*` | Conversation and messages scoped by `tenant_id`. |
| 12 | **Chat Streaming** | `IMPLEMENTED_AND_VERIFIED` | Real-time token streaming with SSE. | Interactive Chat View | `POST /api/v1/assistants/{id}/chat` | Tokens streamed directly via SSE. |
| 13 | **Citations** | `IMPLEMENTED_AND_VERIFIED` | Grounded source citations with page numbers and snippets. | Footnote popovers and citation drawer | Persisted in `MessageCitation` table | Chunks verified against tenant ownership. |
| 14 | **Document Ingestion** | `IMPLEMENTED_AND_VERIFIED` | Upload and parsing of PDF, DOCX, TXT, MD. | `/dashboard/knowledge` | `POST /api/v1/documents/upload` | File validation, path sanitization, size limits. |
| 15 | **OCR Engine** | `PARTIALLY_IMPLEMENTED` | Optical character recognition on scanned PDFs/images. | Automated during ingestion | `app/ocr/engine.py` | CPU-friendly Tesseract with text fallback. |
| 16 | **Chunking Engine** | `IMPLEMENTED_AND_VERIFIED` | Structural, sentence, and fixed-size chunking. | Document processing stage | `app/chunking/*` | Chunks maintain page number and heading path. |
| 17 | **Chunk Inspection** | `PARTIALLY_IMPLEMENTED` | Inspector viewing chunk boundaries and token counts. | Knowledge Studio Drawer (M08) | `GET /api/v1/documents/{id}/chunks` | User can only inspect authorized tenant docs. |
| 18 | **Embeddings** | `IMPLEMENTED_AND_VERIFIED` | FastEmbed CPU embeddings & OpenAI-compatible embeddings. | Configured per Knowledge Base | `app/embeddings/*` | CPU-friendly, no GPU required. |
| 19 | **Vector Stores** | `IMPLEMENTED_AND_VERIFIED` | PostgreSQL FTS, pgvector, and Qdrant support. | Auto-selected based on deployment | `app/vectorstores/*` | Storage partitioned by `tenant_id` filter. |
| 20 | **Retrieval Engine** | `IMPLEMENTED_AND_VERIFIED` | Lexical (`ts_rank_cd`), Semantic, Hybrid (RRF). | Automated during assistant inference | `app/retrieval/service.py` | Pre-retrieval authorization validates user ACL. |
| 21 | **Retrieval Playground** | `IMPLEMENTED_AND_VERIFIED` | Interactive query tester with score breakdowns. | `/dashboard/knowledge` (Playground Tab) | `POST /api/v1/retrieval/playground` | Zero persistence; authorized queries only. |
| 22 | **Safe URL Ingestion** | `IMPLEMENTED_AND_VERIFIED` | Web page ingestion with SSRF defenses. | Knowledge Studio URL Ingestion Modal | `POST /api/v1/documents/ingest-url` | Blocks RFC 1918, loopback, and metadata IPs. |
| 23 | **Provider Registry** | `IMPLEMENTED_AND_VERIFIED` | Groq, Anthropic, Gemini, OpenAI, OmniRoute, Mock. | `/dashboard/providers` | `GET /api/v1/providers/directory` | Dynamic catalog declaring model capabilities. |
| 24 | **BYOK Key Vault** | `IMPLEMENTED_AND_VERIFIED` | Encrypted storage for organization provider keys. | `/dashboard/providers` (Keys Table) | `/api/v1/providers/credentials/*` | Fernet encrypted, keys masked as `sk-...abcd`. |
| 25 | **Provider Selection** | `IMPLEMENTED_AND_VERIFIED` | Dynamic model picker in assistant settings. | Assistant Studio Model Tab | `/api/v1/assistants/{id}` | Validates model against capability registry. |
| 26 | **Usage Accounting** | `IMPLEMENTED_AND_VERIFIED` | Token and request logging per provider call. | `/dashboard/providers` (Usage Summary) | `GET /api/v1/providers/usage/summary` | Atomic logging into `provider_usage_logs`. |
| 27 | **Quota Enforcement** | `IMPLEMENTED_AND_VERIFIED` | Pre-invocation checks against daily/monthly limits. | Quota usage cards | `app/services/quota_service.py` | Raises HTTP 429 when limits are reached. |
| 28 | **Assistant Testing** | `IMPLEMENTED_AND_VERIFIED` | Live zero-persistence preview mode in Studio. | Assistant Workspace Preview Pane | `POST /api/v1/assistants/preview` | In-memory execution; zero DB pollution. |
| 29 | **Assistant Publishing** | `NOT_IMPLEMENTED` | Visibility control (Private, Workspace, Public). | Target M08 (Publish Tab) | `POST /api/v1/assistants/{id}/publish` | Public access requires explicit confirmation. |
| 30 | **Embed Integration** | `NOT_IMPLEMENTED` | Website embed widget with domain restrictions. | Target M08 (Embed Modal) | `GET /api/v1/public/embed/{id}` | Iframe isolation; allowed origin verification. |
| 31 | **Developer APIs** | `NOT_IMPLEMENTED` | Versioned endpoints for external applications. | Target M08 (Developer Settings) | `POST /api/v1/developer/*` | Bearer token authentication via API keys. |
| 32 | **SDKs** | `NOT_IMPLEMENTED` | TypeScript and Python client libraries. | `sdk/typescript/`, `sdk/python/` | Thin API wrappers | Zero server logic duplication in SDKs. |
| 33 | **Audit Logging** | `IMPLEMENTED_AND_VERIFIED` | Immutable audit trail for administrative changes. | `/dashboard/audit` | `/api/v1/audit/logs` | Tamper-proof audit logs per tenant. |
| 34 | **Tenant Settings** | `IMPLEMENTED_AND_VERIFIED` | Workspace configuration, member invites. | `/dashboard/settings` | `/api/v1/tenants/*` | Restricted to tenant Owners and Admins. |
| 35 | **Error Handling** | `IMPLEMENTED_AND_VERIFIED` | Structured HTTP exceptions and client toasts. | Global Error Boundary | Standardized JSON Error format | Strips internal stack traces in public mode. |
| 36 | **Observability** | `PARTIALLY_IMPLEMENTED` | Health checks and structured execution logs. | `/api/v1/health` | Standard library logging | Tracing & OpenTelemetry deferred to M09. |
| 37 | **Background Jobs** | `PARTIALLY_IMPLEMENTED` | Ingestion job processing in async workers. | Processing status badges | `asyncio.create_task` | Distributed Celery queue deferred to M09. |
| 38 | **Data Recovery** | `DEFERRED` | Automated DB and Qdrant recovery procedures. | CLI backup scripts | Disaster recovery runbooks | Drills deferred (`M05 = CONDITIONAL_PASS`). |
| 39 | **Deployment Readiness** | `IMPLEMENTED_AND_VERIFIED` | Blueprints for Docker, Render, and Vercel. | Production builds validated | `render.yaml`, `Dockerfile` | Tested in M05. |
