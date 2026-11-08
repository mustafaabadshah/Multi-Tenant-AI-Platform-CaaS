#!/usr/bin/env bash
# ==============================================================================
# MM AI Platform — Live PostgreSQL Backup & Isolated Restore Drill (Linux / Bash)
# Purpose: Real containerized validation of pg_dump, sha256 manifest,
#          restoration into an isolated disposable target DB, verification
#          of schema, records, relational constraints, in-memory live BYOK
#          decryption, and verification that source DB remains untouched.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"

CONTAINER_NAME="${M05_POSTGRES_CONTAINER:-m05_postgres_test}"
POSTGRES_USER="${M05_POSTGRES_USER:-m05_test}"
POSTGRES_PASSWORD="${M05_POSTGRES_PASSWORD:-m05_test_password_secure_local}"
POSTGRES_PORT="${M05_POSTGRES_PORT:-55432}"
SOURCE_DB="${M05_POSTGRES_DB:-m05_integration}"
RESTORE_DB="m05_restore_drill_disposable"
OUTPUT_DIR="${1:-./test_results}"
mkdir -p "$OUTPUT_DIR"

LOG_FILE="${OUTPUT_DIR}/postgres_backup_restore_drill.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================================="
echo "  Live PostgreSQL Backup & Restore Drill (Isolated Target)"
echo "  Container:         ${CONTAINER_NAME}"
echo "  Source DB:         ${SOURCE_DB}"
echo "  Restore Target DB: ${RESTORE_DB}"
echo "=========================================================="

# Safety Guards: Source and target must be distinct and restore DB must match expected disposable name
if [[ "$RESTORE_DB" == "$SOURCE_DB" ]]; then
    echo "SECURITY ERROR: Restore DB cannot equal Source DB!" >&2
    exit 1
fi

if [[ "$RESTORE_DB" != "m05_restore_drill_disposable" ]]; then
    echo "SECURITY ERROR: Restore DB must be 'm05_restore_drill_disposable'!" >&2
    exit 1
fi

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

# 1. Verify container is healthy
if ! docker inspect --format="{{.State.Health.Status}}" "$CONTAINER_NAME" 2>/dev/null | grep -q "healthy"; then
    echo "Error: Container $CONTAINER_NAME is not healthy." >&2
    exit 1
fi

CONTEXT_FILE="${OUTPUT_DIR}/drill_postgres_context.json"

echo "[Step 1/6] Seeding source DB with encrypted BYOK credential using application crypto..."
(
    cd "$BACKEND_DIR"
    "$PYTHON_CMD" -m app.commands.drill_postgres_recovery \
        --action seed \
        --db-name "$SOURCE_DB" \
        --host "127.0.0.1" \
        --port "$POSTGRES_PORT" \
        --user "$POSTGRES_USER" \
        --password "$POSTGRES_PASSWORD" \
        --context-file "$CONTEXT_FILE"
)

# 2. Perform custom format pg_dump
echo "[Step 2/6] Generating custom-format (-Fc) pg_dump inside container..."
docker exec "$CONTAINER_NAME" pg_dump -U "$POSTGRES_USER" -d "$SOURCE_DB" -Fc -f /tmp/drill_backup.dump

# 3. Verify SHA-256 inside container and copy manifest
echo "[Step 3/6] Computing SHA-256 hash manifest..."
BACKUP_SHA=$(docker exec "$CONTAINER_NAME" sha256sum /tmp/drill_backup.dump | awk '{print $1}')
echo "Backup Archive SHA-256: ${BACKUP_SHA}"
echo "${BACKUP_SHA}  /tmp/drill_backup.dump" > "${OUTPUT_DIR}/drill_backup_sha256.txt"

# 4. Prepare separate clean restore database with strict database name assertion
echo "[Step 4/6] Creating isolated restore target database '${RESTORE_DB}'..."
if [[ "$RESTORE_DB" != "m05_restore_drill_disposable" ]]; then
    echo "SECURITY ABORT: Refusing to create unexpected database name." >&2
    exit 1
fi
docker exec "$CONTAINER_NAME" psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS ${RESTORE_DB};"
docker exec "$CONTAINER_NAME" psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE ${RESTORE_DB};"

# 5. Restore dump into isolated database
echo "[Step 5/6] Restoring dump into isolated database '${RESTORE_DB}'..."
docker exec "$CONTAINER_NAME" pg_restore -U "$POSTGRES_USER" -d "$RESTORE_DB" --no-owner --role="$POSTGRES_USER" /tmp/drill_backup.dump || {
    echo "Notice: pg_restore completed with non-fatal schema warnings (standard for pre-existing extensions)."
}

# 6. Verify restored database schema, relationships, and in-memory live BYOK decryption
echo "[Step 6/6] Verifying schema, data fidelity, and live BYOK decryption in '${RESTORE_DB}'..."
VERIFY_OUTPUT=$(
    cd "$BACKEND_DIR"
    "$PYTHON_CMD" -m app.commands.drill_postgres_recovery \
        --action verify \
        --db-name "$RESTORE_DB" \
        --host "127.0.0.1" \
        --port "$POSTGRES_PORT" \
        --user "$POSTGRES_USER" \
        --password "$POSTGRES_PASSWORD" \
        --context-file "$CONTEXT_FILE"
)
echo "$VERIFY_OUTPUT"

# Assert mandatory evidence markers
for marker in "RESTORE_SCHEMA_PASS" "RESTORE_RECORD_PASS" "BYOK_DECRYPTION_PASS" "BYOK_PLAINTEXT_MATCH_PASS" "SOURCE_DB_UNMODIFIED_PASS"; do
    if ! echo "$VERIFY_OUTPUT" | grep -q "$marker"; then
        echo "Error: Mandatory evidence marker '$marker' missing from verification output!" >&2
        exit 1
    fi
done

# Cleanup drill artifacts safely
echo "Cleaning up disposable drill resources..."
if [[ "$RESTORE_DB" == "m05_restore_drill_disposable" ]]; then
    docker exec "$CONTAINER_NAME" psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE ${RESTORE_DB};"
fi
docker exec "$CONTAINER_NAME" rm -f /tmp/drill_backup.dump
rm -f "$CONTEXT_FILE"

echo "=========================================================="
echo "  [PASS] Live PostgreSQL Backup & Restore Drill Succeeded!"
echo "=========================================================="
exit 0
