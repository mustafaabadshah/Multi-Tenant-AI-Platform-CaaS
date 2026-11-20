# M09 Preflight: Comprehensive Product Capability Matrix

**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Date:** November 10, 2026  
**Auditor:** Principal Software Architect & Product Engineer  
**Milestone:** M09 — Preflight Capability Audit  

---

## 1. Capability Status Taxonomy
- `IMPLEMENTED_AND_VERIFIED`: Full database, backend service, API endpoint, and frontend UI verified via automated tests or verified live flows.
- `IMPLEMENTED_BUT_NOT_VERIFIED`: Code exists across stack but lacks live external network calls (e.g. cloud provider credentials).
- `PARTIALLY_IMPLEMENTED`: Core capability functional, but specific edge cases, drawers, or background worker resilience require completion.
- `BACKEND_ONLY`: API endpoints and DB models exist without complete user-facing UI controls.
- `UI_ONLY`: Interface exists without live functional API backing.
- `MOCK_OR_PLACEHOLDER`: Test harness mock or static stub.
- `NOT_IMPLEMENTED`: Feature planned but not yet built.
- `DEFERRED`: Intentionally scheduled for future operational milestones.

---

## 2. Product Capability Matrix (42 Platform Areas)

| # | Feature / Area | Status | User Outcome | Backend Implementation | Frontend Implementation | Database Support | Auth Coverage | Test Evidence | Known Limitations | Priority |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Authentication** | `IMPLEMENTED_AND_VERIFIED` | Secure registration and login. | `app/api/v1/auth.py` | `/login`, `/register` | `users` table | Argon2id, JWT | `test_auth.py` (Pass) | None | High |
| 2 | **Tenants & Orgs** | `IMPLEMENTED_AND_VERIFIED` | Multi-tenant isolation for companies & solo users. | `app/api/v1/tenants.py` | `/dashboard/workspace` | `tenants`, `organizations` | Tenant membership validation | `test_tenants.py` (Pass) | None | High |
| 3 | **Workspaces** | `IMPLEMENTED_AND_VERIFIED` | Switch between organizations and workspaces. | `app/api/deps.py` (`TenantContext`) | Topbar workspace switcher | `tenant_memberships` | Header `X-Tenant-ID` check | `test_tenants.py` (Pass) | None | Medium |
| 4 | **Departments & Groups** | `IMPLEMENTED_AND_VERIFIED` | Internal departmental segmentation for ACLs. | `app/api/v1/departments.py` | `/dashboard/departments` | `departments`, `employee_groups` | Scoped to active tenant | `test_departments.py` (Pass) | None | Medium |
| 5 | **RBAC & Permissions** | `IMPLEMENTED_AND_VERIFIED` | Role-based controls (Owner, Admin, Member, Viewer). | `app/core/constants.py` | Dynamic UI button disabling | `roles`, `permissions` | `require_permission(...)` | `test_rbac.py` (Pass) | None | High |
| 6 | **Assistant Templates** | `IMPLEMENTED_AND_VERIFIED` | 12 starter templates for quick creation. | `app/templates/registry.py` | Assistant wizard Step 1 | In-memory registry | Tenant-safe read-only | `test_assistants.py` (Pass) | Static catalog | Medium |
| 7 | **Assistant Creation Wizard** | `IMPLEMENTED_AND_VERIFIED` | 5-step guided wizard for non-technical users. | `app/api/v1/assistants.py` | `/dashboard/assistants` modal | `assistants` table | Admin/Owner permission | `test_assistants.py` (Pass) | None | High |
| 8 | **Assistant Configuration** | `IMPLEMENTED_AND_VERIFIED` | Dual Simple & Advanced configuration modes. | `app/api/v1/assistants.py` | Assistant Studio Drawer | `assistants` config cols | Validated single schema | `test_assistants.py` (Pass) | None | High |
| 9 | **Prompt Trust Hierarchy** | `IMPLEMENTED_AND_VERIFIED` | 4-tier assembly preventing prompt injection. | `app/assistant_runtime/context.py` | Configurable in Advanced tab | Dynamic context builder | Sanitized prompt levels | `test_prompt_hierarchy.py` (Pass) | None | High |
| 10 | **Configuration Versioning** | `IMPLEMENTED_AND_VERIFIED` | Rollback and audit history for assistants. | `app/services/assistant_versioning.py`| Version dropdown in Studio | `assistant_versions` | Immutable version records | `test_assistant_versions.py` (Pass) | None | Medium |
| 11 | **Conversations** | `IMPLEMENTED_AND_VERIFIED` | Persistent multi-turn dialogs. | `app/api/v1/conversations.py` | Assistant Chat Workspace | `conversations`, `messages` | Scoped by tenant & user | `test_conversations.py` (Pass) | None | High |
| 12 | **Chat Streaming** | `IMPLEMENTED_AND_VERIFIED` | Real-time SSE token streaming. | `app/assistant_runtime/runtime.py` | Chat streaming bubbles | Async SSE generator | Scoped token generator | `test_chat_stream.py` (Pass) | None | High |
| 13 | **Citations & Footnotes** | `IMPLEMENTED_AND_VERIFIED` | Grounded citations with page numbers & snippets. | `app/assistant_runtime/citations.py` | Interactive footnote popovers | `message_citations` | Verified chunk ownership | `test_citations.py` (Pass) | None | High |
| 14 | **Document Ingestion** | `IMPLEMENTED_AND_VERIFIED` | Ingestion of PDF, DOCX, TXT, MD files. | `app/ingestion/service.py` | `/dashboard/knowledge` upload | `documents`, `document_chunks` | Path validation, size limits | `test_ingestion.py` (Pass) | CPU extraction only | High |
| 15 | **OCR Engine** | `PARTIALLY_IMPLEMENTED` | Text extraction from scanned documents. | `app/ocr/engine.py` | Processing status badges | OCR applied flag | Handled in background | `test_ocr.py` (Pass) | Requires local tesseract | Low |
| 16 | **Chunking Engine** | `IMPLEMENTED_AND_VERIFIED` | Structural, sentence, fixed-size chunking. | `app/chunking/*` | Configurable per KB | `document_chunks` | Scoped by document | `test_chunking.py` (Pass) | None | High |
| 17 | **Chunk Inspection** | `IMPLEMENTED_AND_VERIFIED` | Drawer inspecting chunk boundaries & tokens. | `app/api/v1/documents.py` | Knowledge Studio Drawer | `document_chunks` query | Authorized tenant docs | Live verified in M08 | None | Medium |
| 18 | **FastEmbed CPU Embeddings** | `IMPLEMENTED_AND_VERIFIED` | Zero-GPU CPU embeddings (384 dims). | `app/embeddings/fastembed_provider.py` | Configured per KB | `chunk_embeddings` | Tenant-scoped vectors | `test_embeddings.py` (Pass) | CPU compute | High |
| 19 | **Vector Storage (FTS & PGV)** | `IMPLEMENTED_AND_VERIFIED` | Full-text lexical search & pgvector cosine search. | `app/vectorstores/*` | Auto-selected by environment | FTS / `chunk_embeddings` | Scoped by `tenant_id` | `test_vectorstores.py` (Pass) | None | High |
| 20 | **Retrieval Engine (Hybrid RRF)** | `IMPLEMENTED_AND_VERIFIED` | Hybrid retrieval combining lexical + semantic. | `app/retrieval/service.py` | Automated during RAG | RRF $k=60$ fusion | Pre-retrieval ACL check | `test_hybrid_retrieval.py` (Pass) | None | High |
| 21 | **Retrieval Playground** | `IMPLEMENTED_AND_VERIFIED` | Interactive query tester with score breakdown. | `app/api/v1/retrieval.py` | Knowledge Studio Playground | Zero persistence | Authorized queries only | Live verified in M07 | None | Medium |
| 22 | **Safe URL Ingestion** | `IMPLEMENTED_AND_VERIFIED` | Web page ingestion with SSRF defenses. | `app/api/v1/documents.py` | URL Ingestion modal | `documents` table | Blocks RFC 1918 / loopback | `test_url_ingestion.py` (Pass) | Static HTML only | Medium |
| 23 | **Provider Registry** | `IMPLEMENTED_AND_VERIFIED` | Dynamic catalog of LLM capabilities. | `app/providers/registry.py` | `/dashboard/providers` | Capability registry | Tenant-scoped credentials | `test_providers.py` (Pass) | None | High |
| 24 | **BYOK Key Vault** | `IMPLEMENTED_AND_VERIFIED` | Fernet encrypted organization provider keys. | `app/services/credential_service.py` | Providers Key Table | `provider_credentials` | Master key encryption | `test_byok_vault.py` (Pass) | None | High |
| 25 | **Dynamic Model Selection** | `IMPLEMENTED_AND_VERIFIED` | Model picker filtering by context & features. | `app/api/v1/assistants.py` | Assistant Studio Model Tab | Validated against registry | Tenant admin only | `test_assistants.py` (Pass) | None | Medium |
| 26 | **Usage & Token Accounting** | `IMPLEMENTED_AND_VERIFIED` | Token and cost metering per request. | `app/services/quota_service.py` | Usage Summary Cards | `provider_usage_logs` | Scoped per tenant | `test_quotas.py` (Pass) | Estimated vs exact split | High |
| 27 | **Quota Enforcement** | `IMPLEMENTED_AND_VERIFIED` | Daily & monthly limits with HTTP 429 response. | `app/services/quota_service.py` | Quota status badges | `tenant_quotas` | Enforced pre-inference | `test_quotas.py` (Pass) | Concurrency race risk | High |
| 28 | **Assistant Testing** | `IMPLEMENTED_AND_VERIFIED` | Zero-persistence preview mode in Studio. | `app/api/v1/assistants.py` | Assistant Workspace Preview | In-memory execution | Authorized tenant members | Live verified in M06 | None | Medium |
| 29 | **Assistant Publishing** | `IMPLEMENTED_AND_VERIFIED` | Opaque ID generation, lifecycle (Private/Pub). | `app/services/publishing_service.py`| Studio Publish Tab | `assistant_publications` | Explicit publish action | `test_m08_...py` (Pass) | ID entropy 64-bit | High |
| 30 | **Embed Integration** | `IMPLEMENTED_AND_VERIFIED` | Iframe sandboxing, embed.js script loader. | `app/api/v1/public_chat.py` | `/embed/[publicId]` | `assistant_publications` | Origin/Referer check | `test_m08_...py` (Pass) | Origin not full auth | High |
| 31 | **Developer REST API** | `IMPLEMENTED_AND_VERIFIED` | Scoped API key management & chat endpoints. | `app/api/v1/developer.py` | Settings Developer Tab | `api_keys` (SHA-256) | Bearer token scopes | `test_m08_...py` (Pass) | Scopes coarse | High |
| 32 | **Official SDKs** | `IMPLEMENTED_AND_VERIFIED` | TypeScript `@mmaip/client` & Python `mmaip`. | `sdk/typescript/`, `sdk/python/` | Zero internal deps | Thin REST/SSE wrappers | API key authentication | Verified in M08 | No automated SDK tests | High |
| 33 | **Audit Logging** | `IMPLEMENTED_AND_VERIFIED` | Immutable audit trail for admin mutations. | `app/api/v1/audit.py` | `/dashboard/audit` | `audit_logs` | Tenant-scoped read | `test_audit.py` (Pass) | None | Medium |
| 34 | **Tenant Settings** | `IMPLEMENTED_AND_VERIFIED` | Name, slug, member management. | `app/api/v1/tenants.py` | `/dashboard/settings` | `tenants`, `memberships` | Owners/Admins only | `test_tenants.py` (Pass) | None | Medium |
| 35 | **Error Handling** | `IMPLEMENTED_AND_VERIFIED` | Structured JSON errors and client toasts. | `app/main.py` exception handlers | Global Error Boundary | Standardized responses | Stack traces masked in prod | Full test suite | None | High |
| 36 | **AI Evaluation** | `NOT_IMPLEMENTED` | Retrieval & Answer accuracy, faithfulness, Recall@K. | Target M09 (`app/evaluation/`) | Target M09 (Evaluation Tab) | Target M09 tables | Tenant-isolated datasets | Target M09 Stage 2 | None yet | Critical |
| 37 | **Observability & Tracing** | `PARTIALLY_IMPLEMENTED` | Request lifecycle tracing & latency metrics. | Basic log output | Status indicators | Basic `provider_usage_logs`| Redacted headers | Target M09 Stage 3 | Lacks span drilldown | High |
| 38 | **Durable Background Jobs** | `PARTIALLY_IMPLEMENTED` | Ingestion status tracking in DB. | `app/models/ingestion.py` | Ingestion badges | `ingestion_jobs` | Scoped per tenant | `test_ingestion.py` (Pass) | In-memory task loss | High |
| 39 | **Production Storage Adapter** | `PARTIALLY_IMPLEMENTED` | Local disk storage with abstraction for S3. | `app/storage/*` | Document download links | Local path metadata | Tenant folder isolation | `test_storage.py` (Pass) | Local disk primary | Medium |
| 40 | **Model Capability Registry** | `IMPLEMENTED_AND_VERIFIED` | Dynamic model context windows and capabilities. | `app/providers/capabilities.py` | Model detail badges | In-memory registry | Verified catalog | `test_providers.py` (Pass) | Requires doc updates | Medium |
| 41 | **Disaster Recovery Drills** | `DEFERRED` | Automated DB and Qdrant recovery procedures. | CLI scripts (M05) | Runbooks | Snapshot scripts | Sysadmin credentials | None (DEFERRED) | Deferred in M05 | Low |
| 42 | **Production Deployment** | `IMPLEMENTED_BUT_NOT_VERIFIED` | Render & Vercel blueprints and Dockerfiles. | `render.yaml`, `Dockerfile` | Next.js output standalone | Production env configs | Deployment secrets | M05 blueprints verified | Live deploy not run | Medium |
