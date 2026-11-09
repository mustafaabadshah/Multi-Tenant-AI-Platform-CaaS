# Technical Product Roadmap — Multi-Tenant AI Assistant Platform (CaaS)

**Document Version:** 1.0.0  
**Status:** Architecture Proposal & Workstream Plan  
**Paradigm:** Modular Monolith (FastAPI + Next.js App Router)  
**Database Evolution:** Forward Migrations Only (`0006+`), zero alteration of historical migrations (`0001–0005`)  

---

## 1. Roadmap Phasing Strategy

To prevent a sprawl of half-finished features, implementation is organized into **seven cohesive workstreams (A through G)** sequenced by architectural dependency:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            WORKSTREAM DEPENDENCY MAP                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [Phase 1: Core Lifecycle]                                                  │
│   Workstream A: Product Experience & Linear/Apple Notes Design System        │
│        │                                                                    │
│        ▼                                                                    │
│   Workstream B: Assistant Lifecycle & Template System                       │
│        │                                                                    │
│        ▼                                                                    │
│  [Phase 2: Intelligence & Economics]                                        │
│   Workstream C: Knowledge Studio, Chunk Inspector & Retrieval Playground    │
│        │                                                                    │
│        ▼                                                                    │
│   Workstream D: Multi-Provider BYOK Registry, Quotas & Fallback Routing     │
│        │                                                                    │
│        ▼                                                                    │
│  [Phase 3: Daily Utility & Distribution]                                    │
│   Workstream E: Enhanced Chat, Context Pruning, Attachments & Voice        │
│        │                                                                    │
│        ▼                                                                    │
│   Workstream F: Publishing Engine (Web Widget, Share Link & Developer API)  │
│        │                                                                    │
│        ▼                                                                    │
│  [Phase 4: Enterprise Scale & Trust]                                        │
│   Workstream G: Evaluation Studio, Observability & Durable Job Resiliency   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Workstream Breakdown

### Workstream A — Product Experience & Design System
**Objective:** Transform the UI from a generic dark dashboard into an exceptionally clean, responsive **Linear × Apple Notes** design system.

- **Existing Functionality to Reuse:**
  - Next.js 16 App Router structure (`frontend/app/`).
  - Auth context (`frontend/lib/auth-context.tsx`) with active workspace switcher.
  - Lucide icons and basic layout framing.
- **Missing Functionality:**
  - Coherent typographic hierarchy and color tokens (restrained black `#090a0f`, deep slate `#0f172a`, crisp white `#f8fafc`, light blue accent `#38bdf8`).
  - Simple vs. Advanced mode toggle component.
  - Unified modal and side-sheet system.
- **Backend Changes:** None.
- **Frontend Changes:**
  - Redesign `frontend/app/globals.css` with minimalist design tokens.
  - Refactor `frontend/app/dashboard/layout.tsx` to streamline navigation (Home, Assistants, Knowledge, Providers, Evaluations, Settings).
  - Create reusable UI primitives: `Tabs`, `Modal`, `Drawer`, `Badge`, `Toggle`, `ScoreBar`.
- **Database Changes:** None.
- **Security Implications:** None.
- **Tests:** Frontend unit tests for UI components (`npm run test`); Visual smoke test in real browser.
- **Complexity:** Medium (2–3 days).

---

### Workstream B — Complete Assistant Lifecycle & Templates
**Objective:** Enable non-technical users to create, configure, test, and manage purpose-built assistants through a guided workflow and extensible template engine.

- **Existing Functionality to Reuse:**
  - `Assistant` model (`backend/app/models/assistant.py`) and CRUD endpoints (`/api/v1/assistants`).
  - `AssistantKnowledgeBase` association table.
  - Assistant runtime streaming endpoint (`/api/v1/assistants/{id}/chat`).
- **Missing Functionality:**
  - Guided 5-step Creation Wizard (`AssistantCreationWizard.tsx`).
  - Extensible Template Registry (Exam Prep, Tutor, MCQ, HR Handbook, Customer Support, Legal, Personal).
  - Prompt configuration layering: System Guardrails, Persona/Tone, Refusal Rules, Missing Knowledge Fallback.
  - Prompt version inspector and history rollback.
- **Backend Changes:**
  - Create `backend/app/templates/` module with template schema, default prompts, and recommended RAG parameters.
  - Add API endpoints: `GET /api/v1/templates`, `GET /api/v1/assistants/{id}/versions`, `POST /api/v1/assistants/{id}/revert`.
- **Frontend Changes:**
  - Build `AssistantCreationWizard.tsx` with template selection cards.
  - Add `Simple/Advanced` configuration toggle in `frontend/app/dashboard/assistants/page.tsx`.
  - Add Prompt Versioning tab.
- **Database Changes (Forward Migration `0006`):**
  - Add `template_id` (String nullable) and `audience_level` (String default "general") to `assistants` table.
- **Security Implications:**
  - Strict 4-tier prompt layering in runtime: user prompt cannot override immutable system security delimiters.
- **Tests:** Pytest for template seeding and instantiation; Assistant version rollback unit tests.
- **Complexity:** Medium-High (3–4 days).

---

### Workstream C — Knowledge Intelligence, Chunk Inspector & Playground
**Objective:** Provide full transparency into document processing, chunk inspection, and interactive retrieval scoring before connecting knowledge to assistants.

- **Existing Functionality to Reuse:**
  - Multi-format parsers (`backend/app/parsers/`).
  - Chunking algorithms (`recursive.py`, `structured.py`, `markdown.py`).
  - Vector stores (`pgvector_store.py`, `fts_store.py`, `qdrant_store.py`).
  - `DocumentChunk` and `IngestionJob` models.
- **Missing Functionality:**
  - Interactive **Chunk Inspector** in frontend: view individual chunks, tokens, headings, and character bounds.
  - Live chunking parameter comparison preview (tune chunk size/overlap and see changes in real-time).
  - **Retrieval Playground**: submit test query and view detailed score breakdown (BM25 score, Cosine similarity, RRF rank).
  - Web URL crawler with SSRF and DNS rebinding protection.
  - Document-level permission selector in upload dialog (assign to Department or Employee Group).
- **Backend Changes:**
  - Add endpoint `GET /api/v1/documents/{id}/chunks` with pagination and heading filter.
  - Add endpoint `POST /api/v1/chunking/preview` (runs chunker in memory and returns chunk boundaries).
  - Add `backend/app/parsers/web_parser.py` with RFC-1918 IP blocklist and content length caps.
  - Enhance `POST /api/v1/retrieval/preview` to return raw sub-scores (sparse, dense, fused).
- **Frontend Changes:**
  - Add `ChunkInspectorModal.tsx` in `frontend/app/dashboard/knowledge/`.
  - Enhance `RetrievalPreviewTab.tsx` with Linear-style score breakdown cards.
  - Add Department/Group access dropdown in document upload modal.
- **Database Changes (Forward Migration `0006`):**
  - Add `source_type` (Enum: FILE, URL) and `source_url` (String nullable) to `documents` table.
- **Security Implications:**
  - SSRF protection: reject private/loopback IP addresses (`127.0.0.1`, `10.0.0.0/8`, `169.254.169.254`, `::1`).
  - Document ACL enforcement: retrieval query MUST filter by user's active department and group memberships.
- **Tests:** Unit tests for web parser SSRF rejection; Chunk pagination tests; ACL isolation retrieval tests.
- **Complexity:** High (4–5 days).

---

### Workstream D — Provider Ecosystem, BYOK Vault & Quotas
**Objective:** Deliver an extensible multi-provider registry (OpenAI, Anthropic, Gemini, Groq, local models) with encrypted key storage, connection testing, and enforceable tenant quotas.

- **Existing Functionality to Reuse:**
  - AES-256-GCM encryption helpers (`backend/app/core/crypto.py`).
  - `OpenAIProvider` (`backend/app/llm/providers/openai_provider.py`).
  - Assistant `byok_encrypted_key` field from Migration `0005`.
- **Missing Functionality:**
  - Dedicated provider adapters for Anthropic (`claude-3-5-sonnet`), Google Gemini (`gemini-1.5-pro`), and Groq (`llama-3.3-70b`).
  - Workspace-level **Key Vault**: central credential management so keys don't have to be entered repeatedly on every assistant.
  - "Test Connection" API endpoint for instant credential validation.
  - Tenant usage tracking (prompt tokens, completion tokens, storage bytes) and quota enforcement interceptor.
  - Fallback model routing (primary provider fails → automatically try secondary configured provider).
- **Backend Changes:**
  - Implement `AnthropicProvider`, `GeminiProvider`, `GroqProvider` under `backend/app/llm/providers/`.
  - Create `backend/app/services/quota_service.py` with token decrementing and limit checks.
  - Add endpoints: `POST /api/v1/providers/test-connection`, `GET /api/v1/tenant/quotas`, `POST /api/v1/tenant/keys`.
- **Frontend Changes:**
  - Build `/dashboard/settings/providers` page: Key Vault, connection status indicators, test button.
  - Replace static cards in `/dashboard/settings` with live API-driven quota meters.
- **Database Changes (Forward Migration `0007`):**
  - Create `tenant_provider_keys` table (`id`, `tenant_id`, `provider`, `encrypted_api_key`, `key_fingerprint`, `is_active`, `created_at`).
  - Create `tenant_usage_records` table (`id`, `tenant_id`, `user_id`, `assistant_id`, `tokens_prompt`, `tokens_completion`, `cost_estimate_cents`, `timestamp`).
  - Add `fallback_provider` and `fallback_model` columns to `assistants` table.
- **Security Implications:**
  - Plaintext keys NEVER saved or returned to frontend; masked fingerprints only (e.g. `sk-...4a8b`).
  - Stored keys encrypted with AES-256-GCM and tenant-specific salt.
- **Tests:** Mocked connection tests for all 4 providers; Quota exhaustion 429 response tests; Encryption roundtrip tests.
- **Complexity:** High (4–5 days).

---

### Workstream E — Enhanced Chat, Context Management & Attachments
**Objective:** Elevate the chat interface into a responsive, fluid experience with conversation search, message editing/retry, chat attachments, and voice I/O.

- **Existing Functionality to Reuse:**
  - FastAPI SSE streaming endpoint (`/api/v1/assistants/{id}/chat`).
  - `Conversation` and `Message` models (`backend/app/models/conversation.py`).
  - Visual PDF Citation drawer (`MessageCitationItem`).
- **Missing Functionality:**
  - Inline conversation renaming, search, and archiving.
  - Message regeneration and stop-generation backend cancellation.
  - Ephemeral chat file attachments (upload a PDF for single-turn query without permanent KB ingestion).
  - Conversation context pruning and token budget window (preventing context overflow on 50+ turn chats).
  - Web Speech API integration for speech-to-text input and audio readout.
- **Backend Changes:**
  - Add endpoint `POST /api/v1/conversations/{id}/messages/attach` for ephemeral attachments.
  - Enhance `assistant_runtime/context.py` with dynamic conversation summarization / sliding window.
  - Add search parameter `?q=` to `GET /api/v1/conversations`.
- **Frontend Changes:**
  - Add search bar and inline rename in conversation list sidebar.
  - Add "Regenerate" and "Stop" buttons to chat action bar.
  - Add paperclip icon for chat attachments with thumbnail preview.
  - Add microphone button using Web Speech API for voice dictation.
- **Database Changes:** None (schema already supports `MessageAttachment`).
- **Security Implications:**
  - Ephemeral attachments must be validated for safe extensions and scanned for size limits before parsing.
  - IDOR protection: conversation must strictly belong to active user and active tenant.
- **Tests:** Context window truncation test; Attachment lifecycle test; Conversation IDOR negative test.
- **Complexity:** Medium (3–4 days).

---

### Workstream F — Publishing Engine (Share Links, Embed Widget & Developer API)
**Objective:** Enable creators to distribute assistants externally via public shareable links, embeddable website widgets, and developer REST APIs.

- **Existing Functionality to Reuse:**
  - Assistant authorization and streaming chat pipeline.
  - CORS configuration in `backend/app/main.py`.
- **Missing Functionality:**
  - Public unauthenticated / token-protected chat route (`/chat/share/[token]`).
  - Standalone Embeddable Web Widget (`public/widget/embed.js`).
  - Embed configuration modal in Assistant Studio (copy `<script>` tag, configure theme color and position).
  - Developer API Keys (`X-API-Key`) with rate limiting for programmatic query execution.
- **Backend Changes:**
  - Create public endpoint `POST /api/v1/public/chat/{share_token}` with strict rate limiting (IP-based, e.g. 10 req/min).
  - Add `ApiKey` model and authentication dependency in `backend/app/api/deps.py`.
  - Add endpoints: `POST /api/v1/assistants/{id}/publish`, `POST /api/v1/api-keys`.
- **Frontend Changes:**
  - Create public page `frontend/app/chat/share/[token]/page.tsx` with clean, distraction-free Linear styling.
  - Build `PublishingModal.tsx` with Share Link, Embed Widget, and API Code tabs.
  - Build standalone embed widget script `frontend/public/widget/embed.js`.
- **Database Changes (Forward Migration `0008`):**
  - Add `share_token` (String unique nullable), `allowed_origins` (JSON default []), and `is_published` (Boolean default False) to `assistants` table.
  - Create `api_keys` table (`id`, `tenant_id`, `name`, `key_hash`, `prefix`, `expires_at`, `created_at`).
- **Security Implications:**
  - Public endpoints MUST NOT leak internal system instructions, tenant metadata, or other users' conversations.
  - Domain origin verification (`Origin` / `Referer` headers) for embed widgets.
  - Strict IP rate limiting to prevent DDoS or API credit drainage.
- **Tests:** Cross-origin embed request test; Rate limit 429 verification; Public share token isolation test.
- **Complexity:** High (4–5 days).

---

### Workstream G — Quality, Observability & Durable Job Resiliency
**Objective:** Provide automated assistant evaluation (retrieval recall, faithfulness, latency), request trace observability, and resilient background job recovery.

- **Existing Functionality to Reuse:**
  - `IngestionJob` and `IngestionEvent` tables.
  - Phoenix tracing configuration hooks.
  - Pytest evaluation scaffolding (`test_m05_*.py`).
- **Missing Functionality:**
  - **Evaluation Studio:** Create test question sets, run batch evaluations, calculate retrieval recall, faithfulness, and citation precision.
  - **Observability Dashboard:** View recent traces, latency breakdown (retrieval time vs. LLM generation time), token consumption, and error rates.
  - **Durable Job Resiliency:** Worker restart recovery: scan `ingestion_jobs` with status `PROCESSING` on server startup and resume/retry cleanly.
- **Backend Changes:**
  - Create `backend/app/evaluations/` module with evaluation metrics (groundedness, citation accuracy, recall).
  - Add startup job reconciliation routine in `backend/app/main.py` lifespan handler.
  - Add endpoints: `GET /api/v1/evaluations`, `POST /api/v1/evaluations/run`, `GET /api/v1/observability/traces`.
- **Frontend Changes:**
  - Build `/dashboard/evaluations` page with evaluation run history and accuracy scores.
  - Build `/dashboard/observability` page with trace inspector and latency histograms.
- **Database Changes (Forward Migration `0009`):**
  - Create `evaluation_datasets` table (`id`, `tenant_id`, `name`, `created_at`).
  - Create `evaluation_items` table (`id`, `dataset_id`, `query`, `expected_answer`, `expected_doc_ids`).
  - Create `evaluation_runs` table (`id`, `dataset_id`, `assistant_id`, `recall_score`, `faithfulness_score`, `avg_latency_ms`, `results_json`).
- **Security Implications:**
  - Evaluations and traces are tenant-scoped; no cross-tenant trace leakage. Sensitive prompts redacted from operational logs.
- **Tests:** Evaluation metric unit tests; Startup job recovery integration test.
- **Complexity:** High (4–5 days).

---

## 3. Sequenced Implementation Milestones

| Milestone | Workstreams | Core Deliverables | Target Complexity |
|---|---|---|---|
| **Milestone 06 (M06)** | **Workstreams A & B** | Complete Assistant Studio, Linear/Apple Notes design system, Creation Wizard, 12 Purpose Templates, Dual Simple/Advanced modes, Prompt versioning. | 1 Sprint |
| **Milestone 07 (M07)** | **Workstreams C & D** | Knowledge Studio enhancements, Chunk Inspector, Retrieval Playground, Multi-Provider BYOK (Anthropic, Gemini, Groq), Key Vault, Quotas. | 1 Sprint |
| **Milestone 08 (M08)** | **Workstreams E & F** | Enhanced Chat, Context pruning, Attachments, Web Widget, Public Share Link, Developer API keys. | 1 Sprint |
| **Milestone 09 (M09)** | **Workstream G** | Evaluation Studio, Trace Observability dashboard, Durable Job recovery, Cloud staging rehearsal. | 1 Sprint |
