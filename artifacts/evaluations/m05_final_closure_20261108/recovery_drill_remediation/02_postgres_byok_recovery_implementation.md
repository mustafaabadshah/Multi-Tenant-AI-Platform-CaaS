# Milestone 05 — PostgreSQL Live BYOK Recovery Implementation

**Audit Phase:** Defect A Remediation  
**Date:** 2026-11-08  
**Target Script:** `infrastructure/scripts/drill-live-postgres-backup-restore.sh`  
**Helper Module:** `backend/app/commands/drill_postgres_recovery.py`  

---

## 1. Remediation Details

### 1.1 Architecture & Safety Guards
The remediation addresses the gap where `drill-live-postgres-backup-restore.sh` previously only checked ciphertext string equality in SQL. 

The new implementation consists of:
1. **Schema Update:** Added mapped column `byok_encrypted_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)` to `Assistant` in `backend/app/models/assistant.py` and `0004_assistants_and_conversations.py`.
2. **Crypto Aliases:** Exposed canonical `encrypt_credential` and `decrypt_credential` in `backend/app/core/crypto.py`.
3. **Dedicated Python Drill Helper:** Created `backend/app/commands/drill_postgres_recovery.py` with two actions:
   - `--action seed`: Encrypts a synthetic disposable test token using `encrypt_credential` and seeds `m05_integration`.
   - `--action verify`: Connects to `m05_restore_drill_disposable`, validates schema, queries assistant, extracts restored ciphertext, invokes `decrypt_credential`, asserts in-memory equality against original token, verifies source DB `m05_integration` was unmodified, and emits required markers.

### 1.2 Mandatory Evidence Markers
The helper script outputs the following explicit markers, which the shell script verifies:
- `RESTORE_SCHEMA_PASS`: Assistant table exists and contains required columns.
- `RESTORE_RECORD_PASS`: Assistant record restored with correct tenant foreign key.
- `BYOK_DECRYPTION_PASS`: Restored ciphertext successfully decrypted via `decrypt_credential`.
- `BYOK_PLAINTEXT_MATCH_PASS`: Decrypted plaintext matches the original disposable token in memory.
- `SOURCE_DB_UNMODIFIED_PASS`: Source database `m05_integration` record count is unchanged.

### 1.3 Strict Database Protection
- `PERMITTED_SOURCE_DB = "m05_integration"`
- `PERMITTED_RESTORE_DB = "m05_restore_drill_disposable"`
- If the restore action is pointed at `m05_integration` or any non-disposable database, the script immediately aborts with exit code 1.
- No `DROP DATABASE` command is ever executed against `m05_integration`.
