#!/usr/bin/env bash
# ==============================================================================
# MM AI Platform — Portable Live Infrastructure Integration Runner (Linux / Bash)
# Target Services: PostgreSQL 16 + pgvector, Qdrant v1.9.0
# Reference: M05 BLK-01 Live Infrastructure Validation & Recovery Drills
# ==============================================================================

set -euo pipefail

MODE="all"
FORCE=false
SKIP_DRILLS=false
OUTPUT_DIR=""

show_usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -m, --mode <mode>        Execution mode: postgres, qdrant, or all (default: all)
  -f, --force              Bypass available RAM and disk space checks (use in isolated CI runners)
  --skip-drills            Skip live backup/restore and Qdrant rebuild drills
  -o, --output-dir <path>  Directory to save test outputs and logs (default: ./test_results)
  -h, --help               Display this help message and exit

Environment Variables:
  M05_POSTGRES_DB          PostgreSQL test DB name (default: m05_integration)
  M05_POSTGRES_USER        PostgreSQL test username (default: m05_test)
  M05_POSTGRES_PASSWORD    PostgreSQL test password (default: m05_test_password_secure_local)
  M05_POSTGRES_PORT        Host port for PostgreSQL (default: 55432)
  M05_QDRANT_PORT          Host HTTP port for Qdrant (default: 6333)
EOF
}

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --skip-drills)
            SKIP_DRILLS=true
            shift
            ;;
        -o|--output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown argument: $1" >&2
            show_usage
            exit 1
            ;;
    esac
done

if [[ "$MODE" != "postgres" && "$MODE" != "qdrant" && "$MODE" != "all" ]]; then
    echo "Error: Invalid mode '$MODE'. Must be 'postgres', 'qdrant', or 'all'." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

if [[ -z "$OUTPUT_DIR" ]]; then
    OUTPUT_DIR="${ROOT_DIR}/test_results_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "$OUTPUT_DIR"

echo "=========================================================="
echo "  MM AI Platform — Live Infrastructure Integration Runner"
echo "  Target Mode: ${MODE}"
echo "  Output Directory: ${OUTPUT_DIR}"
echo "  Include Drills: $([[ "$SKIP_DRILLS" == false ]] && echo 'YES' || echo 'NO')"
echo "=========================================================="

# 1. Check Required Tools
echo "[1/4] Checking required commands..."
for cmd in docker python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: Required command '$cmd' is not installed or not in PATH." >&2
        exit 1
    fi
done

# Check Docker Compose (plugin or standalone)
if docker compose version &>/dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "Error: Neither 'docker compose' nor 'docker-compose' was found." >&2
    exit 1
fi
echo "Docker CLI: $(docker --version)"
echo "Compose: $($DOCKER_COMPOSE version)"
echo "Python: $(python3 --version)"

# 2. Check Docker Daemon Connectivity
echo -e "\n[2/4] Verifying Docker daemon connectivity..."
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker daemon is not running or unreachable by current user." >&2
    echo "Ensure docker service is started and current user is in 'docker' group." >&2
    exit 1
fi
echo "Docker daemon is reachable and responding."

# 3. Resource Preflight Checks (RAM & Disk)
echo -e "\n[3/4] Checking system resources..."
if [[ -f /proc/meminfo ]]; then
    AVAILABLE_KB=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
    AVAILABLE_MB=$(( AVAILABLE_KB / 1024 ))
    echo "Available Physical RAM: ${AVAILABLE_MB} MB"
    if (( AVAILABLE_MB < 2048 )) && [[ "$FORCE" != true ]]; then
        echo "Error: Available physical RAM (${AVAILABLE_MB} MB) is below the 2048 MB safety threshold." >&2
        echo "Use --force if running in an isolated, dedicated test environment." >&2
        exit 2
    fi
elif command -v free &>/dev/null; then
    AVAILABLE_MB=$(free -m | awk '/^Mem:/ {print $7}')
    echo "Available Physical RAM: ${AVAILABLE_MB} MB"
    if (( AVAILABLE_MB < 2048 )) && [[ "$FORCE" != true ]]; then
        echo "Error: Available physical RAM (${AVAILABLE_MB} MB) is below the 2048 MB safety threshold." >&2
        exit 2
    fi
fi

# Disk space check (require at least 2 GB)
DISK_FREE_MB=$(df -m "$ROOT_DIR" | awk 'NR==2 {print $4}')
echo "Available Disk Space: ${DISK_FREE_MB} MB"
if (( DISK_FREE_MB < 2048 )) && [[ "$FORCE" != true ]]; then
    echo "Error: Available disk space (${DISK_FREE_MB} MB) is below 2048 MB." >&2
    exit 2
fi

# Port occupation check helper
check_port() {
    local port="$1"
    local name="$2"
    if (echo > /dev/tcp/127.0.0.1/"$port") 2>/dev/null; then
        echo "Error: Port $port ($name) is already occupied by another process." >&2
        echo "Please terminate conflicting processes before starting integration tests." >&2
        exit 1
    fi
}

# Python virtual environment resolution
if [[ -f "${BACKEND_DIR}/.venv/bin/python" ]]; then
    PYTHON_CMD="${BACKEND_DIR}/.venv/bin/python"
elif [[ -f "${BACKEND_DIR}/.venv/bin/python3" ]]; then
    PYTHON_CMD="${BACKEND_DIR}/.venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

POSTGRES_COMPOSE="${ROOT_DIR}/docker-compose.m05-postgres.yml"
QDRANT_COMPOSE="${ROOT_DIR}/docker-compose.m05-qdrant.yml"

POSTGRES_PASSED=false
POSTGRES_DRILL_PASSED=false
QDRANT_PASSED=false
QDRANT_DRILL_PASSED=false
FINAL_EXIT=0

# ==============================================================================
# Stage: PostgreSQL 16 + pgvector Live Integration Tests & Drill
# ==============================================================================
if [[ "$MODE" == "postgres" || "$MODE" == "all" ]]; then
    echo -e "\n=========================================================="
    echo " [STAGE 1] PostgreSQL 16 + pgvector Live Integration"
    echo "=========================================================="
    
    check_port "${M05_POSTGRES_PORT:-55432}" "PostgreSQL 16"

    echo "Starting PostgreSQL container via ${POSTGRES_COMPOSE}..."
    $DOCKER_COMPOSE -f "$POSTGRES_COMPOSE" up -d

    echo "Waiting for PostgreSQL service healthcheck..."
    RETRIES=20
    HEALTHY=false
    while (( RETRIES > 0 )); do
        STATUS=$(docker inspect --format="{{.State.Health.Status}}" m05_postgres_test 2>/dev/null || echo "starting")
        if [[ "$STATUS" == "healthy" ]]; then
            HEALTHY=true
            break
        fi
        sleep 2
        RETRIES=$(( RETRIES - 1 ))
    done

    if [[ "$HEALTHY" != true ]]; then
        echo "Error: PostgreSQL container failed to report healthy status within timeout." >&2
        docker logs m05_postgres_test > "${OUTPUT_DIR}/postgres_container_failure.log" 2>&1 || true
        $DOCKER_COMPOSE -f "$POSTGRES_COMPOSE" down
        exit 1
    fi
    echo "PostgreSQL container is healthy and ready for queries."

    echo "Executing 12 PostgreSQL/pgvector integration test nodes..."
    PG_TEST_NODES=(
        "tests/integration/test_postgres_connection.py::test_postgres_version_is_16"
        "tests/integration/test_postgres_connection.py::test_pgvector_extension_loaded_and_functional"
        "tests/integration/test_postgres_connection.py::test_transaction_rollback_and_commit_behavior"
        "tests/integration/test_postgres_migrations.py::test_migration_head_and_schema_tables"
        "tests/integration/test_postgres_migrations.py::test_vector_column_data_type_in_postgresql"
        "tests/integration/test_postgres_migrations.py::test_foreign_key_and_tenant_composite_constraints"
        "tests/integration/test_postgres_fts.py::test_native_postgresql_fts_query_and_ranking"
        "tests/integration/test_postgres_fts.py::test_native_postgresql_fts_sql_injection_safety"
        "tests/integration/test_pgvector_operations.py::test_real_pgvector_insert_and_cosine_distance_ranking"
        "tests/integration/test_pgvector_operations.py::test_pgvector_rejects_dimension_mismatch"
        "tests/integration/test_postgres_tenant_isolation.py::test_cross_tenant_isolation_on_real_postgresql"
        "tests/integration/test_postgres_tenant_isolation.py::test_department_isolation_on_real_postgresql"
    )

    (
        cd "$BACKEND_DIR"
        "$PYTHON_CMD" -m pytest "${PG_TEST_NODES[@]}" -v \
            --junitxml="${OUTPUT_DIR}/postgres_test_junit.xml" \
            2>&1 | tee "${OUTPUT_DIR}/postgres_test_output.txt"
    )
    PG_EXIT=${PIPESTATUS[0]}

    if (( PG_EXIT == 0 )); then
        POSTGRES_PASSED=true
        echo "PostgreSQL live integration tests: PASSED"
    else
        echo "PostgreSQL live integration tests: FAILED (Exit Code: $PG_EXIT)" >&2
        FINAL_EXIT=1
    fi

    # Execute Live PostgreSQL Backup & Isolated Restore Drill
    if [[ "$SKIP_DRILLS" == false && -f "${SCRIPT_DIR}/drill-live-postgres-backup-restore.sh" ]]; then
        echo -e "\nExecuting live PostgreSQL backup and isolated restore drill..."
        if bash "${SCRIPT_DIR}/drill-live-postgres-backup-restore.sh" "$OUTPUT_DIR"; then
            POSTGRES_DRILL_PASSED=true
            echo "PostgreSQL backup/restore drill: PASSED"
        else
            echo "PostgreSQL backup/restore drill: FAILED" >&2
            FINAL_EXIT=1
        fi
    fi

    # Capture container logs before stopping
    docker logs m05_postgres_test > "${OUTPUT_DIR}/postgres_container_logs.txt" 2>&1 || true

    echo "Stopping PostgreSQL test container..."
    $DOCKER_COMPOSE -f "$POSTGRES_COMPOSE" down
fi

# ==============================================================================
# Stage: Qdrant Live Integration Tests & Drill
# ==============================================================================
if [[ "$MODE" == "qdrant" || "$MODE" == "all" ]]; then
    echo -e "\n=========================================================="
    echo " [STAGE 2] Qdrant v1.9.0 Live Integration"
    echo "=========================================================="
    
    check_port "${M05_QDRANT_PORT:-6333}" "Qdrant HTTP"

    echo "Starting Qdrant container via ${QDRANT_COMPOSE}..."
    $DOCKER_COMPOSE -f "$QDRANT_COMPOSE" up -d

    echo "Waiting for Qdrant service healthcheck..."
    RETRIES=20
    HEALTHY=false
    while (( RETRIES > 0 )); do
        STATUS=$(docker inspect --format="{{.State.Health.Status}}" m05_qdrant_test 2>/dev/null || echo "starting")
        if [[ "$STATUS" == "healthy" ]]; then
            HEALTHY=true
            break
        fi
        sleep 2
        RETRIES=$(( RETRIES - 1 ))
    done

    if [[ "$HEALTHY" != true ]]; then
        echo "Error: Qdrant container failed to report healthy status within timeout." >&2
        docker logs m05_qdrant_test > "${OUTPUT_DIR}/qdrant_container_failure.log" 2>&1 || true
        $DOCKER_COMPOSE -f "$QDRANT_COMPOSE" down
        exit 1
    fi
    echo "Qdrant container is healthy and ready for queries."

    echo "Executing 5 Qdrant integration test nodes..."
    QDRANT_TEST_NODES=(
        "tests/integration/test_qdrant_live_integration.py::test_qdrant_service_connectivity_and_health"
        "tests/integration/test_qdrant_live_integration.py::test_qdrant_collection_creation_and_dimension_isolation"
        "tests/integration/test_qdrant_live_integration.py::test_qdrant_upsert_and_filtered_search"
        "tests/integration/test_qdrant_live_integration.py::test_qdrant_cross_tenant_payload_isolation"
        "tests/integration/test_qdrant_live_integration.py::test_qdrant_scoped_deletion"
    )

    (
        cd "$BACKEND_DIR"
        "$PYTHON_CMD" -m pytest "${QDRANT_TEST_NODES[@]}" -v \
            --junitxml="${OUTPUT_DIR}/qdrant_test_junit.xml" \
            2>&1 | tee "${OUTPUT_DIR}/qdrant_test_output.txt"
    )
    QDRANT_EXIT=${PIPESTATUS[0]}

    if (( QDRANT_EXIT == 0 )); then
        QDRANT_PASSED=true
        echo "Qdrant live integration tests: PASSED"
    else
        echo "Qdrant live integration tests: FAILED (Exit Code: $QDRANT_EXIT)" >&2
        FINAL_EXIT=1
    fi

    # Execute Live Qdrant Rebuild Drill
    if [[ "$SKIP_DRILLS" == false && -f "${SCRIPT_DIR}/drill-live-qdrant-rebuild.sh" ]]; then
        echo -e "\nExecuting live Qdrant rebuild and payload recovery drill..."
        if bash "${SCRIPT_DIR}/drill-live-qdrant-rebuild.sh" "$OUTPUT_DIR"; then
            QDRANT_DRILL_PASSED=true
            echo "Qdrant rebuild drill: PASSED"
        else
            echo "Qdrant rebuild drill: FAILED" >&2
            FINAL_EXIT=1
        fi
    fi

    # Capture container logs before stopping
    docker logs m05_qdrant_test > "${OUTPUT_DIR}/qdrant_container_logs.txt" 2>&1 || true

    echo "Stopping Qdrant test container..."
    $DOCKER_COMPOSE -f "$QDRANT_COMPOSE" down
fi

# ==============================================================================
# Summary Report
# ==============================================================================
echo -e "\n=========================================================="
echo "  MM AI Platform — Live Test Execution Summary"
echo "=========================================================="
echo "Mode: $MODE"
if [[ "$MODE" == "postgres" || "$MODE" == "all" ]]; then
    echo "PostgreSQL Tests:        $([[ "$POSTGRES_PASSED" == true ]] && echo 'PASSED' || echo 'FAILED')"
    if [[ "$SKIP_DRILLS" == false ]]; then
        echo "PostgreSQL Backup Drill: $([[ "$POSTGRES_DRILL_PASSED" == true ]] && echo 'PASSED' || echo 'FAILED')"
    fi
fi
if [[ "$MODE" == "qdrant" || "$MODE" == "all" ]]; then
    echo "Qdrant Tests:            $([[ "$QDRANT_PASSED" == true ]] && echo 'PASSED' || echo 'FAILED')"
    if [[ "$SKIP_DRILLS" == false ]]; then
        echo "Qdrant Rebuild Drill:    $([[ "$QDRANT_DRILL_PASSED" == true ]] && echo 'PASSED' || echo 'FAILED')"
    fi
fi
echo "Artifacts saved to: ${OUTPUT_DIR}"
echo "=========================================================="

exit "$FINAL_EXIT"
