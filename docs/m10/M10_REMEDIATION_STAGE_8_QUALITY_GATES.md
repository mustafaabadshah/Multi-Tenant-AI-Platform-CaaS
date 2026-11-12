# M10 Remediation — Stage 8: Ruff, Formatting and Historical CI Debt

- **Date:** 2026-11-12
- **Repository HEAD:** `9479847`
- **Scope:** backend Python files touched by M09/M10 only (modified tracked + untracked)
- **Status:** PASS for changed-file lint scope (98 → 0). Global ruff debt intentionally reduced but not eliminated (128 → 30).
- **Git operations:** none. No `add`, `commit`, `stash`, `reset`, or `checkout` was run.

---

## 1. Guardrails Observed

- No repository-wide formatter was executed.
- `ruff format` was **never** run in write mode. Only `ruff format --check .` (read-only) was used.
- Only the 65 backend `.py` files listed in Appendix A were modified.
- No `--unsafe-fixes` was used.
- Auto-fixes were applied only to the changed-file list, then verified against a byte-for-byte pre-fix snapshot of those files.
- The only non-import auto-fix was removal of an unused exception binding (`except Exception as ret_err:` → `except Exception:`), which has no runtime effect. See §6.1.
- No commits were created.

---

## 2. Ruff Configuration

From `backend/pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I"]
ignore = ["B008", "E501"]
```

Consequences:

- `E501` (line-too-long) is ignored, so long prompt strings are not violations.
- `B008` is ignored.
- Import sorting (`I001`) and unused imports (`F401`) are enforced.

---

## 3. Global Before/After

| Metric | Before Stage 8 | After Stage 8 |
|---|---:|---:|
| `ruff check .` (global) | **128** | **30** |
| `ruff check <65 changed files>` | **98** | **0** |
| `ruff format --check .` | 127 (recorded baseline); 131 at Stage 8 start | 131 (not applied) |

The recorded pre-stage baseline was 127 global errors; the first Stage 8 measurement was 128. The +1 drift occurred between the earlier baseline capture and this run (a violation was introduced by intervening working-tree work). This report uses the measured Stage 8 starting value of 128.

### 3.1 Violations by Code

| Code | Changed files before | Changed files after | Global before | Global after |
|---|---:|---:|---:|---:|
| F401 unused-import | 64 | 0 | 88 | 24 |
| I001 unsorted-imports | 23 | 0 | 29 | 6 |
| F841 unused-variable | 8 | 0 | 8 | 0 |
| E741 ambiguous-variable-name | 1 | 0 | 1 | 0 |
| E402 module-import-not-at-top | 1 | 0 | 1 | 0 |
| F811 redefined-while-unused | 1 | 0 | 1 | 0 |
| **Total** | **98** | **0** | **128** | **30** |

All 30 remaining global violations are in files that are **not** part of the M09/M10 changed set (historical debt). None of the 65 changed files contributes a remaining violation.

---

## 4. Changed-File Inventory

Built from `git status --porcelain=v1`:

- 65 backend Python files total
  - 36 modified tracked files (` M`)
  - 29 untracked files (`??`, including files inside the new untracked directories `app/evaluation/`, `app/observability/`, and the Stage 1–3 remediation files)
- 34 of the 65 files had at least one ruff violation before the fixes (98 violations).
- 31 files were already clean.

The complete list is in Appendix A.

---

## 5. Before Counts per Changed File

Only files with non-zero before counts are shown.

| File | Before | Codes |
|---|---:|---|
| `backend/tests/test_m10_stage1_security_verification.py` | 17 | F401×14, F841×2, I001×1 |
| `backend/tests/test_m10_stage3_knowledge_and_retrieval.py` | 11 | F401×9, F811×1, F841×1 |
| `backend/tests/test_m08_publishing_and_api_keys.py` | 9 | F401×7, I001×2 |
| `backend/tests/test_m10_stage2_assistant_lifecycle.py` | 9 | F401×7, E741×1, I001×1 |
| `backend/app/services/evaluation_service.py` | 6 | F401×4, F841×2 |
| `backend/tests/test_groq_and_api_hardening.py` | 5 | F401×3, F841×1, I001×1 |
| `backend/tests/test_evaluation.py` | 3 | F401×2, I001×1 |
| `backend/tests/test_quota_and_byok_policy.py` | 3 | F401×2, I001×1 |
| `backend/app/models/publishing.py` | 2 | F401×2 |
| `backend/app/observability/tracer.py` | 2 | F401×2 |
| `backend/tests/test_conversations_ux.py` | 2 | F401×1, I001×1 |
| `backend/app/assistant_runtime/context.py` | 2 | F841×2 |
| `backend/app/api/v1/public_chat.py` | 2 | F401×2 |
| `backend/app/api/v1/developer.py` | 2 | F401×1, I001×1 |
| `backend/app/llm/providers/groq_provider.py` | 2 | F401×1, I001×1 |
| `backend/tests/test_markdown_normalizer.py` | 2 | F401×1, I001×1 |
| `backend/tests/test_sdk_python.py` | 2 | E402×1, I001×1 |
| `backend/alembic/versions/0009_m09_security_and_evaluation.py` | 1 | I001×1 |
| `backend/tests/test_observability.py` | 1 | I001×1 |
| `backend/tests/test_m05_provider_reliability.py` | 1 | I001×1 |
| `backend/tests/test_s3_storage.py` | 1 | I001×1 |
| `backend/app/main.py` | 1 | I001×1 |
| `backend/app/models/__init__.py` | 1 | I001×1 |
| `backend/app/models/evaluation.py` | 1 | F401×1 |
| `backend/app/api/v1/evaluation.py` | 1 | F401×1 |
| `backend/app/api/v1/observability.py` | 1 | F401×1 |
| `backend/app/api/v1/router.py` | 1 | I001×1 |
| `backend/app/repositories/assistant_repository.py` | 1 | I001×1 |
| `backend/app/services/quota_service.py` | 1 | F401×1 |
| `backend/app/storage/s3.py` | 1 | F401×1 |
| `backend/tests/test_background_recovery.py` | 1 | I001×1 |
| `backend/app/repositories/knowledge_repository.py` | 1 | I001×1 |
| `backend/app/services/ingestion/recovery.py` | 1 | I001×1 |
| `backend/app/services/publishing_service.py` | 1 | F401×1 |
| **Total** | **98** | |

After the fixes, `ruff check` on all 65 files reports:

```text
All checks passed!
```

---

## 6. Fixes Applied

### 6.1 Safe Auto-Fixes (`ruff check --fix`, no `--unsafe-fixes`)

Command (run in `backend/`, with the 65 relative paths):

```powershell
.\.venv\Scripts\python.exe -m ruff check --fix @changed_files
```

All modifications were verified by comparing the working tree against a pre-fix snapshot of the same 65 files. The auto-fix changed 33 files and only:

- sorted import blocks (I001),
- removed unused imports (F401),
- removed an unused `except Exception as ret_err` binding (F841; no behavior change),
- removed a duplicate local `VectorPoint` import that shadowed the top-level import (F811),
- normalized blank lines between import groups.

No code logic, strings, route registration order, or model definitions were altered. In particular, `include_router(...)` call order in `app/api/v1/router.py` was unchanged; only the import block was sorted, so FastAPI route precedence is unaffected.

One non-import line changed: `except Exception as ret_err:` became `except Exception:` in `app/services/evaluation_service.py`. The binding was never referenced; removing it cannot change behavior. This is the only auto-fix outside imports/blank lines, and it was intentionally kept rather than reverted.

### 6.2 Incidental Repair: Truncated `build_rag_context` (`app/assistant_runtime/context.py`)

While fixing the two F841 violations in `context.py`, the cause was found to be a **truncated function**, not ordinary dead code:

- The working-tree file ended at the Tier 2 prompt block with a dangling comment and no newline.
- The entire remainder of `build_rag_context` was missing: Tier 3 assistant instructions, Tier 4 knowledge context assembly, token-budget history pruning, construction of the `LLMMessage` array, and the `return messages, citations` statement.
- The file still parsed (implicit `return None`), so `compileall` alone would not detect it. Any caller would fail on tuple unpacking.
- `git show HEAD:backend/app/assistant_runtime/context.py` contains the complete function. The 70 deleted lines were restored verbatim from HEAD.
- The intended M09/M10 changes in the surviving part were preserved: `BIBLIOGRAPHY_PATTERN`, `strip_generated_bibliography`, `normalize_markdown`, and the updated Tier 1 security/formatting text.

Final working-tree diff for this file is exactly the intended feature change: `+85 / -2` lines (the new normalizer functions plus the two replaced Tier 1 strings). This restored both F841 usages and the runtime behavior.

This was the only functional repair in Stage 8. It is called out here because it exceeds pure lint cleanup and should be reviewed as part of the stage diff.

### 6.3 Manual Fixes

| File | Change | Reason |
|---|---|---|
| `app/assistant_runtime/context.py` | Restored truncated function tail from HEAD | Removed 2×F841 and repaired a broken prompt builder |
| `app/services/evaluation_service.py` | `judge_evaluator` → `_judge_evaluator` | Preserves constructor call; silences F841 |
| `tests/test_groq_and_api_hardening.py` | `openai_provider` → `_openai_provider` | Preserves constructor call; silences F841 |
| `tests/test_m10_stage1_security_verification.py` | `tenant_b` → `_tenant_b`, `asst_a2` → `_asst_a2` | Preserve setup side effects; silence F841 |
| `tests/test_m10_stage3_knowledge_and_retrieval.py` | `doc_repo` → `_doc_repo` | Preserves repository construction; silences F841 |
| `tests/test_m10_stage2_assistant_lifecycle.py` | `[l.action for l in logs]` → `[entry.action for entry in logs]` | E741 ambiguous name; behavior identical |
| `tests/test_sdk_python.py` | Added `# noqa: E402` to `from mmaip.client import ...` | Import must follow `sys.path.insert`; see §6.4 |

### 6.4 E402 Handling (`tests/test_sdk_python.py`)

The file must insert `sdk/python` into `sys.path` before importing the local `mmaip` package:

```python
import sys
from pathlib import Path

import pytest

sdk_path = Path(__file__).resolve().parent.parent.parent / "sdk" / "python"
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from mmaip.client import MMAIPClient, MMAIPError  # noqa: E402
```

Moving the import to the top would break collection because `mmaip` is not installed. The `# noqa: E402` is therefore intentional and narrowly scoped to that one import.

---

## 7. Remaining Global Violations — Historical Debt (Untouched Files)

All 30 remaining violations are in files with **no M09/M10 changes**. Each was checked against the changed list; all returned `IN_CHANGED=False`.

| File | Count | Codes |
|---|---:|---|
| `backend/app/services/ingestion/url_ingestion.py` | 11 | F401×11 |
| `backend/tests/test_m07_knowledge_and_providers.py` | 9 | F401×8, I001×1 |
| `backend/app/api/v1/providers.py` | 2 | F401×2 |
| `backend/app/api/v1/publishing.py` | 2 | F401×2 |
| `backend/alembic/versions/0004_assistants_and_conversations.py` | 1 | I001×1 |
| `backend/alembic/versions/0006_assistant_versions_and_configuration.py` | 1 | I001×1 |
| `backend/alembic/versions/0007_provider_credentials_and_usage.py` | 1 | I001×1 |
| `backend/alembic/versions/0008_assistant_publishing_and_api_keys.py` | 1 | I001×1 |
| `backend/app/models/assistant.py` | 1 | F401×1 |
| `backend/app/templates/schema.py` | 1 | I001×1 |
| **Total** | **30** | F401×24, I001×6 |

### 7.1 Evidence That This Debt Pre-Exists at HEAD

The two largest offenders were re-checked directly against HEAD content, not the working tree:

```powershell
git show HEAD:backend/app/api/v1/providers.py | .\.venv\Scripts\python.exe -m ruff check --stdin-filename app/api/v1/providers.py -
# Found 2 errors. (F401 x2)

git show HEAD:backend/app/services/ingestion/url_ingestion.py | .\.venv\Scripts\python.exe -m ruff check --stdin-filename app/services/ingestion/url_ingestion.py -
# Found 11 errors. (F401 x11)
```

This matches the earlier audit and confirms the debt is historical, not introduced by M09/M10. The remaining eight files are likewise unmodified in `git status`.

These files were intentionally **not** modified: fixing them would violate the Stage 8 constraint against touching unrelated files and would create unrelated churn in the remediation diff.

---

## 8. Formatting Status

`ruff format --check .` still fails:

```text
131 files would be reformatted, 97 files already formatted
```

- Pre-stage baseline: 127 files would be reformatted.
- The increase to 131 is consistent with newly added M09/M10 files entering the scan. No formatting was applied.
- Formatting is **not** part of this stage and was deliberately not run, because a repo-wide format would create a very large, unrelated diff across historical files.
- Recommendation: schedule a dedicated **formatting-only** commit after feature work is frozen:
  1. Run `ruff format .` once.
  2. Commit with no logic changes in the same commit (importantly, do not mix it with M09/M10 work).
  3. Add `ruff format --check .` to CI only after that commit lands.

---

## 9. Safety Verification

Executed sequentially from `backend/`:

### 9.1 Bytecode Compilation

```powershell
.\.venv\Scripts\python.exe -m compileall -q app tests
```

Result: exit code `0`, no errors.

### 9.2 Required Pytest Suite

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short `
  tests/test_remediation_stage1_cors.py `
  tests/test_remediation_stage2_invitation_roles.py `
  tests/test_remediation_stage3_storage.py `
  tests/test_markdown_normalizer.py
```

Exact result line:

```text
43 passed, 1 warning in 155.44s (0:02:35)
```

### 9.3 Supplementary Regression Suite

Because imports were removed from the M10 test files and `context.py` was repaired, the affected suites were also run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short `
  tests/test_m10_stage1_security_verification.py `
  tests/test_m10_stage2_assistant_lifecycle.py `
  tests/test_m10_stage3_knowledge_and_retrieval.py `
  tests/test_m05_prompt_injection.py `
  tests/test_assistants_and_rag.py
```

Exact result line:

```text
80 passed, 2 warnings in 578.35s (0:09:38)
```

This confirms that:

- removed unused imports were not required for SQLAlchemy metadata registration (all models are registered via `app/models/__init__.py`),
- the restored `build_rag_context` prompt assembly works,
- the M10 Stage 1–3 suites still pass after import cleanup and variable renames.

---

## 10. Remaining Risks

1. **Evaluation judge remains unwired (M09).**
   `EvaluationService` constructs `_judge_evaluator = JudgeEvaluator(...)` but never uses it. The lint fix preserves the constructor call (renamed with an underscore) rather than deleting it. This suggests LLM-as-judge scoring is not actually invoked in the evaluation pipeline. This is a functional gap for review, not a lint issue.

2. **API-key security matrix coverage gap (M10 Stage 1).**
   `test_developer_api_key_security_matrix` assigns `_tenant_b` and `_asst_a2` but never exercises them. The names were underscored to preserve setup without pretending they are used. A true cross-tenant key-denial assertion is still missing; this should be added in a functional stage.

3. **`context.py` truncation root cause unknown.**
   The file was truncated in the working tree only (not at HEAD) and ended without a newline. The full tail was restored from HEAD and verified by 80 passing tests. Future edits to this file should include a diff review to ensure no truncation recurs; `compileall` cannot detect a missing `return`.

4. **Historical lint debt remains and will fail a strict CI gate.**
   There are 30 violations in 10 untouched files (24 F401, 6 I001). If `ruff check .` is made blocking now, CI will fail. Either clean them in a dedicated commit or introduce a ratcheted baseline that only fails on new violations.

5. **Format debt grew from 127 to 131 files.**
   This is expected from new files and is not a regression in code quality. Deferring formatting avoids mixing unrelated churn into M09/M10 review.

6. **`# noqa: E402` is load-bearing.**
   If the SDK import is ever moved or the `sys.path` bootstrap is removed, the noqa must be re-evaluated rather than blindly retained or deleted.

---

## 11. Exact Commands Used

```powershell
# Inventory
git status --porcelain=v1
git diff --name-only --diff-filter=M
git ls-files --others --exclude-standard

# Before / after
.\.venv\Scripts\python.exe -m ruff check <65 changed files>   # 98
.\.venv\Scripts\python.exe -m ruff check .                    # 128
.\.venv\Scripts\python.exe -m ruff check --fix <65 changed files>
.\.venv\Scripts\python.exe -m ruff check <65 changed files>   # All checks passed!
.\.venv\Scripts\python.exe -m ruff check .                    # 30

# Format / compile / tests
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m compileall -q app tests
.\.venv\Scripts\python.exe -m pytest -q --tb=short <required four files>
.\.venv\Scripts\python.exe -m pytest -q --tb=short <supplementary five files>

# HEAD evidence for historical debt
git show HEAD:backend/app/api/v1/providers.py | .\.venv\Scripts\python.exe -m ruff check --stdin-filename app/api/v1/providers.py -
git show HEAD:backend/app/services/ingestion/url_ingestion.py | .\.venv\Scripts\python.exe -m ruff check --stdin-filename app/services/ingestion/url_ingestion.py -
```

No `git add`, `git commit`, `git stash`, `git reset`, or `git checkout` was executed. No repository-wide formatting was performed.

---

## Appendix A — Full Changed-File List (65 Files)

`M` = modified tracked, `U` = untracked.

```text
M backend/alembic/env.py
M backend/alembic/versions/0003_embeddings_and_vector_stores.py
U backend/alembic/versions/0009_m09_security_and_evaluation.py
U backend/alembic/versions/0010_m10_remediation_schema_alignment.py
M backend/app/api/v1/conversations.py
M backend/app/api/v1/developer.py
U backend/app/api/v1/evaluation.py
M backend/app/api/v1/ingestion.py
M backend/app/api/v1/knowledge.py
U backend/app/api/v1/observability.py
M backend/app/api/v1/public_chat.py
M backend/app/api/v1/router.py
M backend/app/assistant_runtime/__init__.py
M backend/app/assistant_runtime/context.py
U backend/app/assistant_runtime/markdown_normalizer.py
M backend/app/assistant_runtime/runtime.py
M backend/app/core/config.py
U backend/app/core/cors.py
M backend/app/embeddings/providers/openai_provider.py
U backend/app/evaluation/judge.py
U backend/app/evaluation/metrics.py
U backend/app/evaluation/starter_benchmarks.py
M backend/app/llm/base.py
M backend/app/llm/capabilities.py
M backend/app/llm/providers/groq_provider.py
M backend/app/llm/providers/openai_provider.py
M backend/app/main.py
M backend/app/models/__init__.py
U backend/app/models/evaluation.py
M backend/app/models/publishing.py
U backend/app/observability/tracer.py
M backend/app/repositories/assistant_repository.py
M backend/app/repositories/knowledge_repository.py
M backend/app/retrieval/service.py
M backend/app/schemas/assistant.py
U backend/app/schemas/evaluation.py
M backend/app/schemas/publishing.py
M backend/app/services/api_key_service.py
M backend/app/services/byok_vault.py
U backend/app/services/evaluation_service.py
U backend/app/services/ingestion/recovery.py
M backend/app/services/publishing_service.py
M backend/app/services/quota_service.py
M backend/app/storage/__init__.py
M backend/app/storage/s3.py
M backend/app/vectorstores/qdrant_store.py
U backend/tests/test_background_recovery.py
U backend/tests/test_conversations_ux.py
U backend/tests/test_evaluation.py
U backend/tests/test_groq_and_api_hardening.py
M backend/tests/test_m05_prompt_injection.py
M backend/tests/test_m05_provider_reliability.py
M backend/tests/test_m05_staging_readiness.py
M backend/tests/test_m08_publishing_and_api_keys.py
U backend/tests/test_m10_stage1_security_verification.py
U backend/tests/test_m10_stage2_assistant_lifecycle.py
U backend/tests/test_m10_stage3_knowledge_and_retrieval.py
U backend/tests/test_markdown_normalizer.py
U backend/tests/test_observability.py
U backend/tests/test_quota_and_byok_policy.py
U backend/tests/test_remediation_stage1_cors.py
U backend/tests/test_remediation_stage2_invitation_roles.py
U backend/tests/test_remediation_stage3_storage.py
U backend/tests/test_s3_storage.py
U backend/tests/test_sdk_python.py
```