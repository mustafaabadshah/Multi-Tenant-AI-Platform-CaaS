# M10 Git Integration - Stage 6: Commit Architecture Plan

- **Timestamp (UTC):** 2026-11-12T08:14:39Z (measurement); plan finalized in the 08:20Z window
- **Repository:** `E:\MM Office\Multi-Tanant-CaaS`
- **Branch / HEAD:** `main` / `9479847b846aaae43cb8f51e81cf18aaf2646d0f`
- **HEAD subject:** `feat(m08): implement Public Assistant Publishing, Embed Widgets, Developer API, and SDKs`
- **origin/main:** `4f75f680250ae6b040e5d3c30bb13ac6fbe34a0f` (ahead 3, behind 0)
- **Mode:** READ-ONLY inspection plus this document. No `git add`, `commit`, `stash`, `reset`, `checkout`, `restore`, `rebase`, `cherry-pick`, branch change, push, or deployment was executed.
- **Purpose:** define an exact, dependency-aware, ordered commit sequence (C1-C8) that assigns every modified and untracked file exactly once.

> This is a plan only. Nothing is staged and no commit exists. The working tree remains exactly as found plus this document (and the Stage 7 / final report documents).

---

## 1. Current git state (measured 2026-11-12T08:14:39Z)

| Metric | Value | Method |
|---|---:|---|
| Branch | `main` | `git rev-parse --abbrev-ref HEAD` |
| HEAD | `9479847b846aaae43cb8f51e81cf18aaf2646d0f` | `git rev-parse HEAD` |
| origin/main | `4f75f680250ae6b040e5d3c30bb13ac6fbe34a0f` | `git rev-parse origin/main` |
| Ahead / behind | **3 / 0** | `git rev-list --left-right --count origin/main...HEAD` -> `0	3` |
| Modified tracked files (` M`) | **69** | `git status --porcelain=v1` |
| Untracked porcelain entries (`??`, directory-collapsed) | **39** | `git status --porcelain=v1` |
| Untracked files (fully expanded) | **142** | `git ls-files --others --exclude-standard` |
| Staged files | **0** | `git diff --cached --name-only` empty |
| Deleted tracked files | **0** | no ` D` / `D ` / `DD` entries |
| Porcelain lines (`-uall`) | **211** = 69 + 142 | `git status --porcelain=v1 --untracked-files=all` |
| Inventory at plan time | **211 files** | 69 modified + 142 untracked |
| After this stage's three documents | **214 files** | 69 modified + 145 untracked |

The three documents written by this stage (`M10_GIT_STAGE_6_COMMIT_PLAN.md`, `M10_GIT_STAGE_7_FINAL_READINESS.md`, `M10_GIT_INTEGRATION_FINAL_REPORT.md`) are inside the already-collapsed untracked directory `docs/m10/`; they raise the expanded untracked count from 142 to 145 but do not add new porcelain lines (the directory entry stays one line). The commit plan below covers all **214** files.

### 1.1 Modified tracked files (69)

```text
.env.example
.env.production.example
backend/alembic/env.py
backend/alembic/versions/0003_embeddings_and_vector_stores.py
backend/app/api/v1/conversations.py
backend/app/api/v1/developer.py
backend/app/api/v1/ingestion.py
backend/app/api/v1/knowledge.py
backend/app/api/v1/public_chat.py
backend/app/api/v1/router.py
backend/app/assistant_runtime/__init__.py
backend/app/assistant_runtime/context.py
backend/app/assistant_runtime/runtime.py
backend/app/core/config.py
backend/app/core/crypto.py
backend/app/embeddings/providers/openai_provider.py
backend/app/llm/base.py
backend/app/llm/capabilities.py
backend/app/llm/providers/groq_provider.py
backend/app/llm/providers/openai_provider.py
backend/app/main.py
backend/app/models/__init__.py
backend/app/models/publishing.py
backend/app/repositories/assistant_repository.py
backend/app/repositories/knowledge_repository.py
backend/app/retrieval/service.py
backend/app/schemas/assistant.py
backend/app/schemas/publishing.py
backend/app/services/api_key_service.py
backend/app/services/byok_vault.py
backend/app/services/publishing_service.py
backend/app/services/quota_service.py
backend/app/storage/__init__.py
backend/app/storage/s3.py
backend/app/vectorstores/qdrant_store.py
backend/pyproject.toml
backend/tests/test_m05_prompt_injection.py
backend/tests/test_m05_provider_reliability.py
backend/tests/test_m05_staging_readiness.py
backend/tests/test_m08_publishing_and_api_keys.py
docs/IMPLEMENTATION_ROADMAP.md
frontend/app/dashboard/assistants/AssistantCreationWizard.tsx
frontend/app/dashboard/assistants/AssistantWorkspaceView.tsx
frontend/app/dashboard/assistants/PublishTab.tsx
frontend/app/dashboard/assistants/page.tsx
frontend/app/dashboard/audit/page.tsx
frontend/app/dashboard/departments/page.tsx
frontend/app/dashboard/employees/page.tsx
frontend/app/dashboard/groups/page.tsx
frontend/app/dashboard/knowledge/IndexStatusTab.tsx
frontend/app/dashboard/knowledge/RetrievalPreviewTab.tsx
frontend/app/dashboard/knowledge/RetrievalSettingsTab.tsx
frontend/app/dashboard/knowledge/page.tsx
frontend/app/dashboard/layout.tsx
frontend/app/dashboard/page.tsx
frontend/app/dashboard/providers/page.tsx
frontend/app/dashboard/settings/DeveloperApiKeysSection.tsx
frontend/app/dashboard/settings/page.tsx
frontend/app/dashboard/workspace/page.tsx
frontend/app/embed/[publicId]/page.tsx
frontend/app/globals.css
frontend/app/layout.tsx
frontend/app/login/page.tsx
frontend/app/p/[publicId]/page.tsx
frontend/app/page.tsx
frontend/app/register/page.tsx
frontend/lib/api.ts
render.yaml
sdk/typescript/src/index.ts
```

### 1.2 Delta versus the Stage 0 snapshot (68 M / 134 untracked)

Stage 0 recorded **68 modified + 134 untracked = 202**. The current pre-write measurement is **69 modified + 142 untracked = 211**. The nine added files are fully explained:

| # | File | State | Origin |
|---:|---|---|---|
| 1 | `backend/app/core/crypto.py` | **M (new since Stage 0)** | Stage 3A F1 fix: active Fernet key now prefers `SECRET_ENCRYPTION_KEY` with `SECRET_KEY` fallback |
| 2 | `backend/tests/test_remediation_encryption_key.py` | ?? | Stage 3A F1 regression suite (3 tests) |
| 3 | `docs/m10/M10_GIT_STAGE_0_BASELINE.md` | ?? | Post-snapshot audit document (Stage 0) |
| 4 | `docs/m10/M10_GIT_STAGE_1_CHANGE_CLASSIFICATION.md` | ?? | Post-snapshot audit document (Stage 1) |
| 5 | `docs/m10/M10_GIT_STAGE_2_MIGRATION_REVIEW.md` | ?? | Stage 2 migration review |
| 6 | `docs/m10/M10_GIT_STAGE_3_SECURITY_REVIEW.md` | ?? | Stage 3 security review |
| 7 | `docs/m10/M10_GIT_STAGE_3A_F1_ENCRYPTION_KEY.md` | ?? | Stage 3A F1 remediation record |
| 8 | `docs/m10/M10_GIT_STAGE_4_DEPENDENCY_REVIEW.md` | ?? | Stage 4 dependency review |
| 9 | `docs/m10/M10_GIT_STAGE_5_REGRESSION_REPORT.md` | ?? | Stage 5 regression report |

Reconciliation: modified **68 -> 69 (+1, crypto.py)**; untracked **134 -> 142 (+8: 7 Git-stage documents + test_remediation_encryption_key.py)**. This stage then adds 3 more documents (`STAGE_6`, `STAGE_7`, final report), giving **69 modified + 145 untracked = 214**. No source or test file outside the F1 fix changed between Stage 0 and this plan.

### 1.3 Staged / deleted / remote checks

```text
STAGED_FILES = 0
DELETED_TRACKED_FILES = 0
REMOTES = origin fetch/push -> https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS.git
git diff --cached --name-only = <empty>
git status deletion filter (^D|^ D) = <empty>
```
---

## 2. Current group ownership (A-F) and commit mapping

Primary-group rule from Stage 1 is retained: every file is counted once. Current totals include the F1 files and the Git-stage documents.

| Group | Scope | Modified | Untracked | Total | Commit(s) |
|---|---|---:|---:|---:|---|
| **A** | M09 security/evaluation/observability/recovery/quota/BYOK + `0009` | 20 | 11 | **31** | C1 (28), C3 (2), C4 (1) |
| **B** | M10 UI/product integration + frontend/SDK + markdown normalizer | 32 | 16 | **48** | C3 (41), C4 (7) |
| **C** | Remediation/security configuration (CORS, RBAC, storage, crypto) | 10 | 7 | **17** | C5 (15), C6 (2) |
| **D** | Migrations/database alignment | 2 | 1 | **3** | C2 (3) |
| **E** | Tests and quality gates | 4 | 12 | **16** | C1 (7), C3 (4), C4 (3), C5 (2) |
| **F** | Documentation and evidence | 1 | 98 | **99** | C4 (1), C5 (3), C6 (1), C7 (6), C8 (88) |
| **Total** | | **69** | **145** | **214** | **214** |

Group C grew from 15 to 17 because of `backend/app/core/crypto.py` (M) and `backend/tests/test_remediation_encryption_key.py` (??). Group F grew from 91 observed at Stage 1 to 99 because of the seven Git-stage documents already on disk plus the three documents written in this stage.

---

## 3. Ordered commit sequence (C1-C8)

Ordering constraints that drive the sequence:

- **R1/R2:** `0010` declares `down_revision = "0009"`; 0010 must follow C1. `0009` must ship with the model/service changes it supports.
- **R7:** `main.py` (C5) imports `api/v1/router.py` (C1), which imports evaluation/observability (C1) and recovery (C1).
- **R8:** `runtime.py` imports `app.observability.tracer` (C1) and `normalize_markdown` through `context.py` (C4). The modified runtime can only land at C4.
- **R10:** frontend pages import `components/ui`, `lib/api.ts`, and `MarkdownRenderer.tsx`. Pages cannot be committed without those modules. `MarkdownRenderer.tsx` is therefore pulled forward into C3 because the assistant wizard/studio pages (C3) already import it.
- **R12:** security fixes ship with their regression suites: CORS/storage/encryption tests in C5, invitation-role tests in C6.
- **C4 depends on C3:** `runtime.py` imports `app.retrieval.service` (C3); `conversations/page.tsx` imports `components/ui` (C3) and `lib/citations.ts` (C4).
- **C6 depends on C3:** `employees/page.tsx` imports `@/components/ui/*` (C3) and `@/lib/api` (C3).

### C1 - `feat(m09): add evaluation, observability, and background recovery`

**Files (35 = 18 M + 17 ??)**

```text
backend/app/api/v1/developer.py
backend/app/api/v1/ingestion.py
backend/app/api/v1/public_chat.py
backend/app/api/v1/router.py
backend/app/embeddings/providers/openai_provider.py
backend/app/llm/base.py
backend/app/llm/capabilities.py
backend/app/llm/providers/groq_provider.py
backend/app/llm/providers/openai_provider.py
backend/app/models/__init__.py
backend/app/models/publishing.py
backend/app/schemas/publishing.py
backend/app/services/api_key_service.py
backend/app/services/byok_vault.py
backend/app/services/publishing_service.py
backend/app/services/quota_service.py
backend/app/vectorstores/qdrant_store.py
backend/tests/test_m08_publishing_and_api_keys.py
backend/alembic/versions/0009_m09_security_and_evaluation.py
backend/app/api/v1/evaluation.py
backend/app/api/v1/observability.py
backend/app/evaluation/judge.py
backend/app/evaluation/metrics.py
backend/app/evaluation/starter_benchmarks.py
backend/app/models/evaluation.py
backend/app/observability/tracer.py
backend/app/schemas/evaluation.py
backend/app/services/evaluation_service.py
backend/app/services/ingestion/recovery.py
backend/tests/test_background_recovery.py
backend/tests/test_evaluation.py
backend/tests/test_groq_and_api_hardening.py
backend/tests/test_observability.py
backend/tests/test_quota_and_byok_policy.py
backend/tests/test_sdk_python.py
```

**Why grouped:** this is the self-contained M09 backend slice: evaluation engine/API/models/tables, observability tracer/API, startup recovery, API-key assistant scoping, quota reservations, BYOK validation, publishing/session binding, provider hardening, and migration `0009`. `models/__init__.py` must land with `models/evaluation.py` (import graph). `router.py` must land with the new evaluation/observability routers. `0009` must land with `models/publishing.py` and the services that read the new columns.

**Required prior commits:** none (first commit on the branch).

**Tests/gates that must pass:** `compileall -q app tests`; `pytest tests/test_evaluation.py tests/test_observability.py tests/test_background_recovery.py tests/test_quota_and_byok_policy.py tests/test_groq_and_api_hardening.py tests/test_m08_publishing_and_api_keys.py tests/test_sdk_python.py -q`; `alembic heads` still reports `0009` as the only head before 0010 lands.

**Expected application state:** the app imports against HEAD `main.py`; evaluation/observability routes are mounted; M09 quota/BYOK/API-key hardening is active; `0009` is the migration head. The nine 0010 tables are not yet in migration history (C2 resolves that). `runtime.py` remains at HEAD, which still calls `QuotaService.check_quota` (retained in the modified service), so startup is not broken.

**Risk if committed independently:** low-to-moderate. The 0010 schema alignment is absent, so Alembic-managed databases remain structurally behind the models for nine tables; the modified `models/publishing.py` requires `0009`, which is included. No import break is expected because `runtime.py` and `main.py` are still at HEAD.
---

### C2 - `fix(db): align migration chain with models and SQLite compatibility`

**Files (3 = 2 M + 1 ??)**

```text
backend/alembic/env.py
backend/alembic/versions/0003_embeddings_and_vector_stores.py
backend/alembic/versions/0010_m10_remediation_schema_alignment.py
```

**Why grouped:** `0010` is the child of `0009` and creates the nine missing model tables plus 38 indexes and drops `tenant_quotas.daily_request_limit`. `0003` needs `render_as_batch=True` and SQLite URL normalization from `env.py` so the dialect-aware FK create/drop path is consistent in online and offline modes. This is the migration-only unit with no runtime code.

**Required prior commits:** **C1** (`0010.down_revision = "0009_m09_security_and_evaluation"`; 0009 is added by C1).

**Tests/gates that must pass:** `alembic heads` = single `0010_m10_remediation_schema_alignment (head)`; `alembic history` linear; fresh SQLite `upgrade head` exit 0; `0008 -> head` seeded `api_keys`/`public_chat_sessions` rows preserved with new columns NULL; 0010 downgrade/re-upgrade symmetry. Evidence already recorded in Stage 2 and Stage 5.

**Expected application state:** migration chain is linear and model-aligned on SQLite; PostgreSQL DDL semantics are preserved by inspection only. `0010` is **not idempotent** against databases bootstrapped by `Base.metadata.create_all()`; such databases must be parity-checked or stamped, never blindly upgraded.

**Risk if committed independently:** **high**. Cherry-picking C2 without C1 leaves Alembic unable to resolve `0009`; 0010 fails. On a create_all-initialised database, 0010 raises `table already exists`. C2 must never be pushed alone.

---

### C3 - `feat(m10): assistant workspace, design system, and conversations UX`

**Files (47 = 30 M + 17 ??)**

```text
backend/app/api/v1/conversations.py
backend/app/api/v1/knowledge.py
backend/app/repositories/assistant_repository.py
backend/app/repositories/knowledge_repository.py
backend/app/retrieval/service.py
backend/app/schemas/assistant.py
frontend/app/dashboard/assistants/AssistantCreationWizard.tsx
frontend/app/dashboard/assistants/AssistantWorkspaceView.tsx
frontend/app/dashboard/assistants/PublishTab.tsx
frontend/app/dashboard/assistants/page.tsx
frontend/app/dashboard/audit/page.tsx
frontend/app/dashboard/departments/page.tsx
frontend/app/dashboard/groups/page.tsx
frontend/app/dashboard/knowledge/IndexStatusTab.tsx
frontend/app/dashboard/knowledge/RetrievalPreviewTab.tsx
frontend/app/dashboard/knowledge/RetrievalSettingsTab.tsx
frontend/app/dashboard/knowledge/page.tsx
frontend/app/dashboard/layout.tsx
frontend/app/dashboard/page.tsx
frontend/app/dashboard/providers/page.tsx
frontend/app/dashboard/settings/DeveloperApiKeysSection.tsx
frontend/app/dashboard/settings/page.tsx
frontend/app/dashboard/workspace/page.tsx
frontend/app/globals.css
frontend/app/layout.tsx
frontend/app/login/page.tsx
frontend/app/page.tsx
frontend/app/register/page.tsx
frontend/lib/api.ts
sdk/typescript/src/index.ts
frontend/app/dashboard/assistants/EvaluationTab.tsx
frontend/app/dashboard/observability/page.tsx
frontend/components/chat/MarkdownRenderer.tsx
frontend/components/ui/Badge.tsx
frontend/components/ui/Button.tsx
frontend/components/ui/Card.tsx
frontend/components/ui/ConfirmModal.tsx
frontend/components/ui/EmptyState.tsx
frontend/components/ui/Input.tsx
frontend/components/ui/Modal.tsx
frontend/components/ui/Spinner.tsx
frontend/components/ui/StatusIndicator.tsx
frontend/components/ui/index.ts
backend/tests/test_conversations_ux.py
backend/tests/test_m10_stage1_security_verification.py
backend/tests/test_m10_stage2_assistant_lifecycle.py
backend/tests/test_m10_stage3_knowledge_and_retrieval.py
```

**Why grouped:** this is the M10 product/UI slice: assistant studio/wizard/workspace, Knowledge Studio tabs, providers/settings/audit/departments/groups/dashboard pages, design-system primitives, shared `lib/api.ts`, TypeScript SDK contract, evaluation/observability UI tabs, conversation rename/status API + `ConversationUpdateRequest`, assistant provider whitelist, knowledge update/count queries, lexical retrieval fallback, and Stage 1-3 regression tests. `MarkdownRenderer.tsx` is included here (rather than C4) because `AssistantCreationWizard.tsx:31` and `assistants/page.tsx:41` import it; omitting it would break the C3 Next.js build. `lib/api.ts` is the shared client for every C3 page.

**Required prior commits:** **C1** for evaluation/observability endpoints consumed by `EvaluationTab.tsx`/`observability/page.tsx` and for the M09 services behind conversation/knowledge flows.

**Tests/gates that must pass:** `pytest tests/test_m10_stage1_security_verification.py tests/test_m10_stage2_assistant_lifecycle.py tests/test_m10_stage3_knowledge_and_retrieval.py tests/test_conversations_ux.py -q`; `npx tsc --noEmit`; `npm run build` (the conversations route is not yet present; all committed routes compile).

**Expected application state:** M10 Stage 1-4 product surface and design system are usable; evaluation/observability tabs render; the conversations workspace page is not yet committed (C4). All modified pages compile against `lib/api.ts` and `components/ui`.

**Risk if committed independently:** **moderate**. C3 depends on C1 endpoints at runtime; a standalone C3 checkout would compile but evaluation/observability UI calls would 404. The backend knowledge/conversation changes are otherwise self-contained. Do not cherry-pick C3 without C1.
---

### C4 - `feat(m10): markdown rendering and citation quality (stage 6)`

**Files (12 = 7 M + 5 ??)**

```text
backend/app/assistant_runtime/__init__.py
backend/app/assistant_runtime/context.py
backend/app/assistant_runtime/runtime.py
backend/tests/test_m05_prompt_injection.py
backend/tests/test_m05_provider_reliability.py
frontend/app/embed/[publicId]/page.tsx
frontend/app/p/[publicId]/page.tsx
backend/app/assistant_runtime/markdown_normalizer.py
backend/tests/test_markdown_normalizer.py
frontend/app/dashboard/conversations/page.tsx
frontend/lib/citations.ts
docs/m10/M10_STAGE_6_FINAL_REPORT.md
```

**Why grouped:** the canonical markdown normalizer (`markdown_normalizer.py`), its re-export through `context.py`/`assistant_runtime/__init__.py`, the shared citation deduper (`lib/citations.ts`), the first-class conversations canvas, both public chat surfaces' citation edits, and the backend markdown/prompt/provider regression updates. `runtime.py` is committed here, not in C1, because it imports both `app.observability.tracer` (C1) and `normalize_markdown` from `context.py` (C4); file-level commits cannot split those imports. `test_m05_prompt_injection.py`/`test_m05_provider_reliability.py` follow their subjects (`context.py`/`runtime.py`) per R12.

**Required prior commits:** **C1** (tracer, quota/BYOK services, evaluation/observability) and **C3** (`app.retrieval.service`, `lib/api.ts`, `components/ui`, `MarkdownRenderer.tsx`).

**Tests/gates that must pass:** `pytest tests/test_markdown_normalizer.py tests/test_m05_prompt_injection.py tests/test_m05_provider_reliability.py -q`; targeted 63-test reconciliation set from Stage 5 section 12; `npx tsc --noEmit`; `npm run build` (20/20 routes, now including `/dashboard/conversations`).

**Expected application state:** markdown output is normalized server-side and rendered safely client-side; citation chips/dedup work on conversations, public page, and embed; the conversations route is live. This is the first commit where the full frontend route set exists.

**Risk if committed independently:** **high**. `runtime.py` imports `app.observability.tracer` (C1) and `context.py`/`markdown_normalizer.py`; cherry-picking C4 onto HEAD without C1 fails at import/startup. The frontend conversation route also needs C3's `lib/api.ts` and UI primitives.

---

### C5 - `fix(security): fail-closed CORS, tenant-safe storage, and dedicated BYOK key`

**Files (20 = 10 M + 10 ??)**

```text
.env.example
.env.production.example
backend/app/core/config.py
backend/app/core/crypto.py
backend/app/main.py
backend/app/storage/__init__.py
backend/app/storage/s3.py
backend/pyproject.toml
render.yaml
backend/tests/test_m05_staging_readiness.py
backend/.dockerignore
backend/app/core/cors.py
backend/tests/test_remediation_encryption_key.py
backend/tests/test_remediation_stage1_cors.py
backend/tests/test_remediation_stage3_storage.py
backend/tests/test_s3_storage.py
frontend/.dockerignore
docs/m10/M10_REMEDIATION_STAGE_1_CORS.md
docs/m10/M10_REMEDIATION_STAGE_3_STORAGE.md
docs/m10/M10_GIT_STAGE_3A_F1_ENCRYPTION_KEY.md
```

**Why grouped:** one security/configuration unit: centralized fail-closed CORS (`core/cors.py` + `main.py` + `config.py` + env templates), tenant-safe storage validation and S3 key neutralization (`storage/__init__.py`, `storage/s3.py`), the F1 dedicated `SECRET_ENCRYPTION_KEY` fix (`config.py`, `crypto.py`), dependency declarations (`pyproject.toml`), S3 production blueprint (`render.yaml`), build-context exclusions, and every regression suite for these controls. `test_s3_storage.py` is included here (not C1) because it exercises the modified `storage/s3.py`; the security fix must ship with its tests. `test_m05_staging_readiness.py` follows the CORS policy change.

**Required prior commits:** **C1** (`main.py` imports `api/v1/router.py`, which imports evaluation/observability/recovery added in C1); **C4** is not strictly required but the sequence keeps the app fully assembled before the security unit.

**Tests/gates that must pass:** `pytest tests/test_remediation_stage1_cors.py tests/test_remediation_stage3_storage.py tests/test_remediation_encryption_key.py tests/test_s3_storage.py tests/test_m05_staging_readiness.py -q`; `compileall -q app`; `pip check`; `python -c "from app.main import app"`.

**Expected application state:** production startup fails closed on untrusted CORS, local storage, or missing S3 credentials; S3 keys cannot escape the tenant prefix; BYOK encryption uses `SECRET_ENCRYPTION_KEY` when set and falls back to `SECRET_KEY` when empty. Existing ciphertext remains decryptable as long as the setting is unset.

**Risk if committed independently:** **high**. `main.py` imports `app.core.cors` (included) but also `api/v1/router.py` with evaluation/observability/recovery (C1); a standalone C5 checkout on HEAD fails at import. Production config also becomes fail-closed by design, so a deployment that still selects local storage will refuse to start.
---

### C6 - `fix(rbac): align invitation roles with canonical registry`

**Files (3 = 1 M + 2 ??)**

```text
frontend/app/dashboard/employees/page.tsx
backend/tests/test_remediation_stage2_invitation_roles.py
docs/m10/M10_REMEDIATION_STAGE_2_INVITATION_ROLES.md
```

**Why grouped:** the SEC-1 fix restores the invite dropdown to the six canonical `SystemRole` values and aligns badge variants; the 15-test suite proves canonical values, rejection of `manager`/`admin`/`super_admin`, default `employee`, owner-only escalation, cross-tenant isolation, and employee denial. Test and fix ship together per the security-fix-with-tests rule.

**Required prior commits:** **C3** (`employees/page.tsx` imports `@/components/ui/*`, `@/lib/api`, which C3 adds).

**Tests/gates that must pass:** `pytest tests/test_remediation_stage2_invitation_roles.py -q` (15 passed); `npx tsc --noEmit`.

**Expected application state:** invitation UI offers only canonical roles; backend rejects unsupported role names with 400 and non-owner `tenant_owner`/`platform_superadmin` assignment with 403. No other UI behavior changes.

**Risk if committed independently:** **medium**. The backend test suite passes against the backend at C1-C5, but the frontend page imports C3 components; a standalone C6 checkout fails Next.js resolution. No database or migration dependency.

---

### C7 - `docs(m10): record remediation stages and test reconciliation evidence`

**Files (6 ??, documentation only)**

```text
docs/m10/M10_REMEDIATION_STAGE_0_BASELINE.md
docs/m10/M10_REMEDIATION_STAGE_4_MIGRATIONS.md
docs/m10/M10_REMEDIATION_STAGE_5_DEPENDENCIES.md
docs/m10/M10_REMEDIATION_STAGE_6_TEST_RECONCILIATION.md
docs/m10/M10_REMEDIATION_STAGE_8_QUALITY_GATES.md
docs/m10/M10_REMEDIATION_FINAL_TEST_REPORT.md
```

**Why grouped:** these are the remediation baseline, migration, dependency, test-reconciliation, quality-gate, and final test reports. **No ungrouped test file remains**: the four remediation suites are already attached to C5/C6 by the security-fix-with-tests rule, and the M05/Markdown test updates are attached to their subjects in C1/C4. The originally proposed `test(m10): add remediation and security regression suites` subject is therefore adjusted to a docs subject; a `test` commit with no test code would be misleading. This is the only deliberate message change from the recommended structure.

**Required prior commits:** C1-C6 (the documents reference the remediation code and results they describe).

**Tests/gates that must pass:** documentation review only; no code change. The full suite remains the Stage 5 result.

**Expected application state:** no runtime change. Remediation evidence is recorded in the repository.

**Risk if committed independently:** **none** (documentation only).
---

### C8 - `docs(m10): record final integration audit and release evidence`

**Files (88 = 1 M + 87 ??)**

```text
docs/IMPLEMENTATION_ROADMAP.md
artifacts/evaluations/m09_final/final_m09_report.md
artifacts/evaluations/m09_final/m09_background_processing_report.md
artifacts/evaluations/m09_final/m09_evaluation_report.md
artifacts/evaluations/m09_final/m09_known_limitations.md
artifacts/evaluations/m09_final/m09_observability_report.md
artifacts/evaluations/m09_final/m09_preflight_summary.md
artifacts/evaluations/m09_final/m09_production_readiness_report.md
artifacts/evaluations/m09_final/m09_provider_architecture_report.md
artifacts/evaluations/m09_final/m09_test_evidence.md
artifacts/evaluations/m09_final/m09_usage_and_quota_report.md
artifacts/evaluations/m09_final/m09_user_experience_report.md
artifacts/evaluations/m09_m08_security_closure/anonymous_session_security_audit.md
artifacts/evaluations/m09_m08_security_closure/developer_api_key_audit.md
artifacts/evaluations/m09_m08_security_closure/embed_security_audit.md
artifacts/evaluations/m09_m08_security_closure/m08_security_closure_report.md
artifacts/evaluations/m09_m08_security_closure/public_access_security_tests.md
artifacts/evaluations/m09_m08_security_closure/public_identifier_audit.md
artifacts/evaluations/m09_m08_security_closure/sdk_verification.md
artifacts/evaluations/m09_preflight/architecture_audit.md
artifacts/evaluations/m09_preflight/m08_security_audit.md
artifacts/evaluations/m09_preflight/m09_execution_plan.md
artifacts/evaluations/m09_preflight/milestone_reconciliation.md
artifacts/evaluations/m09_preflight/product_capability_matrix.md
artifacts/evaluations/m09_preflight/repository_baseline.md
artifacts/evaluations/m09_preflight/technical_debt_register.md
docs/m10/M10_FINAL_CONFIGURATION_AUDIT.md
docs/m10/M10_FINAL_DATABASE_READINESS.md
docs/m10/M10_FINAL_DEPLOYMENT_READINESS.md
docs/m10/M10_FINAL_FRONTEND_SDK_AUDIT.md
docs/m10/M10_FINAL_GIT_INVENTORY.md
docs/m10/M10_FINAL_INTEGRATION_REPORT.md
docs/m10/M10_FINAL_PROJECT_STATUS.md
docs/m10/M10_FINAL_RELIABILITY_AUDIT.md
docs/m10/M10_FINAL_SECURITY_INTEGRATION_AUDIT.md
docs/m10/M10_GIT_STAGE_0_BASELINE.md
docs/m10/M10_GIT_STAGE_1_CHANGE_CLASSIFICATION.md
docs/m10/M10_GIT_STAGE_2_MIGRATION_REVIEW.md
docs/m10/M10_GIT_STAGE_3_SECURITY_REVIEW.md
docs/m10/M10_GIT_STAGE_4_DEPENDENCY_REVIEW.md
docs/m10/M10_GIT_STAGE_5_REGRESSION_REPORT.md
docs/m10/M10_REMEDIATION_FINAL_GIT_READINESS.md
docs/m10/M10_REMEDIATION_FINAL_SUMMARY.md
docs/m10/M10_STAGE_0_BASELINE_AUDIT.md
docs/m10/M10_STAGE_1_SECURITY_AUDIT.md
docs/m10/M10_STAGE_1_TEST_RESULTS.md
docs/m10/M10_STAGE_2_IMPLEMENTATION.md
docs/m10/M10_STAGE_2_LIFECYCLE_AUDIT.md
docs/m10/M10_STAGE_2_TEST_RESULTS.md
docs/m10/M10_STAGE_2_UI_VERIFICATION.md
docs/m10/M10_STAGE_3_IMPLEMENTATION.md
docs/m10/M10_STAGE_3_KNOWLEDGE_AUDIT.md
docs/m10/M10_STAGE_3_TEST_RESULTS.md
docs/m10/M10_STAGE_3_UI_VERIFICATION.md
docs/m10/M10_STAGE_4_BASELINE_AUDIT.md
docs/m10/M10_STAGE_4_CONVERSATION_UX.md
docs/m10/M10_STAGE_4_DESIGN_SYSTEM.md
docs/m10/M10_STAGE_4_IMPLEMENTATION.md
docs/m10/M10_STAGE_4_RELEASE_GATE.md
docs/m10/M10_STAGE_4_TEST_RESULTS.md
docs/m10/M10_STAGE_4_UI_VERIFICATION.md
docs/m10/M10_STAGE_5_BASELINE_AUDIT.md
docs/m10/M10_STAGE_5_DEPLOYMENT_READINESS.md
docs/m10/M10_STAGE_5_FINAL_REPORT.md
docs/m10/M10_STAGE_5_RELEASE_GATE.md
docs/m10/M10_STAGE_5_RELIABILITY_AUDIT.md
docs/m10/M10_STAGE_5_SECURITY_REVIEW.md
docs/m10/M10_STAGE_5_TEST_RESULTS.md
docs/m10/M10_STAGE_5_THEME_AUDIT.md
docs/m10/M10_STAGE_5_UI_IMPLEMENTATION.md
docs/m10/evidence/stage4/screenshots/assistants_page_1794158165533.png
docs/m10/evidence/stage4/screenshots/assistants_page_1794335771790.png
docs/m10/evidence/stage4/screenshots/conversations_workspace_1794335827119.png
docs/m10/evidence/stage4/screenshots/dashboard_overview_1794335518522.png
docs/m10/evidence/stage4/screenshots/developer_api_keys_1794335965539.png
docs/m10/evidence/stage4/screenshots/developer_api_keys_1794336037907.png
docs/m10/evidence/stage4/screenshots/employees_directory_1794335854741.png
docs/m10/evidence/stage4/screenshots/knowledge_studio_1794335800390.png
docs/m10/evidence/stage4/screenshots/login_page_1794147799240.png
docs/m10/evidence/stage4/screenshots/login_page_1794157794037.png
docs/m10/evidence/stage4/screenshots/login_page_1794247099678.png
docs/m10/evidence/stage4/screenshots/login_page_1794335389121.png
docs/m10/evidence/stage4/screenshots/mobile_drawer_1794336094411.png
docs/m10/evidence/stage4/screenshots/sidebar_compact_1794335586296.png
docs/m10/evidence/stage4/screenshots/sidebar_compact_1794335708355.png
docs/m10/M10_GIT_STAGE_6_COMMIT_PLAN.md
docs/m10/M10_GIT_STAGE_7_FINAL_READINESS.md
docs/m10/M10_GIT_INTEGRATION_FINAL_REPORT.md
```

**Why grouped:** all remaining milestone documentation/evidence: final M10 audit reports, Git integration stage reports (except 3A, which ships with its F1 code in C5), remediation final summary/readiness, all M10 stage reports except Stage 6 closeout (C4), the implementation roadmap update, M09 evaluation artifacts, Stage 4 UI screenshots, and this stage's three documents. No runtime dependency.

**Required prior commits:** C1-C7 (the reports describe the complete code/migration/test state).

**Tests/gates that must pass:** documentation review only; final gate re-confirms the Stage 5 full-suite result (`335 passed, 18 skipped, 4 warnings in 469.06s`) and frontend build `20/20`.

**Expected application state:** no runtime change. The full M10 + Git integration evidence set is committed; `git status` should then show a clean tree except ignored local state.

**Risk if committed independently:** **none** (documentation/evidence only).
---

## 4. Coverage proof

### 4.1 Per-commit totals

| Commit | Message type | Modified | Untracked | Total |
|---|---|---:|---:|---:|
| C1 | feat(m09) | 18 | 17 | **35** |
| C2 | fix(db) | 2 | 1 | **3** |
| C3 | feat(m10) | 30 | 17 | **47** |
| C4 | feat(m10) | 7 | 5 | **12** |
| C5 | fix(security) | 10 | 10 | **20** |
| C6 | fix(rbac) | 1 | 2 | **3** |
| C7 | docs(m10) | 0 | 6 | **6** |
| C8 | docs(m10) | 1 | 87 | **88** |
| **Total** | | **69** | **145** | **214** |

### 4.2 Group-by-commit matrix

| Group | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 28 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | **31** |
| B | 0 | 0 | 41 | 7 | 0 | 0 | 0 | 0 | **48** |
| C | 0 | 0 | 0 | 0 | 15 | 2 | 0 | 0 | **17** |
| D | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | **3** |
| E | 7 | 0 | 4 | 3 | 2 | 0 | 0 | 0 | **16** |
| F | 0 | 0 | 0 | 1 | 3 | 1 | 6 | 88 | **99** |
| **Total** | **35** | **3** | **47** | **12** | **20** | **3** | **6** | **88** | **214** |

### 4.3 Union verification

```text
INVENTORY_MODIFIED                = 69
INVENTORY_UNTRACKED               = 145 (142 measured + 3 documents written by this stage)
INVENTORY_TOTAL                   = 214
FILES_ASSIGNED_IN_C1_C8           = 214
FILES_ASSIGNED_EXACTLY_ONCE       = 214
DUPLICATE_ASSIGNMENTS             = 0
UNASSIGNED_FILES                  = 0
UNKNOWN_FILES                     = 0
C1_MODIFIED + ... + C8_MODIFIED   = 69
C1_UNTRACKED + ... + C8_UNTRACKED = 145
```

The three documents written by this stage are assigned exactly once, in C8. The pre-write measurement (`69 M + 142 ?? = 211`) is also fully covered by the same plan minus those three paths.

---

## 5. Dependency notes and deliberate adjustments

| Decision | Reason |
|---|---|
| `runtime.py` is in C4, not C1 | It imports `app.observability.tracer` (C1) and `normalize_markdown` from `context.py`/`markdown_normalizer.py` (C4). At file granularity the earliest import-safe commit is C4; splitting the file is not possible. |
| `test_m05_provider_reliability.py` is in C4 | It asserts the strict-BYOK / persisted-error behavior implemented by `runtime.py`; R12 says tests ship with their subject. |
| `test_m05_prompt_injection.py` is in C4 | It asserts the new prompt formatting/security text in `context.py`. |
| `MarkdownRenderer.tsx` is in C3 | `AssistantCreationWizard.tsx:31` and `assistants/page.tsx:41` import it; C3's build would fail without it. C4 still owns the citation layer and the conversations/public surfaces. |
| `test_s3_storage.py` is in C5 | It exercises `storage/s3.py`; storage is C5. Keeping it in C1 would separate the test from its subject. |
| `conversations.py` + `schemas/assistant.py` are in C3 | They carry the conversation rename/status contract used by `test_conversations_ux.py` and the conversations UI. |
| `env.py` is in C2 | `0003` relies on `render_as_batch=True` and SQLite URL normalization for consistent offline/autogenerate behavior (R3). |
| C7 is docs-only | No ungrouped test files remain; all four remediation suites are attached to C5/C6 and the M05/Markdown updates to C1/C4. The prescribed `test(m10)` subject is adjusted to `docs(m10)`. |
| 0009 ships in C1; 0003+0010 in C2 | Migration chain integrity (R1/R2); 0010 cannot precede 0009. |
| No backend lockfile commit | Stage 4 recommends a dedicated dependency-only lock commit before staging; generating one is outside this read-only phase. Do not fold it into C5. |
| No 0010 idempotency change | 0010 is not idempotent on create_all-bootstrapped databases; the operational recommendation is to stamp/parity-check, not to edit the migration in this phase. |

---

## 6. Commit-level gate summary

| Commit | Minimum gate before committing | Full-suite gate |
|---|---|---|
| C1 | M09 targeted tests listed above; compileall; single head `0009` | Full suite after C1 is not the final gate; Stage 5 full run is reused at C8 |
| C2 | Alembic heads/history + fresh SQLite + 0008->head preservation | Migration evidence from Stage 2/5 |
| C3 | M10 Stage 1-3 + conversations tests; tsc; build | Frontend route set compiles |
| C4 | Markdown/prompt/provider tests; tsc; build 20/20 | Full frontend build |
| C5 | CORS/storage/encryption/S3/staging tests; pip check; app import | Security regression suites |
| C6 | Invitation-role suite (15); tsc | RBAC regression |
| C7 | Documentation review | None (no code) |
| C8 | Final evidence review | Stage 5: `335 passed, 18 skipped, 4 warnings in 469.06s`; tsc 0; build 20/20 |

---

## 7. Files that cannot be safely assigned / exceptions

- **None unassigned.** Every one of the 214 files has exactly one primary commit.
- **Flagged ordering constraints:** `0010` (C2) cannot exist without `0009` (C1); `runtime.py` (C4) cannot exist without C1's tracer and C4's normalizer; `main.py` (C5) cannot exist without C1's router/evaluation/observability; `employees/page.tsx` (C6) cannot build without C3's UI primitives; `conversations/page.tsx` (C4) cannot build without C3's UI/api/renderer.
- **Flagged message adjustment:** C7 uses `docs(m10)` because no ungrouped test files remain. This is not a coverage gap; it is a consequence of the security-fix-with-tests rule.
- **Not committed / not assigned:** ignored local state (`backend/.env`, `backend/local.db`, `backend/test.db`, `backend/.venv`, `frontend/node_modules`, `backend/data/`, `.obsidian/`) is correctly outside the inventory and must never be added.

---

## 8. Preservation and safety declarations

```text
COMMIT_PLAN_ONLY                       = YES
GIT_MUTATIONS_EXECUTED                 = NONE
STAGED_FILES                           = 0
COMMITS_CREATED                        = 0
PUSHES                                 = 0
REMOTE_CHANGES                         = 0
DEPLOYMENTS                            = 0
SOURCE_OR_TEST_FILES_EDITED            = NO (only the three Stage 6/7/final documents were written)
UNCOMMITTED_WORK_PRESERVED             = YES
FILES_DELETED_OR_IGNORED_BY_THIS_STAGE = NONE
TOTAL_FILES_MAPPED                     = 214
```

The plan awaits explicit user approval. No staging or commit should occur until the user reviews this sequence.