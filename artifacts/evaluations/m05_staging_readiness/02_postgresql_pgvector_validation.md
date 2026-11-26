# M05 Phase 1 — Real PostgreSQL 16, Native FTS & pgvector Validation Report

**Project:** Multi-Tenant AI Platform / CaaS  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Execution Date:** 2026-11-07  
**Auditor:** Senior PostgreSQL & Database Integration Test Engineer  
**Status:** **PARTIAL (Implementation Validated, Dedicated Suite Created, Live Server Execution Paused Due to Physical RAM Constraints)**

---

## A. Environment & Resource Safety Audit

| Metric / Parameter | Value | Assessment |
|---|---|---|
| **Host OS** | Windows 11 Home / Pro (amd64) | Verified |
| **Python Version** | Python 3.12.3 (`backend\.venv`) | Verified |
| **Target Database Image** | `pgvector/pgvector:pg16` | Verified in Compose specification |
| **Target Port** | `127.0.0.1:55432` | Verified free (no conflicting binds) |
| **Docker CLI Version** | 25.0.3 (Build 4debf41) | Installed |
| **Docker Engine Daemon** | **STOPPED** (`//./pipe/docker_engine` not found) | Service inactive |
| **WSL2 Distros** | `docker-desktop` (Stopped), `docker-desktop-data` (Stopped) | Inactive |
| **Total Physical RAM** | 8,008,680 KB (~7.82 GB) | Hardware limit |
| **Free Physical RAM at Audit** | **980,048 KB (~957 MB)** | **BELOW 2.0 GB THRESHOLD** |
| **Free Physical RAM at Conclusion** | 1,128,664 KB (~1.10 GB) | **BELOW 2.0 GB THRESHOLD** |
| **Top Memory Consumers** | Chrome (~720 MB), Antigravity IDE (~700 MB + ~382 MB), Language Server (~308 MB), MsMpEng (~254 MB) | System load |

### Resource Safety Decision
Under Section 4 and Section 16 of the M05 specification:
> *"If available RAM is below 2 GB, do not automatically launch Docker Desktop or start a PostgreSQL container. If memory is insufficient, document the blocker and ask the user to free resources before attempting live integration."*

Because free physical memory was **957 MB – 1.10 GB** (below the 2.0 GB threshold) and the Docker engine was stopped, launching Docker Desktop and WSL2 automatically would have triggered heavy memory swapping, risking host instability. Therefore, live container startup was conservatively held, the dedicated test harness was built, and the exact commands for execution once memory is freed are provided below.

---

## B. Migration Results & Schema Inspection

### 1. Migration Chain Graph
The repository contains 4 sequential Alembic revisions:
- `0001_initial_core_schema.py` (Base multi-tenant schema: tenants, users, roles, permissions, departments, groups)
- `0002_document_ingestion_engine.py` (Documents, versions, chunks, ingestion jobs, deduplication)
- `0003_embeddings_and_vector_stores.py` (Retrieval configs, chunk_embeddings table, pgvector extension, embedding jobs)
- `0004_assistants_and_conversations.py` (Assistants, knowledge links, conversations, messages, citations)

- **Expected Head Revision:** `0004_assistants_and_conversations`
- **Dialect Handling:**
  - In `0003_embeddings_and_vector_stores.py`, line 28 explicitly checks `if bind.dialect.name == "postgresql": op.execute("CREATE EXTENSION IF NOT EXISTS vector")`.
  - Column `vector` is mapped to `Vector()`, which in pgvector 0.2.5+ creates a dynamic vector column without locking the schema to a fixed 1536 dimension.
- **Relational Integrity:**
  - Foreign key constraints link `assistant_knowledge_bases` to `assistants.id` and `knowledge_bases.id` with `ondelete="CASCADE"`.
  - Every tenant entity enforces composite or explicit `tenant_id` foreign keys to `tenants.id`.

---

## C. Native PostgreSQL Full-Text Search (FTS) Implementation

### 1. Code Inspection
In `backend/app/vectorstores/fts_store.py`:
- **PostgreSQL Branch:** When `dialect_name == "postgresql"`, the store generates native PostgreSQL FTS calls:
  ```python
  ts_query = func.plainto_tsquery("english", cleaned_query)
  ts_vector = func.to_tsvector("english", DocumentChunk.content)
  rank_col = func.ts_rank_cd(ts_vector, ts_query).label("rank_score")
  stmt = stmt.add_columns(rank_col).where(ts_vector.op("@@")(ts_query)).order_by(rank_col.desc()).limit(top_k)
  ```
- **Ranking Algorithm:** `ts_rank_cd` (Cover Density ranking), which measures the proximity and density of query lexemes within the document chunk.
- **Language Dictionary:** `"english"` Snowball stemmer with stop-word removal.
- **Parameterization:** User queries are passed as bound parameters to `plainto_tsquery`, preventing raw SQL string interpolation.
- **SQLite Fallback:** When running under SQLite in memory, lines 135–214 tokenize keywords in Python. This is an explicit unit-test fallback, not native PostgreSQL FTS.

---

## D. pgvector Implementation & Dimensional Safety

### 1. Code Inspection
In `backend/app/vectorstores/pgvector_store.py`:
- **PostgreSQL Branch:**
  ```python
  cosine_dist = ChunkEmbedding.vector.cosine_distance(query_vector)
  stmt = stmt.order_by(cosine_dist).limit(top_k)
  ```
  This emits the native pgvector `<=>` operator in PostgreSQL.
- **Dimensional Isolation (Option B):**
  - Line 41: Validates that `actual_dim == p.dimensions` before upsert.
  - Line 91: Validates that `len(query_vector) == filter_criteria.expected_dimensions`.
  - Line 118: Explicit SQL filter: `ChunkEmbedding.dimensions == query_dim`. This prevents queries against spaces of different dimensionalities (e.g., 384 vs 1536).

---

## E. Security & Authorization Inspection

- **Multi-Tenant Isolation:**
  - `PostgresFTSStore` filters `DocumentChunk.tenant_id == filter_criteria.tenant_id`.
  - `PgVectorStore` filters `ChunkEmbedding.tenant_id == filter_criteria.tenant_id`.
  - `RetrievalAuthorizer.filter_authorized_candidates` re-queries the authoritative `Document` table to discard deleted documents (`status == 'DELETED'`), department mismatches, and revoked access before candidates leave the backend.
- **Cross-Tenant Guessed UUIDs:** If Tenant B attempts to pass Tenant A's KB UUID, `RetrievalAuthorizer.validate_knowledge_bases` raises `PermissionError("Unauthorized or non-existent knowledge bases")`.

---

## F. Test Suite Execution Evidence

### 1. Unit & Regression Suite (SQLite In-Memory)
- **Command:** `.venv\Scripts\python -m pytest tests/ -m "not postgres_integration" -v`
- **Result:** **70 passed, 12 deselected in 82.69s (100% pass rate)**.
- **Evidence:** All M01–M04 unit tests remain clean and unregressed.

### 2. Dedicated PostgreSQL Integration Suite (Live Target)
- **Command:** `.venv\Scripts\python -m pytest tests/integration/ -v`
- **Result:** **12 skipped in 10.46s (0 failures, 0 errors)**.
- **Skip Reason:** Live PostgreSQL 16 instance is not online at `127.0.0.1:55432` (`is_postgres_online()` cleanly detected offline daemon and skipped without false passes).
- **Test Inventory Created:**
  1. `test_postgres_connection.py::test_postgres_version_is_16`
  2. `test_postgres_connection.py::test_pgvector_extension_loaded_and_functional`
  3. `test_postgres_connection.py::test_transaction_rollback_and_commit_behavior`
  4. `test_postgres_migrations.py::test_migration_head_and_schema_tables`
  5. `test_postgres_migrations.py::test_vector_column_data_type_in_postgresql`
  6. `test_postgres_migrations.py::test_foreign_key_and_tenant_composite_constraints`
  7. `test_postgres_fts.py::test_native_postgresql_fts_query_and_ranking`
  8. `test_postgres_fts.py::test_native_postgresql_fts_sql_injection_safety`
  9. `test_pgvector_operations.py::test_real_pgvector_insert_and_cosine_distance_ranking`
  10. `test_pgvector_operations.py::test_pgvector_rejects_dimension_mismatch`
  11. `test_postgres_tenant_isolation.py::test_cross_tenant_isolation_on_real_postgresql`
  12. `test_postgres_tenant_isolation.py::test_department_isolation_on_real_postgresql`

---

## G. Fixes & Files Added

1. **`docker-compose.m05-postgres.yml`**:
   - Added isolated service specification binding strictly to `127.0.0.1:55432` using `pgvector/pgvector:pg16`.
   - Bounded container memory to `512m` and shared memory to `128m` for conservative resource usage.
2. **`backend/pyproject.toml`**:
   - Registered `postgres_integration` marker in `[tool.pytest.ini_options]` so that unit and integration test runs can be cleanly separated.
3. **`backend/tests/integration/`**:
   - Created dedicated integration testing package with fixtures (`conftest_postgres.py`) and 12 live validation tests.
4. **Ruff Lint Fixes**:
   - Organized imports in `backend/alembic/versions/0004_assistants_and_conversations.py` and `backend/app/assistant_runtime/runtime.py`.
   - Removed unused `settings` import in `backend/app/llm/providers/openai_provider.py`.

---

## H. Limitations & Exact Instructions for Manual Live Execution

### Current Limitation:
Live PostgreSQL 16 + pgvector operations were **NOT RUN** against a live container during this automated run because available physical RAM on the Windows host was **957 MB – 1.10 GB** (below the 2.0 GB safety threshold), and the Docker daemon was stopped.

### Instructions to Run Live PostgreSQL Integration When Memory is Freed:

1. **Free Host RAM:**
   Close heavy browser tabs (Chrome is consuming ~720 MB) or background applications to bring available memory above 2.0 GB.

2. **Start Docker Desktop Service:**
   ```powershell
   Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
   # Wait for Docker engine to enter 'running' state
   docker info
   ```

3. **Start the Isolated M05 PostgreSQL Container:**
   ```powershell
   Set-Location "E:\MM Office\Multi-Tanant-CaaS"
   docker compose -f docker-compose.m05-postgres.yml up -d
   ```

4. **Execute the PostgreSQL 16 & pgvector Integration Suite:**
   ```powershell
   Set-Location "E:\MM Office\Multi-Tanant-CaaS\backend"
   .venv\Scripts\python -m pytest tests/integration/ -m postgres_integration -v
   ```

5. **Stop the Isolated Container After Validation:**
   ```powershell
   Set-Location "E:\MM Office\Multi-Tanant-CaaS"
   docker compose -f docker-compose.m05-postgres.yml down
   ```

---

## I. Git Status & Verification

```powershell
git status --short
 M backend/alembic/versions/0004_assistants_and_conversations.py
 M backend/app/assistant_runtime/runtime.py
 M backend/app/llm/providers/openai_provider.py
 M backend/pyproject.toml
?? artifacts/evaluations/m05_staging_readiness/02_postgresql_pgvector_validation.md
?? artifacts/evaluations/m05_staging_readiness/results/postgresql_integration_results.json
?? backend/tests/integration/
?? docker-compose.m05-postgres.yml
```

- **Branch:** `main`
- **HEAD Commit:** `448431c4b004dc4b134dc94705b7dd96d0f2a9f5`
- No destructive git operations were executed. No changes were committed or pushed.
