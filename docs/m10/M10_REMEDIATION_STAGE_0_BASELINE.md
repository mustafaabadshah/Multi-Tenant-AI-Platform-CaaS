# M10 Remediation — Stage 0: Read-Only Baseline & Repository Inventory

**Date:** 2026-11-11
**Mode:** Read-only. No source files modified in this stage.

---

## 1. Git baseline (re-verified, current)

| Item | Value |
|---|---|
| Working directory | `E:\MM Office\Multi-Tanant-CaaS` |
| Branch | `main` |
| HEAD | `9479847b846aaae43cb8f51e81cf18aaf2646d0f` (feat(m08)) |
| vs `origin/main` | **3 ahead / 0 behind** |
| Modified tracked | 60 (includes `docs/IMPLEMENTATION_ROADMAP.md` + 2 `.dockerignore` additions from the previous integration audit) |
| Untracked entries | 32 `??` groups (105 files; includes `docs/m10/M10_FINAL_*.md` from previous audit) |
| Staged | 0 (porcelain clean of staged state) |
| Alembic head | `0009_m09_security_and_evaluation` (single head, linear chain) |

## 2. Finding re-verification matrix

| ID | Finding | Status now | File:line | Reproduction | Root cause | Severity |
|---|---|---|---|---|---|---|
| D11 | Dev CORS regex active by default | **CONFIRMED** | `backend/app/main.py:66-70` | `pytest tests/test_m05_staging_readiness.py::test_cors_origin_resolution` → 400≠200 | Gate is `settings.DEBUG or ENVIRONMENT=="development"`; both default to dev values | High |
| SEC-1 | Invite roles `manager`/`admin` unsupported by backend | **CONFIRMED** | `frontend/app/dashboard/employees/page.tsx:284-286` vs `backend/app/core/constants.py:27` (SystemRole) | invite with `manager` → `Role 'manager' does not exist` (400) | Frontend narrowed dropdown to values absent from canonical role enum | High |
| STOR-1 | Production env example uses ephemeral local storage | **CONFIRMED** | `.env.production.example:48` (`STORAGE_BACKEND=local`) | inspection | Template not updated when S3 adapter landed | High |
| MIG-1 | Fresh SQLite `alembic upgrade` fails at 0003 | **CONFIRMED** | `backend/alembic/versions/0003_embeddings_and_vector_stores.py:34,46` | `DATABASE_URL=sqlite+aiosqlite:///<temp>` + `alembic upgrade head` → `NotImplementedError` (ALTER ADD CONSTRAINT) | `op.create_foreign_key` outside batch mode is PostgreSQL-only | High |
| D5 | `aioboto3` undeclared | **CONFIRMED** | `backend/pyproject.toml` (absent); `storage/s3.py:51` lazy import | `pip check`/import smoke on S3 path | dependency never added when S3 provider landed | High |
| C2 | `fastembed`/`sentence-transformers` undeclared while `render.yaml` selects `sentence-transformers` | **CONFIRMED** | `backend/pyproject.toml` (absent); `render.yaml:67` | first embedding in staging → RuntimeError from `sentence_transformer_provider.py:82` | provider implemented after packaging freeze | High |
| T1 | 6 failing tests (289/6/18) | **CONFIRMED** — `pytest --lf` reproduces all 6 | see Stage 6 | full suite | 5 stale M05 expectations vs intentional M09/M10 behavior + 1 real D11 regression | High |
| STG6 | M10 Stage 6 report missing | **CONFIRMED** | `docs/m10/` contains no `*STAGE_6*` | directory listing | report never produced | Medium (process) |
| RUFF | ruff/format gates red; pre-existing at HEAD | **CONFIRMED** | `ci.yml` steps | `ruff check .` → 127 errors; stdin-check of unmodified tracked files at HEAD shows violations | historical debt + new-file violations | Medium |
| — | `alembic check` drift on SQLite (`chunk_embeddings.vector` NUMERIC vs VECTOR) | expected, cosmetic | `0003` migration | `alembic check` | pgvector type renders NUMERIC on SQLite | Low |
| — | `LLM_DEFAULT_MODEL` dead; OpenAI+`auto` template pair | **CONFIRMED** | `backend/app/core/config.py:92`; `.env.production.example:73-76` | grep (no consumers) | config debt | Low |
| — | `.dockerignore` files | **FIXED previously** — present and correct | `backend/.dockerignore`, `frontend/.dockerignore` | inspection | added by M10 integration audit | resolved |

## 3. Remediation decisions (proposed, stage-owner approval implied by prompt)

| Stage | Decision |
|---|---|
| 1 (D11) | Centralize CORS in `app/core/cors.py`; dev regex only when `ENVIRONMENT=="development"` AND explicitly opted-in LAN origins (`ALLOW_DEV_LAN_ORIGINS`); production fail-fast on missing/invalid origins; `create_app(settings)` factory for testability. |
| 2 (SEC-1) | **Option A — frontend correction:** expose canonical roles (`employee`, `viewer`, `knowledge_editor`, `assistant_manager`, `dept_admin`, `org_admin`) in the invite dropdown; backend already validates against the canonical registry. No new roles invented. |
| 3 (STOR-1) | Production fail-closed: raise at provider/startup when `ENVIRONMENT=production` and storage is not S3-backed or S3 config incomplete. Update `.env.production.example` to S3 with placeholders. |
| 4 (MIG-1) | Dialect-aware fix of 0003 (batch mode for non-PostgreSQL). Justification: no shared/production DB has ever run these migrations (staging never provisioned, `DEPLOYED=NO`); SQLite migration support is documented in README/`.env.example`; PostgreSQL path preserved byte-for-byte. |
| 5 (D5/C2) | Declare `fastembed` (default CPU embedding path in all deployment templates) and `aioboto3` (production storage) in core runtime dependencies; validate with `pip check` + import smoke tests in the project venv. |
| 6 (T1) | Per-test evidence-based disposition: 5 expectation updates (implementation intentionally evolved) + 1 real fix already in Stage 1; markdown normalizer implementation fixed (tests are the spec) + merge duplicate definitions (D1/D2). |
| 7 (STG6) | Produce `docs/m10/M10_STAGE_6_FINAL_REPORT.md` from verified implementation + targeted tests; no second renderer. |
| 8 (RUFF) | Fix violations only in M09/M10-touched files; document historical debt separately; no repo-wide formatting. |

## 4. Files already opened/verified for remediation

`backend/app/main.py`, `backend/app/core/config.py`, `backend/app/assistant_runtime/{context.py,markdown_normalizer.py,__init__.py,runtime.py}`, `backend/app/storage/{__init__.py,s3.py,local.py}`, `backend/alembic/versions/0003_*.py`, `backend/pyproject.toml`, `.env.example`, `.env.production.example`, `frontend/app/dashboard/employees/page.tsx`, `backend/tests/{test_m05_staging_readiness.py,test_m05_prompt_injection.py,test_m05_provider_reliability.py,test_markdown_normalizer.py}`.

## 5. Declarations

```text
STAGE_0_BASELINE_CAPTURED = YES
SOURCE_MODIFIED_IN_STAGE_0 = NO
```
