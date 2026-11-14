# M10 Stage 2 — Assistant Lifecycle Audit Report

**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Milestone:** M10 Stage 2  
**Audit Scope:** End-to-End Assistant Lifecycle (Create → Configure → Add Knowledge → Select Model → Test → Publish → Manage → Update → Version → Rollback)  
**Date:** 2026-11-10  
**Status:** COMPLETE  

---

## 1. Executive Summary

This audit evaluates the end-to-end assistant lifecycle across the Multi-Tenant AI Platform (CaaS). The audit examined data models, repository abstractions, API routes, inference runtimes, publishing controllers, and user-facing frontend components in Next.js 16.

The platform architecture exhibits strong multi-tenant scoping and an immutable forward-versioning model. Prior to this milestone, a critical integration defect existed where `AssistantRepository` arbitrarily restricted configurable LLM providers to a 3-element set (`omniroute`, `openai`, `mock`), blocking registered providers `anthropic`, `gemini`, and `groq` from persistence despite backend adapters being present. Furthermore, sandbox preview inference (`/api/v1/assistants/preview-test`) lacked the strict BYOK credential check enforced in standard chat runtime (`stream_chat`), presenting a risk of unintended provider invocation. Both defects were identified and resolved in Stage 2.

---

## 2. Assistant Lifecycle Matrix

The table below documents the lifecycle capabilities across backend models, service layers, REST APIs, frontend UI components, test coverage, and decisions:

| Lifecycle Capability | Existing Implementation | API Endpoint | UI Component | Automated Tests | Decision |
|---|---|---|---|---|---|
| **Create Assistant** | `AssistantRepository.create_assistant` with UUID PK and automatic Version 1 snapshot | `POST /api/v1/assistants` | `AssistantCreationWizard.tsx` (5-step modal) & `page.tsx` | `test_01`, `test_02`, `test_05` | Verified. Supports individual and organization workspaces. |
| **Select Template** | `TemplateRegistry` (12 data-driven blueprints across Education, Business, Personal, Domain) | `GET /api/v1/templates`, `GET /api/v1/templates/{id}` | `AssistantCreationWizard.tsx` (Step 1 grid with category filters) | `test_03`, `test_m06_assistant_studio.py` | Verified. Template selection initializes real parameters, not labels. |
| **Configure Audience** | `Assistant.audience_level` (`general`, `school`, `undergraduate`, `employees`, `customers`, `researchers`) | `POST /api/v1/assistants`, `PUT /api/v1/assistants/{id}` | Wizard Step 2 & Workspace "Instructions & Behavior" tab | `test_03`, `test_05` | Verified. Persisted and applied in prompt context. |
| **Configure Behavior** | `response_style`, `uncertainty_behavior`, `citation_style`, `system_prompt` | `POST /api/v1/assistants`, `PUT /api/v1/assistants/{id}` | Wizard Step 4 (Simple mode) & Workspace "Instructions" tab | `test_03`, `test_04`, `test_05` | Verified. Bound to 4-tier prompt safety hierarchy. |
| **Attach Knowledge** | `AssistantKnowledgeBase` junction table with tenant-scoped validation | `POST /api/v1/assistants`, `PUT /api/v1/assistants/{id}` | Wizard Step 3 & Workspace "Knowledge Bases" tab | `test_06`, `test_07` | Verified. Empty document allowlists fail closed; cross-tenant KBs rejected with HTTP 400. |
| **Select Provider/Model** | `LLMProviderRegistry` + `ModelCapabilityRegistry` (`omniroute`, `openai`, `anthropic`, `gemini`, `groq`, `mock`) | `POST /api/v1/assistants`, `PUT /api/v1/assistants/{id}` | Wizard Step 4 (Advanced mode) & Workspace "Model & Retrieval" tab | `test_08`, `test_m10_stage2_assistant_lifecycle.py` | Fixed. Expanded `VALID_ASSISTANT_PROVIDERS` to encompass all registered providers. |
| **Test in Sandbox** | `AssistantRuntime.stream_preview` (ephemeral live SSE preview without DB persistence) | `POST /api/v1/assistants/preview-test` | Wizard Step 5 & Main Chat Sandbox (`viewMode="chat"`) | `test_09`, `test_10`, `test_11` | Fixed. Added strict BYOK check to preview runtime matching production chat. |
| **Publish/Share** | `PublishingService.publish_assistant` with 128-bit CSPRNG `public_id` | `POST /api/v1/assistants/{id}/publish` | Workspace "Publish & Embed" tab (`PublishTab.tsx`) | `test_15`, `test_m08_publishing_and_api_keys.py` | Verified. Supports `PUBLIC`, `WORKSPACE`, domain restrictions, and embed widgets. |
| **Edit Assistant** | `AssistantRepository.update_assistant` with differential field updates | `PUT /api/v1/assistants/{id}` | Workspace Studio tabs with "Save Changes" action | `test_04`, `test_05`, `test_12` | Verified. Auto-increments version and preserves snapshots. |
| **Create Version** | `AssistantVersion` records with JSON config snapshot, actor ID, and summary | Automatic on `create_assistant` and `update_assistant` | Workspace "Version History" tab | `test_12`, `test_13` | Verified. Strict forward-incrementing version schema. |
| **View Version History** | `AssistantRepository.list_versions` sorted by `version_num DESC` | `GET /api/v1/assistants/{id}/versions` | Workspace "Version History" tab with snapshot inspection | `test_13` | Verified. Displays version number, actor, timestamp, diff summary. |
| **Rollback** | `AssistantRepository.rollback_to_version` (creates new $V+1$ snapshot) | `POST /api/v1/assistants/{id}/rollback` | Workspace "Version History" tab "Rollback" trigger | `test_14` | Verified. Immutable rollback: restores config without deleting historical records. |
| **Archive/Delete** | `TenantScopedRepository.delete` with cascading entity cleanup | `DELETE /api/v1/assistants/{id}` | Assistant list / Workspace menu with confirmation dialog | `test_17`, `test_18` | Verified. Scoped to active tenant; cascades versions, prompts, and memberships. |

---

## 3. Deep Dive Findings & Integrations

### 3.1 Defect 1: Provider Validation Whitelist in Assistant Repository
- **File:** `backend/app/repositories/assistant_repository.py` lines 76 and 207
- **Root Cause:** A hardcoded set `valid_providers = {"omniroute", "openai", "mock"}` rejected user attempts to configure `anthropic`, `gemini`, or `groq`, raising `ValueError: Unsupported LLM provider`.
- **Resolution:** Replaced with module-level constant `VALID_ASSISTANT_PROVIDERS = {"omniroute", "openai", "anthropic", "gemini", "groq", "mock"}` synchronized with `LLMProviderRegistry`. Added matching option elements in `AssistantCreationWizard.tsx` and `AssistantWorkspaceView.tsx`.

### 3.2 Defect 2: Strict BYOK Enforcement in Ephemeral Preview Sandbox
- **File:** `backend/app/assistant_runtime/runtime.py` line 439 (`stream_preview`)
- **Root Cause:** Unlike `stream_chat` (which checked lines 229-237 for commercial providers without tenant credentials), `stream_preview` proceeded with `api_key=None`, risking unexpected outbound requests or confusing HTTP 500 errors.
- **Resolution:** Added the strict BYOK verification to `stream_preview`:
  ```python
  resolved_key, resolved_base_url = await byok_svc.resolve_plaintext_key(llm_provider)
  if llm_provider in ("openai", "anthropic", "gemini", "groq") and not resolved_key:
      err_msg = (
          f"Provider '{llm_provider}' is not configured with an active BYOK credential for this workspace. "
          f"Please add your API key under Providers & Keys."
      )
      yield format_sse("message_error", {"error": err_msg})
      return
  ```

### 3.3 Defect 3: Hybrid Search Graceful Degradation on Offline Embedding Gateway
- **File:** `backend/app/retrieval/service.py` lines 145-155
- **Root Cause:** In hybrid retrieval, if the embedding gateway on localhost:20128 was offline, semantic search raised an unhandled `TimeoutError`, crashing user chat despite lexical candidates having already been gathered.
- **Resolution:** Wrapped semantic search phase in a `try...except` block that logs a warning and falls back to lexical candidates via Reciprocal Rank Fusion ($RRF$). Additionally, updated `backend/app/embeddings/providers/openai_provider.py` to fast-fail on localhost connection refused.

---

## 4. Verification Conclusion

All 13 lifecycle capabilities are fully backed by robust database models, tenant-isolated API routes, interactive frontend UI, and automated tests.
