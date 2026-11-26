# M11 Continuation - Stage 0 Repository Baseline (Read-Only)

| Field | Value |
|---|---|
| Milestone | M11 continuation - production hardening |
| Stage | 0 - Repository baseline and preservation checkpoint |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Branch | `main` |
| Execution window (UTC) | 2026-11-12T10:38:28Z to 2026-11-12T10:41Z |
| Execution window (local, PKT) | 2026-11-12T15:38:28+05:00 to 15:41+05:00 |
| Shell | Windows PowerShell 5.1 |
| Git | 2.45.2.windows.1 (`core.autocrlf=true`) |
| Python | 3.12.3 (`backend\.venv\Scripts\python.exe`) |
| Mode | READ-ONLY baseline. No Git mutation, install, Docker change, or deletion. |
| Writes | `docs/m11/M11_CONTINUATION_STAGE_0_BASELINE.md` (this file) only. |

> **Status statement**
>
> Every value below is an exact command result recorded during this run. Nothing is
> inferred from a previous milestone. Uncommitted M11 work was expected and is treated
> as expected; each item is nevertheless classified explicitly in Section 3.

---

## 1. Environment

| Item | Measured value |
|---|---|
| Repository root | `E:\MM Office\Multi-Tanant-CaaS` |
| Tracked files (`git ls-files`) | 758 |
| Branch | `main` |
| Working tree state | 4 modified tracked files, 12 untracked files (6 status entries), 0 staged, 0 deleted |
| Git remote | `origin` = `https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS.git` (fetch and push) |
| Git line-ending normalization | `core.autocrlf=true`; Git emitted `LF will be replaced by CRLF` warnings for the four modified files. Warnings only, no content change. |
| Backend venv | `backend\.venv\Scripts\python.exe` (Python 3.12.3) |

---

## 2. Exact Git State

### 2.1 Identity and divergence

```text
$ git branch --show-current
main

$ git rev-parse HEAD
fdb12463a8308d86015cba8d82546faf0f546c8b

$ git rev-parse origin/main
fdb12463a8308d86015cba8d82546faf0f546c8b

$ git rev-list --left-right --count origin/main...HEAD
0	0
```

`0	0` means 0 commits exist only on `origin/main` and 0 commits exist only on `HEAD`.
Local `main` is therefore identical to `origin/main`, and it contains the expected
remote commit `fdb12463a8308d86015cba8d82546faf0f546c8b` by being exactly that commit.
There is no ahead/behind divergence.

### 2.2 Status

```text
$ git status --branch
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   backend/alembic/env.py
	modified:   backend/alembic/versions/0009_m09_security_and_evaluation.py
	modified:   backend/pyproject.toml
	modified:   backend/tests/integration/conftest.py

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	docs/m10/M10_GITHUB_PUBLICATION_VERIFICATION.md
	docs/m10/M10_GIT_COMMIT_AND_GITHUB_PUSH_FINAL_REPORT.md
	docs/m10/M10_GIT_EXECUTION_STAGE_0.md
	docs/m10/M10_GIT_EXECUTION_STAGE_1.md
	docs/m10/M10_GIT_EXECUTION_STAGE_10.md
	docs/m11/
```

```text
$ git status --short
 M backend/alembic/env.py
 M backend/alembic/versions/0009_m09_security_and_evaluation.py
 M backend/pyproject.toml
 M backend/tests/integration/conftest.py
?? docs/m10/M10_GITHUB_PUBLICATION_VERIFICATION.md
?? docs/m10/M10_GIT_COMMIT_AND_GITHUB_PUSH_FINAL_REPORT.md
?? docs/m10/M10_GIT_EXECUTION_STAGE_0.md
?? docs/m10/M10_GIT_EXECUTION_STAGE_1.md
?? docs/m10/M10_GIT_EXECUTION_STAGE_10.md
?? docs/m11/
```

`git status --porcelain --untracked-files=all` expands `docs/m11/` to 7 files, so the
untracked file count is 12 (5 in `docs/m10/`, 7 in `docs/m11/`).

### 2.3 Remotes and history

```text
$ git remote -v
origin	https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS.git (fetch)
origin	https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS.git (push)

$ git log --oneline --decorate -5
fdb1246 (HEAD -> main, origin/main) docs(m10): record final integration audit and release evidence
b67296a docs(m10): record remediation stages and test reconciliation evidence
f41b460 fix(rbac): align invitation roles with canonical registry
cbbfc69 fix(security): fail-closed CORS, tenant-safe storage, and dedicated BYOK key
cfac4eb feat(m10): markdown rendering and citation quality (stage 6)
```

### 2.4 Working-tree diff

```text
$ git diff --stat
 backend/alembic/env.py                             | 24 ++++++++++++++++++++++
 .../versions/0009_m09_security_and_evaluation.py   |  6 +++---
 backend/pyproject.toml                             |  2 ++
 backend/tests/integration/conftest.py              |  4 ----
 4 files changed, 29 insertions(+), 7 deletions(-)

$ git diff --name-status
M	backend/alembic/env.py
M	backend/alembic/versions/0009_m09_security_and_evaluation.py
M	backend/pyproject.toml
M	backend/tests/integration/conftest.py

$ git diff --numstat
24	0	backend/alembic/env.py
3	3	backend/alembic/versions/0009_m09_security_and_evaluation.py
2	0	backend/pyproject.toml
0	4	backend/tests/integration/conftest.py

$ git diff --cached --stat
(empty)
```

---

## 3. Complete Inventory and Classification

Class codes:

- **(a) M11-PG-REMEDIATION** - the four reported PostgreSQL remediation files.
- **(b) M11-DOCS** - M11 stage/report documents.
- **(c) M10-LOCAL-EVIDENCE** - pre-existing M10 local-only evidence documents.
- **(d) UNEXPECTED** - anything not explained by the above.

| # | Path | Git state | Size (bytes) | Class | Attribution evidence |
|---|---|---|---|---|---|
| 1 | `backend/alembic/env.py` | Modified (tracked) | - | (a) | `docs/m11/M11_STAGE_2_POSTGRESQL_VALIDATION.md:841` item D1 |
| 2 | `backend/alembic/versions/0009_m09_security_and_evaluation.py` | Modified (tracked) | - | (a) | `M11_STAGE_2_POSTGRESQL_VALIDATION.md:842` item D2 |
| 3 | `backend/tests/integration/conftest.py` | Modified (tracked) | - | (a) | `M11_STAGE_2_POSTGRESQL_VALIDATION.md:843-844` items D3, D4 |
| 4 | `backend/pyproject.toml` | Modified (tracked) | - | (a) | `M11_STAGE_2_POSTGRESQL_VALIDATION.md:845` item D5 |
| 5 | `docs/m11/M11_STAGE_0_BASELINE.md` | Untracked | 19530 | (b) | M11 Stage 0 read-only baseline |
| 6 | `docs/m11/M11_STAGE_1_ARCHITECTURE_DECISION.md` | Untracked | 86096 | (b) | M11 Stage 1 architecture decision (awaiting approval) |
| 7 | `docs/m11/M11_STAGE_2_POSTGRESQL_VALIDATION.md` | Untracked | 43962 | (b) | M11 Stage 2 live PostgreSQL validation; source of items D1-D5 |
| 8 | `docs/m11/M11_STAGE_5_BACKGROUND_JOB_RELIABILITY.md` | Untracked | 74297 | (b) | M11 Stage 5 background job reliability |
| 9 | `docs/m11/M11_STAGE_7_SECURITY_AND_PRIVATE_TESTING.md` | Untracked | 37506 | (b) | M11 Stage 7 security/private testing readiness |
| 10 | `docs/m11/M11_STAGE_8_STORAGE_AND_BACKUP.md` | Untracked | 115274 | (b) | M11 Stage 8 storage, backup, lifecycle |
| 11 | `docs/m11/M11_STAGE_10_MANUAL_UI_ACCEPTANCE.md` | Untracked | 48735 | (b) | M11 Stage 10 manual UI acceptance handoff |
| 12 | `docs/m10/M10_GIT_EXECUTION_STAGE_0.md` | Untracked | 9129 | (c) | Pre-existing M10 execution evidence (2026-11-12T13:39:15) |
| 13 | `docs/m10/M10_GIT_EXECUTION_STAGE_1.md` | Untracked | 18788 | (c) | Pre-existing M10 execution evidence (2026-11-12T13:40:20) |
| 14 | `docs/m10/M10_GIT_EXECUTION_STAGE_10.md` | Untracked | 12727 | (c) | Pre-existing M10 execution evidence (2026-11-12T14:25:14) |
| 15 | `docs/m10/M10_GITHUB_PUBLICATION_VERIFICATION.md` | Untracked | 3530 | (c) | Pre-existing M10 publication evidence (2026-11-12T14:26:43) |
| 16 | `docs/m10/M10_GIT_COMMIT_AND_GITHUB_PUSH_FINAL_REPORT.md` | Untracked | 9849 | (c) | Pre-existing M10 push evidence (2026-11-12T14:26:59) |

Totals: 16 items = 4 modified tracked + 12 untracked files. Classification totals:
(a) 4, (b) 7, (c) 5, (d) 0.

No untracked or modified path exists outside `backend/` and `docs/`:

```text
$ git ls-files --others --exclude-standard | Where-Object { $_ -notmatch '^docs/' }
(empty)
```

---

## 4. Verification of the Four Remediation Files

Hunk register (headers captured with `git diff --unified=0`):

| File | Git hunk header | Working-tree lines | Change | Verified |
|---|---|---|---|---|
| `backend/alembic/env.py` | `@@ -35,0 +36,22 @@ def run_migrations_offline` | 36-57 (helper), 59-60 (call) | Added PostgreSQL `alembic_version` capacity helper and call site | YES |
| `backend/alembic/versions/0009_m09_security_and_evaluation.py` | `@@ -55 +55 @@` | 55 | `is_system` default `sa.text("0")` -> `sa.false()` | YES |
| `backend/alembic/versions/0009_m09_security_and_evaluation.py` | `@@ -73,2 +73,2 @@` | 73-74 | `is_unanswerable`, `is_adversarial` defaults -> `sa.false()` | YES |
| `backend/tests/integration/conftest.py` | `@@ -112 +111,0 @@` | removed old line 112 | Dropped `is_active=True` (user_a) | YES |
| `backend/tests/integration/conftest.py` | `@@ -140 +138,0 @@` | removed old line 140 | Dropped `code="ENG"` (dept_a) | YES |
| `backend/tests/integration/conftest.py` | `@@ -150 +147,0 @@` | removed old line 150 | Dropped `is_active=True` (user_b) | YES |
| `backend/tests/integration/conftest.py` | `@@ -178 +174,0 @@` | removed old line 178 | Dropped `code="MKT"` (dept_b) | YES |
| `backend/pyproject.toml` | `@@ -63,0 +64,2 @@ asyncio_mode = "auto"` | 64-65 | Added session-scoped asyncio loop defaults | YES |

### 4.1 `backend/alembic/env.py` - PostgreSQL version-table capacity helper

New lines 36-55 (function) and 59-60 (call inside `do_run_migrations`):

```python
36: def _ensure_version_table_capacity(connection: Connection) -> None:
37:     """Widen alembic_version.version_num on PostgreSQL.
...
43:     if connection.dialect.name != "postgresql":
44:         return
45:     # Commit this DDL immediately so Alembic's own migration transaction still owns
46:     # (and commits) the migration work instead of inheriting an implicit transaction.
47:     with connection.begin():
48:         connection.exec_driver_sql(
49:             "CREATE TABLE IF NOT EXISTS alembic_version ("
50:             "version_num VARCHAR(255) NOT NULL, "
51:             "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
52:         )
53:         connection.exec_driver_sql(
54:             "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
55:         )
...
58: def do_run_migrations(connection: Connection) -> None:
59:     # Must run before context.configure so Alembic finds a sufficiently wide version table.
60:     _ensure_version_table_capacity(connection)
```

Supporting check: `Connection` is imported at `backend/alembic/env.py:5`
(`from sqlalchemy.engine import Connection`), so the annotation resolves. The guard at
line 43 restricts the DDL to PostgreSQL; SQLite and offline mode are untouched.

### 4.2 `0009_m09_security_and_evaluation.py` - boolean `sa.false()` defaults

```python
55:         sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
...
73:         sa.Column("is_unanswerable", sa.Boolean(), nullable=False, server_default=sa.false()),
74:         sa.Column("is_adversarial", sa.Boolean(), nullable=False, server_default=sa.false()),
```

Residual scan for `sa.text("0")` in this file returns no matches; the three replacements
are complete. Names, types, nullability, and constraint clauses are otherwise unchanged
(diff is 3 insertions / 3 deletions).

### 4.3 `backend/tests/integration/conftest.py` - invalid seeding kwargs removed

```python
107:     user_a = User(
...
111:         full_name="Alice Owner",
112:     )
...
135:     dept_a = Department(
136:         id=uuid.uuid4(),
137:         tenant_id=tenant_a.id,
138:         name="Engineering",
139:     )
...
143:     user_b = User(
...
147:         full_name="Bob Owner",
148:     )
...
171:     dept_b = Department(
172:         id=uuid.uuid4(),
173:         tenant_id=tenant_b.id,
174:         name="Marketing",
175:     )
```

Residual scan of the whole file for `is_active` and `code=` returns no matches. The diff
is deletion-only (0 insertions / 4 deletions), so test intent and IDs are unchanged.

### 4.4 `backend/pyproject.toml` - async loop scope settings

```toml
62: [tool.pytest.ini_options]
63: asyncio_mode = "auto"
64: asyncio_default_fixture_loop_scope = "session"
65: asyncio_default_test_loop_scope = "session"
```

---

## 5. Migration Head

```text
$ cd backend
$ .\.venv\Scripts\python.exe -m alembic heads
0010_m10_remediation_schema_alignment (head)
```

Single head, matching the expected value. `alembic heads` reads the script directory
only; it does not connect to a database.

Revision chain (`backend/alembic/versions/*.py`, 10 files):

| # | File | Revision ID | Length | down_revision |
|---|---|---|---|---|
| 1 | `0001_initial_core_schema.py` | `0001_initial_core_schema` | 24 | `None` |
| 2 | `0002_document_ingestion_engine.py` | `0002_document_ingestion_engine` | 30 | `0001_initial_core_schema` |
| 3 | `0003_embeddings_and_vector_stores.py` | `0003_embeddings_and_vector_stores` | 33 | `0002_document_ingestion_engine` |
| 4 | `0004_assistants_and_conversations.py` | `0004_assistants_and_conversations` | 33 | `0003_embeddings_and_vector_stores` |
| 5 | `0005_add_assistant_byok_encrypted_key.py` | `0005_add_assistant_byok_encrypted_key` | 37 | `0004_assistants_and_conversations` |
| 6 | `0006_assistant_versions_and_configuration.py` | `0006_assistant_versions_and_configuration` | 41 | `0005_add_assistant_byok_encrypted_key` |
| 7 | `0007_provider_credentials_and_usage.py` | `0007_provider_credentials_and_usage` | 35 | `0006_assistant_versions_and_configuration` |
| 8 | `0008_assistant_publishing_and_api_keys.py` | `0008_assistant_publishing_and_api_keys` | 38 | `0007_provider_credentials_and_usage` |
| 9 | `0009_m09_security_and_evaluation.py` | `0009_m09_security_and_evaluation` | 32 | `0008_assistant_publishing_and_api_keys` |
| 10 | `0010_m10_remediation_schema_alignment.py` | `0010_m10_remediation_schema_alignment` | 37 | `0009_m09_security_and_evaluation` |

The chain is linear with exactly one head. Eight of the ten revision IDs exceed
Alembic's default `VARCHAR(32)` version column, including the head (37 characters), which
is precisely the failure the `env.py` helper in Section 4.1 remediates.

---

## 6. Documentation and Artifact Inventory

### 6.1 `docs/m11/` (7 files, all untracked, 425,400 bytes total)

| File | Bytes | Modified (local) |
|---|---|---|
| `M11_STAGE_0_BASELINE.md` | 19530 | 2026-11-12T14:47:47 |
| `M11_STAGE_1_ARCHITECTURE_DECISION.md` | 86096 | 2026-11-12T15:03:39 |
| `M11_STAGE_2_POSTGRESQL_VALIDATION.md` | 43962 | 2026-11-12T15:30:06 |
| `M11_STAGE_5_BACKGROUND_JOB_RELIABILITY.md` | 74297 | 2026-11-12T14:53:39 |
| `M11_STAGE_7_SECURITY_AND_PRIVATE_TESTING.md` | 37506 | 2026-11-12T14:49:24 |
| `M11_STAGE_8_STORAGE_AND_BACKUP.md` | 115274 | 2026-11-12T14:56:50 |
| `M11_STAGE_10_MANUAL_UI_ACCEPTANCE.md` | 48735 | 2026-11-12T14:47:41 |

`git ls-files docs/m11` is empty: every M11 document is local-only and untracked. Stages
3, 4, 6, and 9 have no document in this directory; that is an observed documentation
gap, not a repository anomaly.

### 6.2 `docs/m10/` - five local-only evidence files

| File | Exists | Bytes | Modified (local) |
|---|---|---|---|
| `M10_GITHUB_PUBLICATION_VERIFICATION.md` | YES | 3530 | 2026-11-12T14:26:43 |
| `M10_GIT_COMMIT_AND_GITHUB_PUSH_FINAL_REPORT.md` | YES | 9849 | 2026-11-12T14:26:59 |
| `M10_GIT_EXECUTION_STAGE_0.md` | YES | 9129 | 2026-11-12T13:39:15 |
| `M10_GIT_EXECUTION_STAGE_1.md` | YES | 18788 | 2026-11-12T13:40:20 |
| `M10_GIT_EXECUTION_STAGE_10.md` | YES | 12727 | 2026-11-12T14:25:14 |

`docs/m10/` contains 78 files in total: 63 tracked `.md` at the top level plus 15 tracked
screenshots under `docs/m10/evidence/stage4/screenshots/`. The five files above are the
only untracked M10 files, and all five predate this stage.

### 6.3 New artifacts outside ignored paths

None. The only untracked files in the repository are the 12 `docs/` files classified in
Section 3. Newer-than-HEAD files that exist elsewhere are all inside ignored paths:

| Artifact | Ignore rule | Note |
|---|---|---|
| `backend/data/observability_traces.json` | `.gitignore:51` (`data/`) | Runtime trace output |
| `backend/data/storage/tenants/...` (7 KB document fixtures) | `.gitignore:51` (`data/`) | Ingestion test storage |
| `sdk/typescript/dist/index.{js,js.map,d.ts,d.ts.map}` | `.gitignore:9` (`dist/`) | Build output |
| `backend/test.db` (0 bytes, 2026-11-11) | `.gitignore:53` (`*.db`) | Pre-existing, empty |
| `backend/local.db` (0 bytes, 2026-11-08) | `.gitignore:53` (`*.db`) | Pre-existing, empty |

No test database, log, or screenshot was created outside an ignored path by this stage.

---

## 7. Integrity Checks

| Check | Result | Evidence |
|---|---|---|
| Staged files | 0 | `git diff --cached --stat` and `git diff --cached --name-status` both empty |
| Deleted tracked files | 0 | `git status --porcelain` contains no `D` status |
| Git history changed | NO | `HEAD` = `fdb12463a8308d86015cba8d82546faf0f546c8b`; reflog top is the same commit at 2026-11-12 14:08:24 +05:00; no new reflog entry |
| Remote changed | NO | `origin` URL unchanged; `origin/main` = `HEAD`; no fetch/push performed |
| Stash created | NO | `git stash list` empty |
| Branch changed | NO | `git branch --show-current` = `main` throughout |
| `.git/FETCH_HEAD` | Pre-existing | 2026-11-12T14:26:33, earlier than this stage's first command |

`git diff` reports only the four expected remediation hunks, so the `LF -> CRLF`
warnings are normalization notices, not content changes.

---

## 8. Unexpected-Change Assessment

**UNEXPECTED CHANGES: NONE.**

All 16 items in Section 3 are explained:

- The four modified tracked files are exactly the four reported PostgreSQL remediation
  files, and each hunk matches its reported intent (Section 4).
- The seven untracked `docs/m11/` files are M11 stage reports, including the Stage 2
  document that specifies remediation items D1-D5.
- The five untracked `docs/m10/` files are the pre-existing local-only M10 evidence set,
  all older than this stage.
- Nothing is untracked outside `docs/`, nothing is staged, and nothing is deleted.
- The working tree is otherwise clean relative to `HEAD`, which equals `origin/main`.

The expected remote commit is present locally as `HEAD` itself, with zero divergence in
either direction.

---

## 9. Preservation Declaration

```text
UNCOMMITTED_WORK_PRESERVED = YES
GIT_MUTATIONS = NONE
```

No `git add`, `commit`, `push`, `fetch`, `pull`, `branch`, `stash`, `reset`, `checkout`,
`restore`, `clean`, or `rm` was executed. No file was deleted, moved, or renamed. No
package was installed and no Docker state was changed. The single write in this stage is
this document.

---

## 10. Gate Decision

```text
STAGE 0 GATE = GO
```

No unexplained change exists, the expected remote commit is present, exactly one migration
head exists, and all uncommitted work remains intact. Stage 0 places no blocker on
proceeding. Uncommitted changes remain uncommitted by design; committing, staging, or
pushing is out of scope for this stage.