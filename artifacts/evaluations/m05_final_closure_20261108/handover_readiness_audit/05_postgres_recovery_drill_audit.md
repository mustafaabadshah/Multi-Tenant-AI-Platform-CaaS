# Milestone 05 External Execution — PostgreSQL Backup/Restore Drill Audit

**Project:** Multi-Tenant AI Platform / CaaS  
**Target Script:** `infrastructure/scripts/drill-live-postgres-backup-restore.sh`  
**Audit Phase:** Phase 6 — PostgreSQL Backup/Restore Drill Audit  
**Auditor:** Senior Database Reliability Engineer & Disaster Recovery Auditor  

---

## 1. Compliance Checklist (Section 6 Requirements)

| # | Audit Requirement | Script Implementation Detail | Audit Finding |
|---|---|---|---|
| 1 | Source DB is disposable `m05_integration` | Line 13: `SOURCE_DB="${M05_POSTGRES_DB:-m05_integration}"` | **COMPLIANT** |
| 2 | Backup uses PostgreSQL custom format (`pg_dump -Fc`) | Line 62: `docker exec ... pg_dump ... -Fc -f /tmp/drill_backup.dump` | **COMPLIANT** |
| 3 | Backup SHA-256 checksum generated | Line 66: `BACKUP_SHA=$(docker exec ... sha256sum /tmp/drill_backup.dump ...)` | **COMPLIANT** |
| 4 | Restore targets separate disposable database | Line 14, 73: `RESTORE_DB="m05_restore_drill_disposable"`; creates fresh DB | **COMPLIANT** |
| 5 | Source database is never dropped or modified | Lines 72, 98: Drop/Create targets strictly `m05_restore_drill_disposable` | **COMPLIANT** |
| 6 | Restored DB queried for expected schema/records | Line 83: Queries count of restored assistant record | **COMPLIANT** |
| 7 | Composite FK and tenant constraints verified | Line 83: `WHERE id = ... AND tenant_id = ...` enforces composite scoping | **COMPLIANT** |
| 8 | Restored assistant record queried | Line 83–84: Queries assistant ID and `byok_encrypted_key` | **COMPLIANT** |
| 9 | Restored ciphertext decrypted via `decrypt_credential` | Line 86: Compares ciphertext string equality (`$RESTORED_KEY == "$DISPOSABLE_BYOK_CIPHERTEXT"`) | **DEFECT / OMISSION** |
| 10 | Decrypted plaintext compared in memory | Omitted in shell script (evaluates ciphertext string match only) | **DEFECT / OMISSION** |
| 11 | Plaintext tokens never printed to logs | Verified: Script only echoes masked status messages; zero secrets logged | **COMPLIANT** |
| 12 | Cleanup targets only drill DB and temp dump | Lines 98–99: `DROP DATABASE m05_restore_drill_disposable` and `rm -f /tmp/drill_backup.dump` | **COMPLIANT** |

---

## 2. In-Depth Technical Finding: Missing Live Decryption Verification

### The Gap:
In `drill-live-postgres-backup-restore.sh` (lines 83–94):
```bash
RESTORED_KEY=$(docker exec "$CONTAINER_NAME" psql -U "$POSTGRES_USER" -d "$RESTORE_DB" -t -A -c "SELECT byok_encrypted_key FROM assistants WHERE id = '$DISPOSABLE_ASSISTANT_ID';")

if [[ "$RESTORED_ASSISTANT_COUNT" -eq 1 && "$RESTORED_KEY" == "$DISPOSABLE_BYOK_CIPHERTEXT" ]]; then
    echo "Data integrity verified:"
    echo "  - Encrypted BYOK key preserved byte-for-byte in restored target database."
```
The script verifies that the database restored the exact encrypted ciphertext string. However, **it does not execute a Python decryption call to decrypt the restored ciphertext using the designated Fernet key**. Ciphertext equality confirms binary storage fidelity, but does not prove end-to-end cryptographic recovery.

---

## 3. Drill Classification & Recommendation

### Classification:
**`NOT_READY`** (per Section 6 directive: *"If the drill cannot establish actual decryption and original-token equality, classify the drill as NOT READY."*)

### Recommended Operator Enhancement:
Before or during external runner execution, the operator should execute a Python verification snippet against `m05_restore_drill_disposable`:
```python
from app.core.crypto import decrypt_credential
# Assert that decrypt_credential(restored_ciphertext, test_key) == test_token
```
This guarantees complete cryptographic fidelity for unconditional release.
