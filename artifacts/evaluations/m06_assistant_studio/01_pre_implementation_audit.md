# M06 Pre-Implementation Audit & Architectural Verification Report

**Date:** 2026-11-08  
**Project:** Multi-Tenant AI Platform / CaaS  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Git Branch:** `main`  
**Verified Baseline HEAD:** `4f75f680250ae6b040e5d3c30bb13ac6fbe34a0f`  
**Working Tree Status:** Clean (untracked `docs/product/` from previous planning turn)  
**Alembic Head Migration:** `0005_add_assistant_byok_encrypted_key`  
**Test Suite State:** 170 passed, 18 skipped, 0 failed in 150.37s  

---

## 1. Verified Baseline & Architecture Facts

Direct source code inspection resolved the ten architectural questions:

| Question | Code Fact | Source Reference |
|---|---|---|
| **1. BYOK Encryption Algorithm** | **Fernet & MultiFernet** (AES-128-CBC + HMAC-SHA256 authenticated symmetric encryption), NOT AES-256-GCM. We preserve Fernet/MultiFernet to maintain 100% backward compatibility with encrypted keys. | [`backend/app/core/crypto.py:8-51`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/core/crypto.py#L8-L51) |
| **2. Real Assistant Schema** | `id`, `tenant_id`, `name`, `slug`, `description`, `default_model`, `llm_provider`, `temperature`, `max_tokens`, `visibility`, `retrieval_mode`, `top_k`, `system_prompt`, `status`, `byok_encrypted_key`, `created_at`, `updated_at`. | [`backend/app/models/assistant.py:14-31`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/models/assistant.py#L14-L31) |
| **3. Persisted Assistant Settings** | All generation and retrieval settings are columns on the `assistants` table. Migration `0005` added `byok_encrypted_key`. | [`backend/alembic/versions/0004_assistants_and_conversations.py`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/alembic/versions/0004_assistants_and_conversations.py) |
| **4. Tenant-Scoped KB Associations** | `assistant_knowledge_bases` has `tenant_id`, `assistant_id`, `knowledge_base_id` with composite unique constraint `uq_assistant_kb`. | [`backend/alembic/versions/0004_assistants_and_conversations.py:49-66`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/alembic/versions/0004_assistants_and_conversations.py#L49-L66) |
| **5. Assistant Authorization Enforcement** | Route-level permissions: `ASSISTANT_READ`, `ASSISTANT_CREATE`, `ASSISTANT_UPDATE`, `ASSISTANT_DELETE`, `ASSISTANT_EXECUTE` enforced via `require_permission()`. | [`backend/app/api/v1/assistants.py`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/api/v1/assistants.py), [`backend/app/api/deps.py`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/api/deps.py) |
| **6. Roles & Workspace Representation** | `SystemRole` enum (`tenant_owner`, `org_admin`, `assistant_manager`, `employee`, `viewer`). Resolved via JWT bearer token and verified against `tenant_memberships`. | [`backend/app/core/constants.py`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/core/constants.py), [`backend/app/api/deps.py`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/api/deps.py) |
| **7. Prompt Instruction Construction** | `build_rag_context` in `assistant_runtime/context.py` constructs messages with anti-injection framing and `<KNOWLEDGE_BASE_CONTEXT>` wrapper. | [`backend/app/assistant_runtime/context.py:37-126`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/assistant_runtime/context.py#L37-L126) |
| **8. Runtime Compatibility on Config Changes** | Conversations store only message text and citation metadata. Assistant runtime loads fresh assistant configuration per query, so configuration updates do not break existing conversations. | [`backend/app/assistant_runtime/runtime.py:74-91`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/assistant_runtime/runtime.py#L74-L91) |
| **9. Current Alembic Head** | `0005_add_assistant_byok_encrypted_key.py`. Forward migration `0006` is open. | [`backend/alembic/versions/0005_add_assistant_byok_encrypted_key.py`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/alembic/versions/0005_add_assistant_byok_encrypted_key.py) |
| **10. Frontend Routes Verification** | 15 routes pre-rendered cleanly. Login, Dashboard overview, Assistants chat drawer, Knowledge bases, Employees, Settings are functional. | Tested locally on Next.js Turbopack at `http://localhost:3000`. |

---

## 2. Existing Reusable Components

- **Backend:**
  - `AssistantRepository` (`backend/app/repositories/assistant_repository.py`)
  - `AssistantRuntime` (`backend/app/assistant_runtime/runtime.py`)
  - `AuditLogRepository` (`backend/app/repositories/audit_repository.py`)
  - `AssistantKnowledgeBase` mapping
  - `RoleRepository` and permission checkers
- **Frontend:**
  - `api.ts` client methods (`listAssistants`, `createAssistant`, `updateAssistant`, `deleteAssistant`, `streamChat`)
  - `auth-context.tsx` with active workspace switcher
  - Streaming SSE message consumer and citation viewer drawer

---

## 3. Actual Gaps for M06

1. **No Data-Driven Template Registry:** Assistants have no template system.
2. **Missing 5-Step Creation Wizard:** Creation is an 8-field side drawer with technical defaults.
3. **No Simple vs. Advanced Mode:** Technical jargon (Top-K, Hybrid RRF, Temperature) is exposed directly to beginners.
4. **No Version History Table in Migrations:** `AssistantVersion` was defined in SQLAlchemy models but missing from Alembic migration chain.
5. **No Version Snapshotting / Rollback:** Updating an assistant does not save snapshots, and there is no rollback endpoint.
6. **Prompt Hierarchy Needs Explicit Trust Layering:** Platform security → Organization policies → Assistant instructions → Untrusted retrieved knowledge.
7. **Optional Knowledge in Wizard:** Wizard must allow creating an assistant with zero uploaded files.

---

## 4. Planned Changes for M06

### Files to Modify
- `backend/app/models/assistant.py`: Add `tenant_id`, `config_snapshot`, `actor_id`, `change_summary` to `AssistantVersion`; add `template_id`, `audience_level`, `response_style`, `uncertainty_behavior`, `citation_style`, `current_version_num` to `Assistant`.
- `backend/app/schemas/assistant.py`: Add template, version, and rollback request/response schemas.
- `backend/app/repositories/assistant_repository.py`: Add version snapshotting on update and auditable rollback methods.
- `backend/app/api/v1/assistants.py`: Add version listing, version detail, rollback, and test preview endpoints.
- `backend/app/assistant_runtime/context.py`: Implement explicit 4-tier prompt trust hierarchy.
- `frontend/lib/api.ts`: Add template listing, version listing, and rollback client methods.
- `frontend/app/dashboard/assistants/page.tsx`: Integrate Creation Wizard, Simple/Advanced mode toggle, and version history.
- `frontend/app/globals.css`: Apply Linear × Apple Notes design tokens.

### New Files to Create
- `backend/alembic/versions/0006_assistant_versions_and_configuration.py`: Forward migration creating `assistant_versions` and adding configuration columns.
- `backend/app/templates/__init__.py`: Package init.
- `backend/app/templates/schema.py`: Pydantic schema for versioned templates.
- `backend/app/templates/registry.py`: Data-driven registry with all 12 initial templates.
- `backend/app/api/v1/templates.py`: REST router for listing and viewing templates.
- `frontend/app/dashboard/assistants/AssistantCreationWizard.tsx`: 5-step guided creation wizard (Purpose → Audience → Knowledge [Optional] → Behavior → Test).
- `frontend/app/dashboard/assistants/AssistantWorkspaceView.tsx`: Assistant detail workspace with tabs (Overview, Knowledge, Instructions/Behavior, Model, Retrieval, Test, Versions).
- `backend/tests/test_m06_assistant_studio.py`: Comprehensive test suite (regression, templates, wizard, simple/advanced, versions, rollback, security).

---

## 5. Security & Isolation Impact

- All template queries are read-only and public to authenticated tenant members.
- Assistant versions are strictly scoped by `tenant_id` and `assistant_id`.
- Rollback operations require `ASSISTANT_UPDATE` permission and create a new forward version (never delete historical records).
- Untrusted retrieved documents are strictly isolated inside `<KNOWLEDGE_BASE_CONTEXT>` and cannot override platform security instructions.

---

## 6. Execution Approval

The baseline is verified, all 10 architectural questions are grounded in source code facts, and changes are strictly confined to M06 scope. Proceeding to Stage 2: Backend Design & Implementation.
