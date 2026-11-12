# M10 Git Integration - Stage 1: Change Ownership & Dependency Audit

- **Timestamp (UTC):** 2026-11-12T07:12:06Z (same working-tree snapshot as Stage 0)
- **Repository:** `E:\MM Office\Multi-Tanant-CaaS`
- **Branch / HEAD:** `main` / `9479847b846aaae43cb8f51e81cf18aaf2646d0f`
- **Baseline:** 68 modified tracked + 134 untracked files = **202 files classified**
- **Post-snapshot:** 2 concurrent sibling documents appeared after the snapshot (section 6.1), bringing observed non-audit files to **204**
- **git state:** `M` = modified tracked (unstaged), `??` = untracked. Staged = 0, deleted = 0.
- **Primary-group rule:** every file appears exactly once. Secondary ownership is noted where a change also serves another group.

### Group key

| Group | Scope |
|---|---|
| **A** | M09 security/evaluation/observability/background recovery/storage/quota/BYOK/conversations implementation + `0009` migration |
| **B** | M10 UI/product integration (frontend design system, pages, chat/markdown/citations, SDK TypeScript; backend product APIs for assistant/knowledge/retrieval) |
| **C** | M10 remediation/security configuration (`core/cors.py`, `main.py`, `config.py`, storage validation/S3, employees page, `.dockerignore`, env templates, `render.yaml`, `pyproject.toml`, remediation tests) |
| **D** | Migrations/database alignment (`alembic/env.py`, `0003`, `0009`, `0010`, models touched for migration parity) |
| **E** | Tests and quality gates (all new/updated tests except the three remediation tests owned by C) |
| **F** | Documentation and evidence (`docs/**`, `artifacts/**`) |

Tie-break decisions:

1. `0009_m09_security_and_evaluation.py` is **A primary / D secondary**: it is an M09 feature migration and the parent of `0010`.
2. `0010_m10_remediation_schema_alignment.py` is **D primary / A secondary**: it is remediation-era schema alignment but belongs to the migration chain.
3. The three `test_remediation_stage*.py` files are **C primary / E secondary** because group C explicitly owns remediation tests; they are the only test files not primary in E.
4. Backend product APIs for knowledge, assistant provider validation, and retrieval fallback are **B** (M10 product integration), with A dependency notes where they touch M09 services.

---

## 1. Group A - M09 implementation + 0009 (31 files: 20 M + 11 ??)

| File | State | Group | Dependency notes | Needed with |
|---|---|---|---|---|
| `backend/app/api/v1/conversations.py` | M | A | Conversation rename/status PATCH used by M10 Stage 4 chat canvas (also documented in the M09 UX report); secondary B | `schemas/assistant.py`, `frontend/lib/api.ts` |
| `backend/app/api/v1/developer.py` | M | A | Enforces assistant-scoped developer API keys; secondary E | `services/api_key_service.py`, `models/publishing.py`, `0009` |
| `backend/app/api/v1/ingestion.py` | M | A | Retry/cancel now syncs `Document.status` with job state (background recovery) | `services/ingestion/recovery.py` |
| `backend/app/api/v1/public_chat.py` | M | A | Deterministic session -> conversation binding | `services/publishing_service.py`, `0009` |
| `backend/app/api/v1/router.py` | M | A | Mounts evaluation and observability routers (import-order cleanup included) | `api/v1/evaluation.py`, `api/v1/observability.py` |
| `backend/app/assistant_runtime/runtime.py` | M | A | Quota reservation, tracing spans, strict BYOK, failure-message persistence, normalized markdown output; secondary B | `observability/tracer.py`, `services/quota_service.py`, `markdown_normalizer.py` |
| `backend/app/embeddings/providers/openai_provider.py` | M | A | Stops retry storms against localhost embedding endpoints | - |
| `backend/app/llm/base.py` | M | A | Adds `extra_headers` to `LLMConfig` | `llm/providers/*` |
| `backend/app/llm/capabilities.py` | M | A | Groq GPT-OSS 120B catalog entry and descriptions | `llm/providers/groq_provider.py` |
| `backend/app/llm/providers/groq_provider.py` | M | A | `auto` resolves to a concrete Groq model (`openai/gpt-oss-120b`) | `llm/capabilities.py` |
| `backend/app/llm/providers/openai_provider.py` | M | A | Fail-fast on missing key, normalized provider errors, extra headers | `llm/base.py` |
| `backend/app/models/__init__.py` | M | A | Registers `EvalDataset`, `EvalDatasetItem`, `EvalRun`, `EvalRunResult`; secondary D | `models/evaluation.py`, `0009` |
| `backend/app/models/publishing.py` | M | A | Adds `APIKey.assistant_id` and `PublicChatSession.conversation_id`; secondary D | `0009` |
| `backend/app/schemas/assistant.py` | M | A | Adds `ConversationUpdateRequest`; secondary B | `api/v1/conversations.py`, `frontend/lib/api.ts` |
| `backend/app/schemas/publishing.py` | M | A | API-key `assistant_id` contract | `services/api_key_service.py`, `0009` |
| `backend/app/services/api_key_service.py` | M | A | Assistant restriction enforcement + `assistant:eval` scope | `schemas/publishing.py`, `0009` |
| `backend/app/services/byok_vault.py` | M | A | Validates credential on creation, prefers HEALTHY credentials | `tests/test_quota_and_byok_policy.py` |
| `backend/app/services/publishing_service.py` | M | A | 128-bit public IDs, session expiry/binding | `api/v1/public_chat.py`, `0009` |
| `backend/app/services/quota_service.py` | M | A | In-flight reservations; removes `daily_request_limit`; secondary D | `0010` (drops column), `runtime.py` |
| `backend/app/vectorstores/qdrant_store.py` | M | A | Returns early for empty `document_ids` filter; secondary B | `retrieval/service.py` |
| `backend/alembic/versions/0009_m09_security_and_evaluation.py` | ?? | A | Adds `api_keys.assistant_id`, `public_chat_sessions.conversation_id`, four `eval_*` tables; parent of 0010; secondary D | `models/publishing.py`, `models/evaluation.py`, `0010` |
| `backend/app/api/v1/evaluation.py` | ?? | A | Evaluation REST API | `models/evaluation.py`, `schemas/evaluation.py`, `services/evaluation_service.py` |
| `backend/app/api/v1/observability.py` | ?? | A | Trace/observability REST API (M09 UI consumes it) | `observability/tracer.py`, `router.py` |
| `backend/app/evaluation/judge.py` | ?? | A | LLM-as-judge scoring | `services/evaluation_service.py` |
| `backend/app/evaluation/metrics.py` | ?? | A | Deterministic retrieval/answer metrics | `services/evaluation_service.py` |
| `backend/app/evaluation/starter_benchmarks.py` | ?? | A | Starter benchmark datasets | `services/evaluation_service.py`, `0009` |
| `backend/app/models/evaluation.py` | ?? | A | Evaluation ORM; tables created by 0009; secondary D | `0009`, `models/__init__.py` |
| `backend/app/observability/tracer.py` | ?? | A | In-process trace/span recorder | `runtime.py`, `api/v1/observability.py` |
| `backend/app/schemas/evaluation.py` | ?? | A | Evaluation request/response contracts | `api/v1/evaluation.py` |
| `backend/app/services/evaluation_service.py` | ?? | A | Evaluation orchestration | `evaluation/{judge,metrics,starter_benchmarks}.py` |
| `backend/app/services/ingestion/recovery.py` | ?? | A | Startup recovery for orphaned ingestion/embedding jobs | `main.py` lifespan |
---

## 2. Group B - M10 UI/product integration (48 files: 32 M + 16 ??)

| File | State | Group | Dependency notes | Needed with |
|---|---|---|---|---|
| `backend/app/assistant_runtime/__init__.py` | M | B | Exports `normalize_markdown`; secondary A | `markdown_normalizer.py` |
| `backend/app/assistant_runtime/context.py` | M | B | Prompt adds Markdown formatting + no-bibliography citation rules; secondary E | `markdown_normalizer.py`, `test_m05_prompt_injection.py` |
| `backend/app/api/v1/knowledge.py` | M | B | M10 Stage 3 KB PATCH + live document count | `repositories/knowledge_repository.py` |
| `backend/app/repositories/assistant_repository.py` | M | B | M10 Stage 2 provider whitelist (`omniroute`, `openai`, `anthropic`, `gemini`, `groq`, `mock`) | `tests/test_m10_stage2_assistant_lifecycle.py` |
| `backend/app/repositories/knowledge_repository.py` | M | B | M10 Stage 3 KB update/count queries | `api/v1/knowledge.py` |
| `backend/app/retrieval/service.py` | M | B | Lexical fallback + actual-mode diagnostics; secondary A | `vectorstores/qdrant_store.py`, `tests/test_m10_stage3_knowledge_and_retrieval.py` |
| `frontend/app/dashboard/assistants/AssistantCreationWizard.tsx` | M | B | M10 design system + wizard flow | `components/ui/*`, `lib/api.ts` |
| `frontend/app/dashboard/assistants/AssistantWorkspaceView.tsx` | M | B | M10 workspace UI | `components/ui/*`, `lib/api.ts` |
| `frontend/app/dashboard/assistants/PublishTab.tsx` | M | B | Publishing/deployment UI | `lib/api.ts` |
| `frontend/app/dashboard/assistants/page.tsx` | M | B | Assistant list/studio page | `components/ui/*`, `lib/api.ts` |
| `frontend/app/dashboard/audit/page.tsx` | M | B | Audit log UI | `components/ui/*`, `lib/api.ts` |
| `frontend/app/dashboard/departments/page.tsx` | M | B | Departments UI | `components/ui/*`, `lib/api.ts` |
| `frontend/app/dashboard/groups/page.tsx` | M | B | Employee groups UI | `components/ui/*`, `lib/api.ts` |
| `frontend/app/dashboard/knowledge/IndexStatusTab.tsx` | M | B | Ingestion/index status UI | `lib/api.ts` |
| `frontend/app/dashboard/knowledge/RetrievalPreviewTab.tsx` | M | B | Retrieval preview UI | `lib/api.ts` |
| `frontend/app/dashboard/knowledge/RetrievalSettingsTab.tsx` | M | B | Retrieval settings UI | `lib/api.ts` |
| `frontend/app/dashboard/knowledge/page.tsx` | M | B | Knowledge Studio page | `components/ui/*`, `lib/api.ts` |
| `frontend/app/dashboard/layout.tsx` | M | B | Sidebar/nav design system, conversation/observability routes | `components/ui/*`, `lib/api.ts` |
| `frontend/app/dashboard/page.tsx` | M | B | Dashboard overview | `components/ui/*`, `lib/api.ts` |
| `frontend/app/dashboard/providers/page.tsx` | M | B | Providers/keys UI | `components/ui/*`, `lib/api.ts` |
| `frontend/app/dashboard/settings/DeveloperApiKeysSection.tsx` | M | B | API-key scoping UI (A backend) | `lib/api.ts`, `schemas/publishing.py` |
| `frontend/app/dashboard/settings/page.tsx` | M | B | Settings page | `components/ui/*`, `lib/api.ts` |
| `frontend/app/dashboard/workspace/page.tsx` | M | B | Workspace settings UI | `components/ui/*`, `lib/api.ts` |
| `frontend/app/embed/[publicId]/page.tsx` | M | B | Embed widget UI | `lib/api.ts` |
| `frontend/app/globals.css` | M | B | Design tokens/theme shared by all pages | all frontend pages |
| `frontend/app/layout.tsx` | M | B | Root layout/theme shell | `globals.css` |
| `frontend/app/login/page.tsx` | M | B | Auth UI redesign | `lib/api.ts`, `components/ui/*` |
| `frontend/app/p/[publicId]/page.tsx` | M | B | Public chat page | `lib/api.ts`, `components/chat/MarkdownRenderer.tsx` |
| `frontend/app/page.tsx` | M | B | Landing page | `globals.css` |
| `frontend/app/register/page.tsx` | M | B | Registration UI | `lib/api.ts`, `components/ui/*` |
| `frontend/lib/api.ts` | M | B | API client for conversations, traces, evaluation, citations, streaming callbacks | all modified pages, `components/*`, `sdk/typescript/src/index.ts` |
| `sdk/typescript/src/index.ts` | M | B | TypeScript SDK hardening/contract update | `api/v1/developer.py`, `api/v1/public_chat.py` |
| `frontend/app/dashboard/assistants/EvaluationTab.tsx` | ?? | B | Evaluation UI | `lib/api.ts`, `api/v1/evaluation.py` |
| `frontend/app/dashboard/conversations/page.tsx` | ?? | B | M10 Stage 4 first-class conversation canvas | `MarkdownRenderer.tsx`, `lib/citations.ts`, `lib/api.ts` |
| `frontend/app/dashboard/observability/page.tsx` | ?? | B | Observability UI for M09 trace API (product integration) | `lib/api.ts`, `api/v1/observability.py` |
| `frontend/components/chat/MarkdownRenderer.tsx` | ?? | B | Safe Markdown + citation rendering | `lib/citations.ts`, conversations page |
| `frontend/components/ui/Badge.tsx` | ?? | B | Design-system primitive | all pages, `ui/index.ts` |
| `frontend/components/ui/Button.tsx` | ?? | B | Design-system primitive | all pages, `ui/index.ts` |
| `frontend/components/ui/Card.tsx` | ?? | B | Design-system primitive | all pages, `ui/index.ts` |
| `frontend/components/ui/ConfirmModal.tsx` | ?? | B | Design-system primitive | conversations/settings pages, `ui/index.ts` |
| `frontend/components/ui/EmptyState.tsx` | ?? | B | Design-system primitive | all pages, `ui/index.ts` |
| `frontend/components/ui/Input.tsx` | ?? | B | Design-system primitive | all pages, `ui/index.ts` |
| `frontend/components/ui/Modal.tsx` | ?? | B | Design-system primitive | conversations/settings pages, `ui/index.ts` |
| `frontend/components/ui/Spinner.tsx` | ?? | B | Design-system primitive | all pages, `ui/index.ts` |
| `frontend/components/ui/StatusIndicator.tsx` | ?? | B | Design-system primitive | knowledge/observability pages, `ui/index.ts` |
| `frontend/components/ui/index.ts` | ?? | B | Barrel export for UI primitives | all frontend pages importing `components/ui` |
| `backend/app/assistant_runtime/markdown_normalizer.py` | ?? | B | Markdown de-escaping/merge logic; secondary A | `context.py`, `runtime.py`, `tests/test_markdown_normalizer.py` |
| `frontend/lib/citations.ts` | ?? | B | Citation parsing/tray helpers | `MarkdownRenderer.tsx`, conversations page |
---

## 3. Group C - M10 remediation/security configuration (15 files: 9 M + 6 ??)

| File | State | Group | Dependency notes | Needed with |
|---|---|---|---|---|
| `.env.example` | M | C | CORS dev/opt-in variables | `backend/app/core/cors.py` |
| `.env.production.example` | M | C | Production fail-closed CORS + S3 storage template (STOR-1) | `storage/__init__.py`, `render.yaml` |
| `backend/app/core/config.py` | M | C | `ALLOW_DEV_LAN_ORIGINS`, `S3_*` settings, dual `.env` lookup | `core/cors.py`, `storage/*` |
| `backend/app/main.py` | M | C | `create_app()` factory, centralized CORS, storage pre-flight, startup recovery; secondary A | `core/cors.py`, `storage/__init__.py`, `services/ingestion/recovery.py`, `api/v1/router.py` |
| `backend/app/storage/__init__.py` | M | C | Fail-closed storage validation + provider factory (STOR-1) | `core/config.py`, env templates, `storage/s3.py` |
| `backend/app/storage/s3.py` | M | C | Traversal-safe tenant-prefixed keys; lazy `aioboto3` | `pyproject.toml` (`aioboto3`) |
| `backend/pyproject.toml` | M | C | Declares `aioboto3>=12.4.0` and `fastembed>=0.3.0` (D5, C2) | `storage/s3.py`, `embeddings/providers/sentence_transformer_provider.py` |
| `render.yaml` | M | C | Render blueprint switches to S3 storage + S3 env keys | `storage/__init__.py`, `.env.production.example` |
| `frontend/app/dashboard/employees/page.tsx` | M | C | SEC-1 fix: invite dropdown restored to canonical roles; secondary B | `tests/test_remediation_stage2_invitation_roles.py` |
| `backend/.dockerignore` | ?? | C | Build-context exclusions (secrets/local state) | `backend/Dockerfile` build |
| `backend/app/core/cors.py` | ?? | C | Centralized CORS policy; imported by `main.py` | `main.py`, `config.py`, CORS tests |
| `backend/tests/test_remediation_stage1_cors.py` | ?? | C | D11 regression (10 tests); secondary E | `core/cors.py`, `main.py` |
| `backend/tests/test_remediation_stage2_invitation_roles.py` | ?? | C | SEC-1 regression (15 tests); secondary E | `employees/page.tsx` |
| `backend/tests/test_remediation_stage3_storage.py` | ?? | C | STOR-1 storage validation/key-safety (11 tests); secondary E | `storage/__init__.py`, `storage/s3.py` |
| `frontend/.dockerignore` | ?? | C | Build-context exclusions (node_modules/.env) | `frontend/Dockerfile` build |

---

## 4. Group D - Migrations/database alignment (3 files: 2 M + 1 ??)

| File | State | Group | Dependency notes | Needed with |
|---|---|---|---|---|
| `backend/alembic/env.py` | M | D | Adds `render_as_batch=True` and SQLite URL normalization so 0003/0010 work on SQLite | `0003`, `0010` |
| `backend/alembic/versions/0003_embeddings_and_vector_stores.py` | M | D | MIG-1: dialect-aware FK create/drop via batch mode for SQLite; PostgreSQL path preserved | `alembic/env.py` |
| `backend/alembic/versions/0010_m10_remediation_schema_alignment.py` | ?? | D | Creates nine model tables + missing indexes, drops unused `tenant_quotas.daily_request_limit`; secondary A | `0009` (parent), `models/__init__.py`, `services/quota_service.py` |

---

## 5. Group E - Tests and quality gates (16 files: 4 M + 12 ??)

| File | State | Group | Dependency notes | Needed with |
|---|---|---|---|---|
| `backend/tests/test_m05_prompt_injection.py` | M | E | Expectation update for new security/formatting prompt; secondary B | `assistant_runtime/context.py` |
| `backend/tests/test_m05_provider_reliability.py` | M | E | Strict BYOK + persisted error message expectations; secondary A | `assistant_runtime/runtime.py` |
| `backend/tests/test_m05_staging_readiness.py` | M | E | Production CORS policy expectation; secondary C | `main.py`, `core/cors.py` |
| `backend/tests/test_m08_publishing_and_api_keys.py` | M | E | API-key assistant scoping and publication security; secondary A | `services/api_key_service.py`, `models/publishing.py` |
| `backend/tests/test_background_recovery.py` | ?? | E | M09 background recovery; secondary A | `services/ingestion/recovery.py` |
| `backend/tests/test_conversations_ux.py` | ?? | E | Conversation rename/lifecycle + cross-tenant; secondary A | `api/v1/conversations.py` |
| `backend/tests/test_evaluation.py` | ?? | E | Evaluation backend; secondary A | `app/evaluation/*`, `api/v1/evaluation.py`, `0009` |
| `backend/tests/test_groq_and_api_hardening.py` | ?? | E | Groq auto-model + provider hardening; secondary A | `llm/providers/*` |
| `backend/tests/test_m10_stage1_security_verification.py` | ?? | E | M10 Stage 1 security regression | security implementation (A/C) |
| `backend/tests/test_m10_stage2_assistant_lifecycle.py` | ?? | E | Assistant lifecycle/provider whitelist; secondary B | `repositories/assistant_repository.py` |
| `backend/tests/test_m10_stage3_knowledge_and_retrieval.py` | ?? | E | Knowledge/retrieval Stage 3; secondary B | `api/v1/knowledge.py`, `retrieval/service.py` |
| `backend/tests/test_markdown_normalizer.py` | ?? | E | Markdown normalizer spec; secondary B | `markdown_normalizer.py` |
| `backend/tests/test_observability.py` | ?? | E | Trace/observability; secondary A | `observability/tracer.py` |
| `backend/tests/test_quota_and_byok_policy.py` | ?? | E | Quota reservations + BYOK policy; secondary A | `quota_service.py`, `byok_vault.py` |
| `backend/tests/test_s3_storage.py` | ?? | E | S3 provider behavior; secondary C | `storage/s3.py`, `pyproject.toml` |
| `backend/tests/test_sdk_python.py` | ?? | E | Python SDK contract; secondary B | developer API/SDK |
---

## 6. Group F - Documentation and evidence (89 files: 1 M + 88 ??)

| File | State | Group | Classification / dependency notes | Needed with |
|---|---|---|---|---|
| `docs/IMPLEMENTATION_ROADMAP.md` | M | F | Roadmap status update for M09/M10 | none (documentation) |
| `artifacts/evaluations/m09_final/final_m09_report.md` | ?? | F | M09 milestone evidence | none |
| `artifacts/evaluations/m09_final/m09_background_processing_report.md` | ?? | F | M09 milestone evidence | none |
| `artifacts/evaluations/m09_final/m09_evaluation_report.md` | ?? | F | M09 milestone evidence | none |
| `artifacts/evaluations/m09_final/m09_known_limitations.md` | ?? | F | M09 milestone evidence | none |
| `artifacts/evaluations/m09_final/m09_observability_report.md` | ?? | F | M09 milestone evidence | none |
| `artifacts/evaluations/m09_final/m09_preflight_summary.md` | ?? | F | M09 milestone evidence | none |
| `artifacts/evaluations/m09_final/m09_production_readiness_report.md` | ?? | F | M09 milestone evidence | none |
| `artifacts/evaluations/m09_final/m09_provider_architecture_report.md` | ?? | F | M09 milestone evidence | none |
| `artifacts/evaluations/m09_final/m09_test_evidence.md` | ?? | F | M09 milestone evidence | none |
| `artifacts/evaluations/m09_final/m09_usage_and_quota_report.md` | ?? | F | M09 milestone evidence | none |
| `artifacts/evaluations/m09_final/m09_user_experience_report.md` | ?? | F | M09 milestone evidence | none |
| `artifacts/evaluations/m09_m08_security_closure/anonymous_session_security_audit.md` | ?? | F | M09/M08 security evidence | none |
| `artifacts/evaluations/m09_m08_security_closure/developer_api_key_audit.md` | ?? | F | M09/M08 security evidence | none |
| `artifacts/evaluations/m09_m08_security_closure/embed_security_audit.md` | ?? | F | M09/M08 security evidence | none |
| `artifacts/evaluations/m09_m08_security_closure/m08_security_closure_report.md` | ?? | F | M09/M08 security evidence | none |
| `artifacts/evaluations/m09_m08_security_closure/public_access_security_tests.md` | ?? | F | M09/M08 security evidence | none |
| `artifacts/evaluations/m09_m08_security_closure/public_identifier_audit.md` | ?? | F | M09/M08 security evidence | none |
| `artifacts/evaluations/m09_m08_security_closure/sdk_verification.md` | ?? | F | M09/M08 security evidence | none |
| `artifacts/evaluations/m09_preflight/architecture_audit.md` | ?? | F | M09 preflight evidence | none |
| `artifacts/evaluations/m09_preflight/m08_security_audit.md` | ?? | F | M09 preflight evidence | none |
| `artifacts/evaluations/m09_preflight/m09_execution_plan.md` | ?? | F | M09 preflight evidence | none |
| `artifacts/evaluations/m09_preflight/milestone_reconciliation.md` | ?? | F | M09 preflight evidence | none |
| `artifacts/evaluations/m09_preflight/product_capability_matrix.md` | ?? | F | M09 preflight evidence | none |
| `artifacts/evaluations/m09_preflight/repository_baseline.md` | ?? | F | M09 preflight evidence | none |
| `artifacts/evaluations/m09_preflight/technical_debt_register.md` | ?? | F | M09 preflight evidence | none |
| `docs/m10/M10_FINAL_CONFIGURATION_AUDIT.md` | ?? | F | M10 audit | none |
| `docs/m10/M10_FINAL_DATABASE_READINESS.md` | ?? | F | M10 audit | none |
| `docs/m10/M10_FINAL_DEPLOYMENT_READINESS.md` | ?? | F | M10 audit | none |
| `docs/m10/M10_FINAL_FRONTEND_SDK_AUDIT.md` | ?? | F | M10 audit | none |
| `docs/m10/M10_FINAL_GIT_INVENTORY.md` | ?? | F | M10 audit | none |
| `docs/m10/M10_FINAL_INTEGRATION_REPORT.md` | ?? | F | M10 audit | none |
| `docs/m10/M10_FINAL_PROJECT_STATUS.md` | ?? | F | M10 audit | none |
| `docs/m10/M10_FINAL_RELIABILITY_AUDIT.md` | ?? | F | M10 audit | none |
| `docs/m10/M10_FINAL_SECURITY_INTEGRATION_AUDIT.md` | ?? | F | M10 audit | none |
| `docs/m10/M10_REMEDIATION_FINAL_GIT_READINESS.md` | ?? | F | M10 remediation closeout | none |
| `docs/m10/M10_REMEDIATION_FINAL_SUMMARY.md` | ?? | F | M10 remediation closeout | none |
| `docs/m10/M10_REMEDIATION_FINAL_TEST_REPORT.md` | ?? | F | M10 remediation closeout | none |
| `docs/m10/M10_REMEDIATION_STAGE_0_BASELINE.md` | ?? | F | M10 remediation stage report | none |
| `docs/m10/M10_REMEDIATION_STAGE_1_CORS.md` | ?? | F | M10 remediation stage report | none |
| `docs/m10/M10_REMEDIATION_STAGE_2_INVITATION_ROLES.md` | ?? | F | M10 remediation stage report | none |
| `docs/m10/M10_REMEDIATION_STAGE_3_STORAGE.md` | ?? | F | M10 remediation stage report | none |
| `docs/m10/M10_REMEDIATION_STAGE_4_MIGRATIONS.md` | ?? | F | M10 remediation stage report | none |
| `docs/m10/M10_REMEDIATION_STAGE_5_DEPENDENCIES.md` | ?? | F | M10 remediation stage report | none |
| `docs/m10/M10_REMEDIATION_STAGE_6_TEST_RECONCILIATION.md` | ?? | F | M10 remediation stage report | none |
| `docs/m10/M10_REMEDIATION_STAGE_8_QUALITY_GATES.md` | ?? | F | M10 remediation stage report | none |
| `docs/m10/M10_STAGE_0_BASELINE_AUDIT.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_1_SECURITY_AUDIT.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_1_TEST_RESULTS.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_2_IMPLEMENTATION.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_2_LIFECYCLE_AUDIT.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_2_TEST_RESULTS.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_2_UI_VERIFICATION.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_3_IMPLEMENTATION.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_3_KNOWLEDGE_AUDIT.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_3_TEST_RESULTS.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_3_UI_VERIFICATION.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_4_BASELINE_AUDIT.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_4_CONVERSATION_UX.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_4_DESIGN_SYSTEM.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_4_IMPLEMENTATION.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_4_RELEASE_GATE.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_4_TEST_RESULTS.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_4_UI_VERIFICATION.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_5_BASELINE_AUDIT.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_5_DEPLOYMENT_READINESS.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_5_FINAL_REPORT.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_5_RELEASE_GATE.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_5_RELIABILITY_AUDIT.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_5_SECURITY_REVIEW.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_5_TEST_RESULTS.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_5_THEME_AUDIT.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_5_UI_IMPLEMENTATION.md` | ?? | F | M10 stage report | none |
| `docs/m10/M10_STAGE_6_FINAL_REPORT.md` | ?? | F | M10 stage report | none |
| `docs/m10/evidence/stage4/screenshots/assistants_page_1794158165533.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/assistants_page_1794335771790.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/conversations_workspace_1794335827119.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/dashboard_overview_1794335518522.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/developer_api_keys_1794335965539.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/developer_api_keys_1794336037907.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/employees_directory_1794335854741.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/knowledge_studio_1794335800390.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/login_page_1794147799240.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/login_page_1794157794037.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/login_page_1794247099678.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/login_page_1794335389121.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/mobile_drawer_1794336094411.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/sidebar_compact_1794335586296.png` | ?? | F | UI evidence screenshot | none |
| `docs/m10/evidence/stage4/screenshots/sidebar_compact_1794335708355.png` | ?? | F | UI evidence screenshot | none |

### 6.1 Post-snapshot concurrent additions (outside the 202-file Stage 0 snapshot)

The following files were created by concurrent sibling audits after the 07:12:06Z baseline (observed through 07:26Z). They are classified for completeness but are not part of the 68/134/202 baseline. Additional sibling reports may appear after this cutoff.

| File | State | Group | Classification / dependency notes | Needed with |
|---|---|---|---|---|
| `docs/m10/M10_GIT_STAGE_2_MIGRATION_REVIEW.md` | ?? | F | Post-snapshot Stage 2 migration/release review (concurrent sibling); documentation only | none |
| `docs/m10/M10_GIT_STAGE_4_DEPENDENCY_REVIEW.md` | ?? | F | Post-snapshot Stage 4 dependency/reproducibility review (concurrent sibling); documentation only | none |

---

## 7. Group summaries

| Group | Baseline `M` | Baseline `??` | Baseline total | Post-snapshot `??` | Observed total |
|---|---:|---:|---:|---:|---:|
| A - M09 implementation + 0009 | 20 | 11 | **31** | 0 | **31** |
| B - M10 UI/product integration | 32 | 16 | **48** | 0 | **48** |
| C - M10 remediation/security configuration | 9 | 6 | **15** | 0 | **15** |
| D - migrations/database alignment | 2 | 1 | **3** | 0 | **3** |
| E - tests and quality gates | 4 | 12 | **16** | 0 | **16** |
| F - documentation and evidence | 1 | 88 | **89** | 2 | **91** |
| **Total** | **68** | **134** | **202** | **2** | **204** |

Reconciliation:

- Modified total: 20 + 32 + 9 + 2 + 4 + 1 = **68**, matching `git status` exactly.
- Baseline untracked total: 11 + 16 + 6 + 1 + 12 + 88 = **134**, matching the Stage 0 snapshot and `git ls-files --others --exclude-standard` at 07:12:06Z.
- Baseline grand total: **202** files, each listed exactly once in sections 1-6.
- Observed tree (07:26Z): **68** `M` + **136** `??` (134 baseline + 2 post-snapshot concurrent docs) = **204** files; all 204 are listed exactly once (202 in sections 1-6, 2 in section 6.1).
- No file was silently omitted, collapsed into a directory row, or double-counted.
- Post-write note: this document and the Stage 0 document are 2 additional untracked files under `docs/m10/`; a fresh `git ls-files --others` count is **138** = 134 baseline + 2 concurrent sibling docs + 2 audit docs. Further sibling reports may add files after this audit window; those are outside the snapshot.

---

## 8. Dependency rules enforced

### R1 - Migration chain: A(0009) -> D(0010)

`0010_m10_remediation_schema_alignment.py` declares `down_revision = "0009_m09_security_and_evaluation"`. Committing 0010 without 0009 makes Alembic fail with an unresolved parent revision. Conversely, `0009` adds `api_keys.assistant_id` and `public_chat_sessions.conversation_id` required by `models/publishing.py`, `api_key_service.py`, and `public_chat.py`. **Ship A's 0009 and its model/service changes together; never commit 0010 alone.**

### R2 - 0010 + models/quota parity

0010 creates nine model tables absent from migrations (`provider_connections`, `embedding_configs`, `vector_store_configs`, `resource_permissions`, `usage_records`, `assistant_prompts`, `invitations`, `assistant_memberships`, `message_attachments`), adds missing indexes, and drops `tenant_quotas.daily_request_limit` that `QuotaService` no longer writes. On databases already initialised by the lifespan `Base.metadata.create_all()`, the nine tables may already exist, so `0010` will raise `table already exists`. Treat 0010 as **fresh-database or parity-verified upgrade only** (check `alembic current`/table inventory first; do not blindly run it against a create_all-initialised database).

### R3 - 0003 + alembic/env.py

0003 now performs SQLite FK changes inside `batch_alter_table`; `env.py` adds `render_as_batch=True` and normalises `sqlite:///` to `sqlite+aiosqlite:///`. The 0003 upgrade path is self-contained, but env.py must ship alongside for consistent offline/autogenerate behavior. PostgreSQL DDL is preserved.

### R4 - CORS remediation set

`backend/app/main.py` imports `app.core.cors` at module import time. `build_cors_policy` reads `ALLOW_DEV_LAN_ORIGINS`, `ALLOWED_ORIGINS`, `CORS_ORIGIN_REGEX`, `FRONTEND_URL`, and `ENVIRONMENT`. **Ship `core/cors.py` + `main.py` + `core/config.py` + env templates + CORS tests as one unit.** `main.py` alone fails with ImportError; `config.py` alone leaves the policy attribute missing.

### R5 - Storage remediation set

`core/config.py` adds `S3_*`; `storage/__init__.py` validates fail-closed and `storage/s3.py` lazily imports `aioboto3`; `.env.production.example` and `render.yaml` switch to `STORAGE_BACKEND=s3`. Shipping `storage/__init__.py` while production config still says `local` causes **startup failure by design**. Shipping `storage/s3.py` without `pyproject.toml` causes ImportError on first S3 operation. **Ship storage code + config + env templates + render.yaml + pyproject together.**

### R6 - Dependencies vs providers

`aioboto3` is required only by the S3 storage path; `fastembed` is required by `embeddings/providers/sentence_transformer_provider.py`, which `render.yaml` selects for CPU embeddings. `pyproject.toml` alone is harmless but does not fix an uninstalled environment; lockfiles/image rebuild must follow.

### R7 - Application import graph (highest-risk)

`main.py` -> `api/v1/router.py` -> `api/v1/evaluation.py` + `api/v1/observability.py`; `main.py` lifespan -> `services/ingestion/recovery.py`; `main.py` -> `core/cors.py` + `storage/__init__.py`. Therefore **C's `main.py` cannot be committed without A's router/evaluation/observability/recovery and C's cors/storage files.**

### R8 - Runtime import graph

`assistant_runtime/runtime.py` imports `app.observability.tracer` (A) and `normalize_markdown` through `context.py` (B). `assistant_runtime/__init__.py` and `context.py` import `app.assistant_runtime.markdown_normalizer` (B). **A runtime + B markdown normalizer must ship together**, or startup fails with ImportError.

### R9 - Model registration

`models/__init__.py` imports `EvalDataset`, `EvalDatasetItem`, `EvalRun`, `EvalRunResult` from `models/evaluation.py`. Committing `models/__init__.py` alone produces ImportError during app startup and breaks every model import. Ship with `models/evaluation.py` and 0009.

### R10 - Frontend build graph

All modified pages import `frontend/components/ui` (barrel `index.ts` + primitives). `conversations/page.tsx` imports `components/chat/MarkdownRenderer.tsx` and `lib/citations.ts`. Pages call new methods on `lib/api.ts`. **Ship `lib/api.ts` + components + pages together**; omitting components or API methods fails Next.js typecheck/build.

### R11 - SDK contract

`sdk/typescript/src/index.ts` is independently compilable but encodes developer/public-chat contracts owned by A (`developer.py`, `public_chat.py`). Commit with those endpoints to avoid contract drift.

### R12 - Tests with their subject

Every test in E imports the new modules directly; committing tests alone fails collection, and committing implementation alone loses the security regression gate. Group E files with the A/B/C implementation they exercise. The three remediation tests are C-owned but E-relevant.

### R13 - Documentation/evidence

F has no runtime or migration dependency. Evidence may be committed with the milestone for traceability; it does not affect deployability.

---

## 9. Risky standalone files (would break startup, build, or migrations if committed alone)

| File | Risk if committed alone | Required companions |
|---|---|---|
| `backend/app/main.py` | ImportError (`core.cors`), startup failure (storage validation/recovery), missing routers | `core/cors.py`, `storage/__init__.py`, `services/ingestion/recovery.py`, `api/v1/router.py` + evaluation/observability modules |
| `backend/app/models/__init__.py` | ImportError at model-package import | `models/evaluation.py`, `0009` |
| `backend/app/assistant_runtime/runtime.py` | ImportError (`observability.tracer`, `markdown_normalizer`) | `observability/tracer.py`, `markdown_normalizer.py` |
| `backend/app/assistant_runtime/context.py` / `__init__.py` | ImportError (`markdown_normalizer`) | `markdown_normalizer.py` |
| `backend/app/models/publishing.py` | ORM/DB schema mismatch on Alembic-managed DB | `0009` |
| `backend/alembic/versions/0010_...py` | Alembic cannot resolve parent revision; table-exists failure on create_all DBs | `0009`, parity verification |
| `backend/app/storage/__init__.py` | Production startup raises if env still selects local storage | `.env.production.example`, `render.yaml`, `config.py` |
| `backend/app/storage/s3.py` | Runtime ImportError if `aioboto3` not packaged | `pyproject.toml` |
| `backend/app/core/cors.py` | Inert alone (not a break); only useful with `main.py` | `main.py`, `config.py` |
| `backend/app/api/v1/router.py` | ImportError if evaluation/observability modules absent | `evaluation.py`, `observability.py` |
| `frontend/lib/api.ts` | Pages referencing new methods fail typecheck if api.ts omitted; api.ts alone compiles | all modified pages |
| `frontend/components/ui/index.ts` / primitives | Page build failure if omitted | all modified pages |
| `frontend/app/dashboard/conversations/page.tsx` | Build failure without renderer/citations/api | `MarkdownRenderer.tsx`, `lib/citations.ts`, `lib/api.ts` |
| `frontend/app/dashboard/employees/page.tsx` | No startup risk; SEC-1 regression test fails without it | `test_remediation_stage2_invitation_roles.py` |
| `backend/pyproject.toml` | Safe alone; does not install packages by itself | rebuild/reinstall environment |

Recommended shipping unit: **one integration commit containing A + B + C + D + E**, or a short ordered series where migrations (D) follow their code (A/C) and tests ship with each subject. Do not split `main.py`, `runtime.py`, `models/__init__.py`, or the migration chain across commits.

---

## 10. Completeness declaration

```text
TOTAL_FILES_CLASSIFIED = 204 (202 baseline snapshot + 2 post-snapshot concurrent documents)
BASELINE_FILES_CLASSIFIED = 202
POST_SNAPSHOT_FILES_CLASSIFIED = 2
MODIFIED_TRACKED_CLASSIFIED = 68
UNTRACKED_FILES_CLASSIFIED = 136 (134 baseline + 2 post-snapshot)
UNKNOWN_FILES = 0
UNCLASSIFIED_FILES = 0
MISSING_FILES = 0
DUPLICATE_CLASSIFICATIONS = 0
MATCHES_GIT_OUTPUT = YES (68 M + 136 ??, excluding the 2 audit documents themselves)
UNTRACKED_DIRECTORIES_EXPANDED = YES (all 38 baseline porcelain entries expanded to 134 files)
PRIMARY_GROUP_ASSIGNED_TO_EVERY_FILE = YES
SECONDARY_GROUP_NOTED_WHERE_RELEVANT = YES
```

Ambiguity resolution recorded:

- `conversations.py` and `schemas/assistant.py` are documented by both the M09 UX report and M10 Stage 4 conversation specification; assigned **A primary** (M09 conversations implementation) with **B secondary** (M10 UI dependency).
- `knowledge.py`, `knowledge_repository.py`, `retrieval/service.py`, and `assistant_repository.py` are M10 product/backend work; assigned **B** (M10 product integration) because no dedicated M10 backend group exists and group C is limited to remediation configuration.
- `0009` and `0010` satisfy both A/D descriptions; split by feature ownership vs migration-chain ownership as stated in the tie-break rules.
- No file remained UNKNOWN after checking diffs, module imports, and milestone reports.