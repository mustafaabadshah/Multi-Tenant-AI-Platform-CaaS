# Milestone 04 — Assistant Runtime & Conversational RAG Report

**Milestone:** M04  
**Status:** `PASS`  
**Execution Date:** 2026-11-07  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Git Branch:** `main`  
**Design Aesthetic:** Linear × Apple Notes  

---

## 1. Executive Summary

Milestone 04 delivers the assistant orchestration and conversational RAG capability on top of the verified multi-tenant knowledge and retrieval infrastructure.

Users can create, configure, and manage purpose-built AI assistants, connect authorized knowledge bases, select their LLM provider (OmniRoute, OpenAI BYOK, or deterministic Mock), and engage in real-time streaming conversations via Server-Sent Events (SSE). Responses are strictly grounded in authorized internal documentation with stable citation references (`[1]`, `[2]`), and access permissions are revalidated at execution time.

---

## 2. Logical Architecture & Module Organization

The assistant runtime adheres strictly to the modular monolith design:

```
User Interface (Next.js 16)
   │
   ▼  SSE Request (POST /api/v1/conversations/{id}/messages/stream)
Assistant API (`app/api/v1/assistants.py` & `app/api/v1/conversations.py`)
   │
   ▼
Assistant Runtime (`app/assistant_runtime/runtime.py`)
   ├── 1. Tenant & Conversation Security Validation
   ├── 2. Execution-Time KB & Document Authorization Re-check
   ├── 3. Retrieval Service (`app/retrieval/service.py`) [Hybrid RRF / Semantic / Lexical]
   ├── 4. RAG Context Builder (`app/assistant_runtime/context.py`) [Token Budget & Anti-Injection]
   ├── 5. LLM Provider Gateway (`app/llm/`) [OmniRoute / OpenAI / Mock]
   ├── 6. SSE Event Streaming (`message_start` → `token` → `citation` → `usage` → `message_complete`)
   └── 7. Relational Persistence (`Message`, `MessageCitation` with chunk UUIDs)
```

### New Backend Modules
1. **`app/models/assistant.py` & `app/models/conversation.py`:**
   - Extended `Assistant` with `llm_provider`, `temperature`, `max_tokens`, `visibility`, `retrieval_mode`, `top_k`.
   - Added `AssistantKnowledgeBase` composite association entity.
   - Enforced `TenantScopedMixin` across `Conversation`, `Message`, and `MessageCitation`.
2. **`alembic/versions/0004_assistants_and_conversations.py`:**
   - Database migration establishing assistant settings, conversations, messages, citations, and composite indexes.
3. **`app/llm/` (Universal Provider Gateway):**
   - `base.py`: Provider interface, message dataclasses, streaming chunk dataclasses.
   - `providers/openai_provider.py`: Universal adapter for OmniRoute (`http://localhost:20128/v1`) and OpenAI BYOK.
   - `providers/mock_provider.py`: Deterministic offline testing provider with realistic token streaming and source grounding.
   - `registry.py`: Singleton provider registry.
4. **`app/assistant_runtime/` (Conversational RAG):**
   - `context.py`: Token budgeting, history pruning, and prompt injection isolation wrapping retrieved chunks within `<KNOWLEDGE_BASE_CONTEXT>`.
   - `runtime.py`: Execution-time reauthorization, retrieval orchestration, SSE streaming formatting, and atomic relational persistence.
5. **`app/api/v1/conversations.py`:**
   - Endpoints for creating conversations, listing message history with citations, and SSE streaming chat.

---

## 3. Data Model & Migration `0004`

| Table | Primary Key | Foreign Keys / Constraints | Purpose |
|---|---|---|---|
| `assistants` | `id` (UUID) | `tenant_id` (CASCADE), `uq_assistant_tenant_slug` | Stores agent persona, model, provider, temperature, and prompt. |
| `assistant_knowledge_bases` | `id` (UUID) | `tenant_id`, `assistant_id`, `knowledge_base_id`, `uq_assistant_kb` | M:N association linking assistants to authorized knowledge bases. |
| `conversations` | `id` (UUID) | `tenant_id`, `assistant_id`, `user_id` | Thread container for chat interactions. |
| `messages` | `id` (UUID) | `tenant_id`, `conversation_id` (CASCADE) | User questions and assistant responses with token count. |
| `message_citations` | `id` (UUID) | `tenant_id`, `message_id` (CASCADE), `chunk_id` | Provenance links to source documents, chunk UUIDs, and snippets. |

---

## 4. Prompt Injection & Security Defense

Retrieved documents and user inputs are strictly isolated:
1. **Untrusted Boundary Delimiters:** Retrieved chunks are wrapped inside explicit `<KNOWLEDGE_BASE_CONTEXT>` XML tags with explicit instructions forbidding the LLM from executing commands found within the documents.
2. **Execution-Time Reauthorization:** Before executing retrieval, the runtime verifies:
   - The conversation belongs to the active tenant.
   - The connected knowledge bases are active and owned by the tenant.
   - Deleted documents (`status == 'DELETED'`) are strictly excluded.
   - Department restrictions are enforced server-side.
3. **Cross-Tenant Isolation:** All endpoints enforce `WHERE id = :id AND tenant_id = :tenant_id`. Guessed UUIDs from other tenants yield immediate `HTTP 404`.

---

## 5. Streaming Event Protocol (Server-Sent Events)

The streaming endpoint (`POST /api/v1/conversations/{id}/messages/stream`) adheres to the standard W3C SSE format:

| Event Type | Payload Fields | Description |
|---|---|---|
| `message_start` | `conversation_id`, `assistant_id`, `assistant_name` | Sent upon session authorization. |
| `retrieval_start` | `connected_kb_count` | Notifies frontend that retrieval search has commenced. |
| `retrieval_complete` | `citation_count`, `citations` | Emits resolved citation metadata (document title, page, snippet). |
| `token` | `delta` | Streamed text token delta for real-time rendering. |
| `usage` | `input_tokens`, `output_tokens`, `duration_ms`, `model` | Generation token metrics and latency. |
| `message_complete` | `message_id`, `conversation_id`, `status` | Sent when generation finishes and database persistence completes. |
| `message_error` | `error` | Emitted on network or provider failure without leaking secrets. |

---

## 6. Frontend Chat Experience (Linear × Apple Notes)

The interface in `frontend/app/dashboard/assistants/page.tsx` delivers a focused, distraction-free environment:
- **Left Panel:** Assistant picker, quick status badges, conversation history list, and "+ New Chat" button.
- **Main Chat:** Clean typography, streaming assistant bubbles, clickable citation chips (`[1]`, `[2]`), copy response button, auto-scrolling, and stop generation control.
- **Citation Drawer:** Clicking any citation chip opens a modal displaying the exact document title, page number, and source snippet.
- **Assistant Configuration Drawer:** Slide-out editor for configuring name, description, LLM provider, model, temperature, connected knowledge bases, retrieval mode, and system instructions.

---

## 7. Automated Test Suite Results

The dedicated M04 test suite (`backend/tests/test_assistants_and_rag.py`) passed 100%:

| Test Name | Type | Result |
|---|---|---|
| `test_assistant_crud_lifecycle` | API / Repository | **PASSED** |
| `test_cross_tenant_assistant_isolation` | Security / Multi-Tenant | **PASSED** |
| `test_cross_tenant_conversation_isolation` | Security / Multi-Tenant | **PASSED** |
| `test_rag_context_builder_budgeting_and_boundaries` | Unit / Prompt Security | **PASSED** |
| `test_end_to_end_conversational_rag_with_citations` | End-to-End RAG | **PASSED** |

### Complete Repository Regression
- **Full Backend Pytest Suite:** **70 passed** in 105.54s (0:01:45).
- **Ruff Linter:** Clean (0 errors).
- **Frontend ESLint:** Clean (0 errors).
- **Next.js Production Build:** 15/15 routes compiled and prerendered cleanly.

---

## 8. M04 Acceptance Sign-Off

- Assistant CRUD & KB associations: **PASS**
- LLM Provider Gateway (OmniRoute, OpenAI BYOK, Mock): **PASS**
- Conversational RAG with Context Manager & Token Budgeting: **PASS**
- Execution-time Authorization: **PASS**
- SSE Streaming Event Protocol: **PASS**
- Citation Provenance with real chunk UUIDs: **PASS**
- Linear × Apple Notes Frontend Chat: **PASS**
- Security Matrix (cross-tenant assistant & chat isolation): **PASS**
- **Status:** **MILESTONE 04 COMPLETE AND VERIFIED**.
