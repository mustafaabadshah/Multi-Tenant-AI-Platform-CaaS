# M27.1 — Existing Architecture & Capability Audit
## Multi-Tenant AI Platform (CaaS) — Web Intelligence, Live URL Reading & Agentic Web Search

**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Git HEAD:** `c4b935b2a582c7c42dce3e81d716e93bcef9888d`  
**Branch:** `main`  
**Status:** Audit Completed  

---

### 1. Existing System Architecture Inventory

A rigorous audit of the current platform codebase was performed across all services, models, runtime layers, and frontend interfaces:

| Component | Current Implementation Path | Key Characteristics | Status for M27 |
| :--- | :--- | :--- | :--- |
| **AssistantRuntime** | `backend/app/assistant_runtime/runtime.py` | Orchestrates RAG context, BYOK resolution, tool discovery, streaming SSE, and agentic tool call loop. | **Reused:** Add first-party web tools to tool execution and SSE streaming. |
| **Context Assembly** | `backend/app/assistant_runtime/context.py` | Enforces 4-tier trust hierarchy: Platform Security (T1), Org Policy (T2), Assistant (T3), Untrusted Context (T4). | **Reused:** Untrusted web text will be placed strictly in T4 with prompt injection neutralization. |
| **Tool Registry** | `backend/app/services/tools/registry.py` | Discovers built-in and custom HTTP tools, enforces tenant boundaries, and executes tool calls. | **Reused:** Wire first-party web tools (`web_read_url`, `web_search`, `web_save_to_kb`). |
| **Built-in Tools** | `backend/app/services/tools/builtin.py` | Implements safe AST calculator and weather lookup. | **Extended:** Register M27 built-in tool definitions. |
| **SSRF Defense** | `backend/app/services/tools/ssrf.py` | Basic URL validation rejecting private IPs and metadata endpoints. | **Hardened:** Add redirect revalidation, DNS pinning, port restrictions, and decimal/IPv6 validation. |
| **Tool Approvals** | `backend/app/services/tools/approval_service.py` | Durable human-in-the-loop approval workflow for mutating actions (`risk_level="WRITE"`). | **Reused:** `web_save_to_kb` triggers this workflow for explicit user consent. |
| **Document Models** | `backend/app/models/knowledge.py` | `Document`, `DocumentVersion`, `DocumentChunk` with `metadata_json` and UUID PKs. | **Reused (Zero Migrations):** Existing schema can store web bookmarks and full content. |
| **Conversation Attachments** | `backend/app/models/conversation_attachment.py` | Scoped per-conversation documents with page indexing and chunk retrieval. | **Reused:** Temporary web context will follow similar conversation-scoped caching. |
| **Observability** | `backend/app/observability/tracer.py` | Traces tool calls, latencies, tokens, and errors in `tool_invocation_logs`. | **Reused:** Web tool executions will log timing, URLs, and token footprints. |
| **Frontend Chat UI** | `frontend/app/dashboard/conversations/page.tsx` | Streaming SSE, Voice modes, attachment drawer, citation chips, and approval cards. | **Extended:** Web source cards, URL detection in composer, and Save to KB action. |
| **Markdown Renderer** | `frontend/components/chat/MarkdownRenderer.tsx` | Clean GFM parser with TSV tables and interactive citation badges. | **Extended:** Clickable web citations opening verified external URLs. |

---

### 2. Capability Matrix & Gap Analysis

| Capability | Current Baseline | Missing Functionality | Impacted Files | Proposed Safe Change | Required Tests |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Direct URL Fetch** | None for arbitrary webpages. Custom HTTP tools only exist for predefined POST endpoints. | Outbound web page reader with safe size limits and timeout bounds. | `backend/app/services/web/reader.py` (new) | Implement `WebFetchService` with streaming size checks (2 MB) and polite User-Agent. | Valid HTTPS fetch, timeout, oversized page, 404/500 handling. |
| **SSRF Protection** | Basic IP resolution in `tools/ssrf.py`. | Redirect revalidation, DNS pinning against rebinding, port allowlist, decimal/IPv6 obfuscation checks. | `backend/app/services/web/ssrf.py` (new/hardened) | Comprehensive defense-in-depth validator with IP pinning and redirect re-checking. | 127.0.0.1, IPv6 loopback, RFC1918, 169.254.169.254, DNS rebinding, redirect to private IP, bad ports. |
| **Web Content Extraction** | None. (Ingestion exists only for PDF, DOCX, TXT, CSV). | HTML text extractor preserving headings, code blocks, lists, and tables while stripping nav/ads. | `backend/app/services/web/extractor.py` (new) | Deterministic CPU-friendly HTML parser converting tables to Markdown and code to fenced blocks. | Heading/code/table extraction, nav/script stripping, malformed HTML, JS-only page detection. |
| **Web Search** | None. Platform only searches internal vector/lexical indices. | Search provider abstraction with deterministic mock and real provider adapter. | `backend/app/services/web/search.py` (new) | Implement `WebSearchProvider`, `MockSearchProvider`, and `BraveSearchProvider`. | Mock search queries, provider failure handling, missing API key graceful message. |
| **Temporary Web Context** | Chat attachments are stored in B2/PostgreSQL. | Conversation-scoped in-memory/session web cache for follow-up questions. | `backend/app/services/web/context_store.py` (new) | In-memory conversation-scoped cache with 1-hour TTL keyed by `(tenant_id, conv_id, url)`. | Cache hit on follow-up, cache isolation between tenants/conversations. |
| **Web Citations** | Document citations only provide document name, page, and chunk ID. | Citations pointing to external URLs with domain, page title, and clickable link. | `backend/app/assistant_runtime/context.py`, `frontend/lib/api.ts` | Add `source_url` and `source_type` to citation schema and UI modal. | Citation payload validation, external link clickability in frontend. |
| **KB Web Source Save** | Attachments can be promoted to KB. No web source save exists. | Action to save web source as Reference Bookmark or Full Extracted Content. | `backend/app/services/web/kb_saver.py` (new) | Implement `WebKBSaveService` using existing `Document` model without schema migration. | Reference save, full content save, duplicate detection, cross-tenant rejection. |
| **Agentic Runtime Tools** | Builtin tools only have `calculator` and `weather_lookup`. | `web_read_url`, `web_search`, and `web_save_to_kb` not exposed to LLM. | `backend/app/services/tools/builtin.py`, `registry.py` | Register tool definitions with strict Pydantic schemas; mark `web_save_to_kb` as `WRITE`. | Tool discovery, LLM tool invocation, approval trigger on KB save. |
| **Prompt Injection Boundary** | `sanitize_untrusted_content` strips boundary tags. | Web text could contain adversarial prompt injection. | `backend/app/assistant_runtime/context.py` | Sanitize web text before feeding to LLM; enforce immutable platform security prompt in Tier 1. | Web text with "ignore instructions", "reveal secrets", "switch tenants". |

---

### 3. Database Schema Evaluation & Zero-Migration Decision

* **Current Alembic Revision:** `0017_m22_conversation_attachments`
* **Finding:** The existing `Document` table contains:
  * `filename: str` (Used for Web Page Title, e.g. "C++ For Loop - W3Schools")
  * `safe_filename: str`
  * `file_path: str` (Stores the canonical URL, e.g. `https://www.w3schools.com/cpp/cpp_for_loop.asp`)
  * `mime_type: str` (`text/html` or `application/x-web-source`)
  * `metadata_json: JSON` (Stores `{"source_type": "web", "source_url": "...", "mode": "REFERENCE"|"FULL_CONTENT", "domain": "..."}`)
  * `status: str` (`READY`)
  * Relationships to `DocumentVersion` (for extracted text and notes) and `DocumentChunk` (for vectorized chunks).
* **Decision:** **Zero database migrations required.** All web intelligence entities and provenance records fit cleanly into the existing PostgreSQL 16 schema. This guarantees staging stability and zero migration risk.
