# MM AI Platform — M05 Portable Live Infrastructure Runner Guide

## 1. Overview & Purpose

This package provides a self-contained, reproducible test environment to execute Milestone 05's **17 container-dependent live integration tests and disaster-recovery drills**:
- **12 PostgreSQL 16 + pgvector + FTS Tests**: Validates true relational constraints, vector cosine ranking, native PostgreSQL full-text search with `ts_rank_cd`, SQL injection neutralization, and tenant isolation.
- **Live PostgreSQL Backup & Restore Drill**: Validates real `pg_dump -Fc` custom archive creation, SHA-256 manifest generation, restoration into an isolated disposable database (`m05_restore_drill_disposable`), and verification of schema, relationships, and encrypted BYOK credentials.
- **5 Qdrant v1.9.0 Tests**: Validates service health, dimension-isolated collections, vector upsert/search with payload filtering, cross-tenant isolation, and scoped deletions.
- **Live Qdrant Rebuild / Reindex Drill**: Validates collection recreation and vector/payload restoration directly from relational store without original binary dependencies.

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

## 3. Step-by-Step Execution Instructions

### Step 1: Transfer & Verify Integrity
Transfer `m05_live_test_snapshot.zip` and verify its SHA-256 hash before extraction:

```bash
sha256sum m05_live_test_snapshot.zip
```
Expected SHA-256:
```text
(Refer to portable_runner/snapshot_sha256.txt generated during packaging)
```
*(If hashes differ, abort execution immediately).*

### Step 2: Extract Snapshot into Isolated Workspace
```bash
mkdir -p ~/m05_runner
unzip m05_live_test_snapshot.zip -d ~/m05_runner
cd ~/m05_runner
```

### Step 3: Install Host Prerequisites & Set Up Virtual Environment

On Ubuntu 22.04 / 24.04 LTS, ensure required host tools are installed:
```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip unzip curl tar
```

Ensure Docker daemon is accessible by the current user:
```bash
docker info >/dev/null && echo "Docker daemon is ready."
```

Create Python 3.12 virtual environment and install both runtime and test dependencies:
> [!IMPORTANT]
> You **must** install with `.[dev]` so that `pytest` and `pytest-asyncio` are installed. Omitting `[dev]` will cause the runner to fail immediately.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
cd ..
```


### Step 4: Run Live Integration Tests & Recovery Drills
The automated runner (`infrastructure/scripts/run-live-integration-tests.sh`) accepts the following arguments:

```text
Usage: run-live-integration-tests.sh [OPTIONS]

Options:
  -m, --mode <mode>        Execution mode: postgres, qdrant, or all (default: all)
  -f, --force              Bypass available RAM and disk space checks
  --skip-drills            Skip live backup/restore and Qdrant rebuild drills
  -o, --output-dir <path>  Directory to save test outputs and logs (default: ./test_results)
  -h, --help               Display help message
```

#### Full Sequential Execution (Recommended):
```bash
chmod +x infrastructure/scripts/*.sh
./infrastructure/scripts/run-live-integration-tests.sh --mode all --output-dir ./test_results
```

#### Individual Service Suites:
```bash
# PostgreSQL 16 + pgvector tests & backup drill only
./infrastructure/scripts/run-live-integration-tests.sh --mode postgres --output-dir ./test_results_postgres

# Qdrant v1.9.0 tests & rebuild drill only
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

Upon completion of the runner, archive the entire output directory containing logs, JUnit reports, and drill evidence:

```bash
tar -czvf m05_live_evidence_results.tar.gz test_results/
```

Expected evidence files inside `test_results/`:
- `postgres_test_output.txt`
- `postgres_test_junit.xml`
- `postgres_container_logs.txt`
- `postgres_backup_restore_drill.log`
- `drill_backup_sha256.txt`
- `qdrant_test_output.txt`
- `qdrant_test_junit.xml`
- `qdrant_container_logs.txt`
- `qdrant_rebuild_drill.log`

Transfer `m05_live_evidence_results.tar.gz` back to the workspace under:
`artifacts/evaluations/m05_final_closure_20261108/`
to complete final unconditional milestone sign-off.
