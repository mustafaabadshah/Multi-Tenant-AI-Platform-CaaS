#!/usr/bin/env bash
# ==============================================================================
# MM AI Platform — Live Qdrant Application-Driven Rebuild Drill (Linux / Bash)
# Purpose: Real containerized validation of Qdrant collection recreation,
#          vector upsert, collection deletion simulation, and complete
#          rebuild driven through IngestionService.reindex_knowledge_base
#          from PostgreSQL-persisted source chunks with zero duplicate points.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

QDRANT_HOST="${M05_QDRANT_HOST:-127.0.0.1}"
QDRANT_PORT="${M05_QDRANT_PORT:-6333}"
QDRANT_CONTAINER="${M05_QDRANT_CONTAINER:-m05_qdrant_test}"

POSTGRES_CONTAINER="${M05_POSTGRES_CONTAINER:-m05_postgres_test}"
POSTGRES_PORT="${M05_POSTGRES_PORT:-55432}"
POSTGRES_DB="${M05_POSTGRES_DB:-m05_integration}"
POSTGRES_USER="${M05_POSTGRES_USER:-m05_test}"
POSTGRES_PASSWORD="${M05_POSTGRES_PASSWORD:-m05_test_password_secure_local}"
POSTGRES_COMPOSE="${ROOT_DIR}/docker-compose.m05-postgres.yml"

OUTPUT_DIR="${1:-./test_results}"
mkdir -p "$OUTPUT_DIR"

LOG_FILE="${OUTPUT_DIR}/qdrant_rebuild_drill.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================================="
echo "  Live Qdrant Application-Driven Rebuild Drill"
echo "  Qdrant Endpoint:   http://${QDRANT_HOST}:${QDRANT_PORT}"
echo "  PostgreSQL Target: 127.0.0.1:${POSTGRES_PORT}/${POSTGRES_DB}"
echo "=========================================================="

# Detect Python command
if [[ -f "${BACKEND_DIR}/.venv/bin/python" ]]; then
    PYTHON_CMD="${BACKEND_DIR}/.venv/bin/python"
elif [[ -f "${BACKEND_DIR}/.venv/bin/python3" ]]; then
    PYTHON_CMD="${BACKEND_DIR}/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# 1. Verify Qdrant connectivity
if ! curl -sf "http://${QDRANT_HOST}:${QDRANT_PORT}/readyz" >/dev/null; then
    echo "Error: Qdrant service is not ready at http://${QDRANT_HOST}:${QDRANT_PORT}." >&2
    exit 1
fi

# 2. Ensure PostgreSQL is available for application-driven reindex
STARTED_POSTGRES=false
if ! docker inspect --format="{{.State.Health.Status}}" "$POSTGRES_CONTAINER" 2>/dev/null | grep -q "healthy"; then
    echo "PostgreSQL container is not running. Starting temporary service for reindex drill..."
    docker compose -f "$POSTGRES_COMPOSE" up -d
    RETRIES=20
    while (( RETRIES > 0 )); do
        STATUS=$(docker inspect --format="{{.State.Health.Status}}" "$POSTGRES_CONTAINER" 2>/dev/null || echo "starting")
        if [[ "$STATUS" == "healthy" ]]; then
            break
        fi
        sleep 2
        RETRIES=$(( RETRIES - 1 ))
    done
    STARTED_POSTGRES=true
fi

# Cleanup trap to stop PostgreSQL if started by this drill
cleanup_drill() {
    if [[ "$STARTED_POSTGRES" == true ]]; then
        echo "Stopping temporary PostgreSQL container started for Qdrant drill..."
        docker compose -f "$POSTGRES_COMPOSE" down >/dev/null 2>&1 || true
    fi
}
trap cleanup_drill EXIT

# 3. Execute application-driven rebuild drill via Python helper
echo "Executing application-driven Qdrant rebuild helper..."
DRILL_OUTPUT=$(
    cd "$BACKEND_DIR"
    "$PYTHON_CMD" -m app.commands.drill_qdrant_rebuild \
        --pg-host "127.0.0.1" \
        --pg-port "$POSTGRES_PORT" \
        --pg-db "$POSTGRES_DB" \
        --pg-user "$POSTGRES_USER" \
        --pg-password "$POSTGRES_PASSWORD" \
        --qdrant-url "http://${QDRANT_HOST}:${QDRANT_PORT}" \
        --evidence-path "${OUTPUT_DIR}/qdrant_rebuild_evidence.json"
)
echo "$DRILL_OUTPUT"

# 4. Verify all mandatory evidence markers and telemetry states
MANDATORY_MARKERS=(
    "SOURCE_DATA_PERSISTED_PASS"
    "POSTGRES_SOURCE_RELOAD_VERIFIED"
    "INITIAL_APPLICATION_INDEX_PASS"
    "COLLECTION_LOSS_SIMULATED_PASS"
    "APPLICATION_REINDEX_ENTRYPOINT_INVOKED"
    "APPLICATION_REINDEX_CALL_STARTED"
    "APPLICATION_REINDEX_CALL_RETURNED"
    "APPLICATION_REINDEX_COMPLETED"
    "POSTGRES_SOURCE_RELOAD_PASS"
    "QDRANT_REBUILD_PASS"
    "QDRANT_REBUILD_VERIFIED"
    "TENANT_FILTER_VERIFICATION_PASS"
    "IDEMPOTENT_REINDEX_PASS"
)

for marker in "${MANDATORY_MARKERS[@]}"; do
    if ! echo "$DRILL_OUTPUT" | grep -q "$marker"; then
        echo "Error: Mandatory evidence marker '$marker' missing from rebuild drill output!" >&2
        exit 1
    fi
done

echo "=========================================================="
echo "  [PASS] Live Qdrant Application Rebuild Drill Succeeded!"
echo "=========================================================="
exit 0
