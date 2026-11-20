# Milestone 05 External Execution — PostgreSQL 16 + pgvector Live Integration Plan

**Project:** Multi-Tenant AI Platform / CaaS  
**Date:** 2026-11-08  
**Audit Phase:** Phase F — PostgreSQL Live Integration Assessment  
**Auditor:** Senior Database Reliability Engineer & Application Security Auditor  

---

## 1. Execution Status & Environment Boundary

- **Execution Status:** **`NOT_RUN — PENDING EXTERNAL LINUX RUNNER`**
- **Reason:** Host physical available RAM is **1,271.36 MB**, which is below the mandatory **2,048 MB memory safety threshold**. In strict accordance with prompt directives, Docker execution locally was withheld.
- **Packaged Deliverable:** Ready for execution inside `artifacts/evaluations/m05_final_closure_20261108/portable_runner/m05_live_test_snapshot.zip`.

---

## 2. Target Container Specification & Isolation

- **Docker Image:** `pgvector/pgvector:pg16`
- **Host Port Binding:** `127.0.0.1:55432:5432` (Dedicated isolated port; zero conflict with system PostgreSQL on 5432)
- **Compose Specification:** `docker-compose.m05-postgres.yml`
- **Database Name:** `m05_integration`
- **User Credentials:** User `m05_test`, Password configured via safe test environment variable
- **Extensions Initialized:** `uuid-ossp`, `pgcrypto`, `vector` (via `infrastructure/scripts/init-db.sql`)
- **Healthcheck Probe:** `pg_isready -U m05_test -d m05_integration` (Interval: 5s, Timeout: 3s, Retries: 10)

---

## 3. Test Suite Inventory (12 Live Node IDs)

The external runner executes the following 12 exact test node IDs:

```text
tests/integration/test_postgres_connection.py::test_postgres_version_is_16
tests/integration/test_postgres_connection.py::test_pgvector_extension_loaded_and_functional
tests/integration/test_postgres_connection.py::test_transaction_rollback_and_commit_behavior
tests/integration/test_postgres_migrations.py::test_migration_head_and_schema_tables
tests/integration/test_postgres_migrations.py::test_vector_column_data_type_in_postgresql
tests/integration/test_postgres_migrations.py::test_foreign_key_and_tenant_composite_constraints
tests/integration/test_postgres_fts.py::test_native_postgresql_fts_query_and_ranking
tests/integration/test_postgres_fts.py::test_native_postgresql_fts_sql_injection_safety
tests/integration/test_pgvector_operations.py::test_real_pgvector_insert_and_cosine_distance_ranking
tests/integration/test_pgvector_operations.py::test_pgvector_rejects_dimension_mismatch
tests/integration/test_postgres_tenant_isolation.py::test_cross_tenant_isolation_on_real_postgresql
tests/integration/test_postgres_tenant_isolation.py::test_department_isolation_on_real_postgresql
```

---

## 4. Specific Properties Validated by the Suite

1. **PostgreSQL Version & Extensions:** Asserts `SHOW server_version` begins with `16` and `vector` extension is active.
2. **Real Vector Insertion & Cosine Ranking:** Inserts real floating-point vectors into `vector(1536)` columns and executes `<=>` cosine distance queries.
3. **Dimension Safety:** Asserts PostgreSQL rejects inserting dimension-mismatched vectors (e.g. 768-dim vector into 1536-dim column).
4. **Alembic Schema & Migrations:** Executes `alembic upgrade head` on the disposable database and validates table existence, foreign key constraints, and UUID primary keys.
5. **PostgreSQL Full-Text Search:** Validates native full-text search with `to_tsvector` and `ts_rank_cd` cover-density ranking (not BM25). Validates that SQL injection payloads in search queries are safely neutralized via parameterized statements.
6. **Relational Tenant & Department Isolation:** Inserts records across Tenant A, Tenant B, Department X, and Department Y; verifies that queries strictly enforce scoping at the database and repository layers.
