# Milestone 05 External Execution — PostgreSQL Test Selection Audit

**Project:** Multi-Tenant AI Platform / CaaS  
**Audit Phase:** Phase 4 — PostgreSQL Test Selection Audit  
**Auditor:** PostgreSQL / pgvector SRE & QA Lead  

---

## 1. Verified Test Node IDs (Exactly 12 Nodes)

The runner script (`run-live-integration-tests.sh`, lines 210–223) explicitly targets the exact 12 integration test node IDs required by Milestone 05:

| # | Exact Node ID | Target File | Core Assertion |
|---|---|---|---|
| 1 | `tests/integration/test_postgres_connection.py::test_postgres_version_is_16` | `test_postgres_connection.py` | PostgreSQL reports version 16.x |
| 2 | `tests/integration/test_postgres_connection.py::test_pgvector_extension_loaded_and_functional` | `test_postgres_connection.py` | pgvector extension active in `pg_extension` |
| 3 | `tests/integration/test_postgres_connection.py::test_transaction_rollback_and_commit_behavior` | `test_postgres_connection.py` | ACID rollback and commit semantics |
| 4 | `tests/integration/test_postgres_migrations.py::test_migration_head_and_schema_tables` | `test_postgres_migrations.py` | Alembic DAG upgrade head; tables created |
| 5 | `tests/integration/test_postgres_migrations.py::test_vector_column_data_type_in_postgresql` | `test_postgres_migrations.py` | `vector(1536)` / `vector(768)` types verified in `information_schema` |
| 6 | `tests/integration/test_postgres_migrations.py::test_foreign_key_and_tenant_composite_constraints` | `test_postgres_migrations.py` | Composite `(id, tenant_id)` foreign keys |
| 7 | `tests/integration/test_postgres_fts.py::test_native_postgresql_fts_query_and_ranking` | `test_postgres_fts.py` | Full-text search with `ts_rank_cd` density ranking |
| 8 | `tests/integration/test_postgres_fts.py::test_native_postgresql_fts_sql_injection_safety` | `test_postgres_fts.py` | Parameterized SQL neutralizing injection payloads |
| 9 | `tests/integration/test_pgvector_operations.py::test_real_pgvector_insert_and_cosine_distance_ranking` | `test_pgvector_operations.py` | Real cosine distance `<=>` operator ranking |
| 10 | `tests/integration/test_pgvector_operations.py::test_pgvector_rejects_dimension_mismatch` | `test_pgvector_operations.py` | Database-level rejection of invalid vector dimension |
| 11 | `tests/integration/test_postgres_tenant_isolation.py::test_cross_tenant_isolation_on_real_postgresql` | `test_postgres_tenant_isolation.py` | Cross-tenant document isolation on live DB |
| 12 | `tests/integration/test_postgres_tenant_isolation.py::test_department_isolation_on_real_postgresql` | `test_postgres_tenant_isolation.py` | Cross-department access restriction enforcement |

---

## 2. Test Selection & Failure Handling Audit

### 2.1 Invocation Method
```bash
(
    cd "$BACKEND_DIR"
    "$PYTHON_CMD" -m pytest "${PG_TEST_NODES[@]}" -v \
        --junitxml="${OUTPUT_DIR}/postgres_test_junit.xml" \
        2>&1 | tee "${OUTPUT_DIR}/postgres_test_output.txt"
)
PG_EXIT=${PIPESTATUS[0]}
```

### 2.2 Failure Propagation
- If any test assertion fails, Pytest returns exit code 1.
- `PIPESTATUS[0]` captures the Pytest exit code directly (bypassing `tee`).
- `PG_EXIT` triggers `POSTGRES_PASSED=false` and sets `FINAL_EXIT=1`.
- The runner terminates with exit code 1, signaling a failed execution run.

### 2.3 Skip Path Guard
Pytest returns code 0 if tests are skipped. To ensure no live test is silently skipped:
- None of the 12 integration tests in the archive contain `@pytest.mark.skip`.
- The JUnit XML output (`postgres_test_junit.xml`) must be parsed by the final release assessor to confirm:
  - `tests="12"`
  - `failures="0"`
  - `errors="0"`
  - `skipped="0"`
- Any run with `skipped > 0` must be rejected for unconditional release.
