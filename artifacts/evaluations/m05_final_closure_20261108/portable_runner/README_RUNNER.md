# MM AI Platform — M05 Portable Live Infrastructure Runner Guide

## 1. Overview & Purpose

This package provides a self-contained, reproducible test environment to execute Milestone 05's **17 container-dependent live integration tests**:
- **12 PostgreSQL 16 + pgvector + FTS Tests**: Validating true relational constraints, vector cosine ranking, native FTS ts_rank_cd, SQL injection neutralization, and tenant isolation.
- **5 Qdrant v1.9.0 Tests**: Validating service health, dimension-isolated collections, vector upsert/search with payload filtering, cross-tenant isolation, and scoped deletions.

This runner is designed to execute on an external Linux machine or dedicated CI runner with sufficient RAM ($\ge 4$ GB) to guarantee zero memory thrashing and complete test reproducibility.

---

## 2. Runner System Requirements

| Component | Minimum Requirement | Recommended |
|---|---|---|
| **OS** | Ubuntu 22.04 LTS / 24.04 LTS / Debian 12 | Ubuntu 24.04 LTS |
| **Available RAM** | 4,096 MB free physical memory | 7,168 MB+ free memory |
| **CPU** | 2 cores (x86_64 or arm64) | 4+ cores |
| **Disk Space** | 5 GB free storage | 10 GB+ SSD |
| **Docker Engine** | Docker 24.0+ with Docker Compose v2 | Docker 26.0+ |
| **Python** | Python 3.12 (with `venv` and `pip`) | Python 3.12.3+ |

---

## 3. Quick-Start Execution Instructions

### Step 1: Transfer & Unpack Snapshot
```bash
# Verify archive integrity
sha256sum -c snapshot_sha256.txt

# Unzip archive into clean workspace
unzip m05_live_test_snapshot.zip -d m05_live_runner
cd m05_live_runner
```

### Step 2: Set Up Python 3.12 Virtual Environment
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
cd ..
```

### Step 3: Run Live Integration Tests
The automated runner supports sequential execution of both PostgreSQL and Qdrant container suites:

```bash
chmod +x infrastructure/scripts/run-live-integration-tests.sh

# Run all 17 live integration tests sequentially
./infrastructure/scripts/run-live-integration-tests.sh --mode all --output-dir ./test_results
```

Alternatively, run specific service suites individually:
```bash
# PostgreSQL 16 + pgvector suite only (12 tests)
./infrastructure/scripts/run-live-integration-tests.sh --mode postgres --output-dir ./test_results_postgres

# Qdrant v1.9.0 suite only (5 tests)
./infrastructure/scripts/run-live-integration-tests.sh --mode qdrant --output-dir ./test_results_qdrant
```

---

## 4. Test Suite Inventory

### PostgreSQL 16 + pgvector (12 Node IDs)
1. `tests/integration/test_postgres_connection.py::test_postgres_version_is_16`
2. `tests/integration/test_postgres_connection.py::test_pgvector_extension_loaded_and_functional`
3. `tests/integration/test_postgres_connection.py::test_transaction_rollback_and_commit_behavior`
4. `tests/integration/test_postgres_migrations.py::test_migration_head_and_schema_tables`
5. `tests/integration/test_postgres_migrations.py::test_vector_column_data_type_in_postgresql`
6. `tests/integration/test_postgres_migrations.py::test_foreign_key_and_tenant_composite_constraints`
7. `tests/integration/test_postgres_fts.py::test_native_postgresql_fts_query_and_ranking`
8. `tests/integration/test_postgres_fts.py::test_native_postgresql_fts_sql_injection_safety`
9. `tests/integration/test_pgvector_operations.py::test_real_pgvector_insert_and_cosine_distance_ranking`
10. `tests/integration/test_pgvector_operations.py::test_pgvector_rejects_dimension_mismatch`
11. `tests/integration/test_postgres_tenant_isolation.py::test_cross_tenant_isolation_on_real_postgresql`
12. `tests/integration/test_postgres_tenant_isolation.py::test_department_isolation_on_real_postgresql`

### Qdrant v1.9.0 (5 Node IDs)
1. `tests/integration/test_qdrant_live_integration.py::test_qdrant_service_connectivity_and_health`
2. `tests/integration/test_qdrant_live_integration.py::test_qdrant_collection_creation_and_dimension_isolation`
3. `tests/integration/test_qdrant_live_integration.py::test_qdrant_upsert_and_filtered_search`
4. `tests/integration/test_qdrant_live_integration.py::test_qdrant_cross_tenant_payload_isolation`
5. `tests/integration/test_qdrant_live_integration.py::test_qdrant_scoped_deletion`

---

## 5. Returning Evidence Artifacts

Upon completion, package the generated `test_results/` directory:
```bash
tar -czvf m05_live_evidence_results.tar.gz test_results/
```
Transfer `m05_live_evidence_results.tar.gz` back to the repository workspace under:
`artifacts/evaluations/m05_final_closure_20261108/`
to complete final unconditional sign-off.
