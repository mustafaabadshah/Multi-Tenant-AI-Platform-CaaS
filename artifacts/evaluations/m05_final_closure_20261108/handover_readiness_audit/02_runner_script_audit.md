# Milestone 05 External Execution — Runner Script Implementation Audit

**Project:** Multi-Tenant AI Platform / CaaS  
**Target Script:** `infrastructure/scripts/run-live-integration-tests.sh`  
**Audit Phase:** Phase 3 — Runner Implementation Audit  
**Auditor:** Senior SRE & DevSecOps Engineer  

---

## 1. Execution Flow & Architecture

The runner script (`run-live-integration-tests.sh`) orchestrates the sequential execution of the live container suites:

```text
[Preflight Checks: Tools, Docker Daemon, RAM >= 2048MB, Disk >= 2048MB]
       │
       ▼
[Stage 1: PostgreSQL 16 + pgvector]
  ├── Port 55432 Conflict Probe (/dev/tcp/127.0.0.1/55432)
  ├── docker compose -f docker-compose.m05-postgres.yml up -d
  ├── Healthcheck Polling: docker inspect --format="{{.State.Health.Status}}" (max 20 retries, 40s)
  ├── pytest 12 Node IDs (capturing JUnit XML + output log + PIPESTATUS exit code)
  ├── drill-live-postgres-backup-restore.sh (if --skip-drills is false)
  ├── docker logs m05_postgres_test > postgres_container_logs.txt
  └── docker compose -f docker-compose.m05-postgres.yml down (Zero -v flag)
       │
       ▼
[Stage 2: Qdrant v1.9.0]
  ├── Port 6333 Conflict Probe (/dev/tcp/127.0.0.1/6333)
  ├── docker compose -f docker-compose.m05-qdrant.yml up -d
  ├── Healthcheck Polling: docker inspect --format="{{.State.Health.Status}}" (max 20 retries, 40s)
  ├── pytest 5 Node IDs (capturing JUnit XML + output log + PIPESTATUS exit code)
  ├── drill-live-qdrant-rebuild.sh (if --skip-drills is false)
  ├── docker logs m05_qdrant_test > qdrant_container_logs.txt
  └── docker compose -f docker-compose.m05-qdrant.yml down (Zero -v flag)
       │
       ▼
[Aggregate Summary & Non-Zero Exit Code Propagation]
```

---

## 2. In-Depth Operational Characteristics

### 2.1 Required Commands & Dependencies
The script asserts the availability of `docker`, `docker compose` (or standalone `docker-compose`), and `python3`. It relies on standard POSIX shell tools (`awk`, `df`, `free`, `sleep`, `curl`, `tee`).

### 2.2 Target Services & Port Requirements
- **PostgreSQL 16 + pgvector:** Binds exclusively to `127.0.0.1:55432`.
- **Qdrant v1.9.0:** Binds to `127.0.0.1:6333` (REST HTTP) and `127.0.0.1:6334` (gRPC).
- **Port Conflict Check:** Uses bash `/dev/tcp/127.0.0.1/$port` socket testing before launching each container. If a port is occupied, it aborts immediately with exit code 1 to protect existing services.

### 2.3 Environment Variables & Defaults
| Variable | Default Value | Purpose |
|---|---|---|
| `M05_POSTGRES_DB` | `m05_integration` | Test database name |
| `M05_POSTGRES_USER` | `m05_test` | Database superuser for testing |
| `M05_POSTGRES_PASSWORD` | `m05_test_password_secure_local` | Safe test password |
| `M05_POSTGRES_PORT` | `55432` | Host port for PostgreSQL |
| `M05_QDRANT_PORT` | `6333` | Host port for Qdrant HTTP |

### 2.4 Resource Preflight Checks
- **Memory Safety:** Reads `/proc/meminfo` (`MemAvailable`) or `free -m` (column 7). Requires available physical memory $\ge 2,048$ MB unless `--force` is supplied.
- **Disk Safety:** Checks `df -m "$ROOT_DIR"`. Requires available free disk space $\ge 2,048$ MB unless `--force` is supplied.

### 2.5 Service Healthcheck Polling
Container startup is not treated as readiness. The script actively polls `docker inspect --format="{{.State.Health.Status}}"` every 2 seconds for up to 20 attempts (40 seconds). If the container does not report `healthy`, it dumps container failure logs, tears down the container, and exits with code 1.

### 2.6 Execution Concurrency
PostgreSQL and Qdrant suites execute **strictly sequentially**, never concurrently. This minimizes host memory footprint during testing ($\le 512$ MB for PostgreSQL, $\le 256$ MB for Qdrant).

### 2.7 Logging, JUnit XML & Exit Code Propagation
- `python -m pytest ... --junitxml="${OUTPUT_DIR}/..._junit.xml" 2>&1 | tee "${OUTPUT_DIR}/..._test_output.txt"`
- The pipeline exit code is captured via `${PIPESTATUS[0]}`. If any test node fails, `FINAL_EXIT=1`.
- Container logs are dumped to `${OUTPUT_DIR}/..._container_logs.txt` prior to container teardown.
- The script exits with `FINAL_EXIT` (0 for complete success, 1 on any failure).

### 2.8 Teardown Safety & Volume Preservation
Both teardown commands execute:  
`$DOCKER_COMPOSE -f "$POSTGRES_COMPOSE" down` and `$DOCKER_COMPOSE -f "$QDRANT_COMPOSE" down`.  
**Neither command uses the `-v` / `--volumes` flag.** Persistent or host-mounted volumes are never automatically pruned. Unrelated containers and volumes outside these compose files are completely untouched.

### 2.9 Hidden Skips & Permissive Fallback Audit
- The script defines fixed arrays of test node IDs (`PG_TEST_NODES` and `QDRANT_TEST_NODES`).
- There are no `|| true` suppressions on the test execution steps.
- **Caveat Identified:** If a test within Python code contains `@pytest.mark.skip`, Pytest exits with code 0. Therefore, automated post-run validation must parse the JUnit XML reports to verify `skipped="0"`.
