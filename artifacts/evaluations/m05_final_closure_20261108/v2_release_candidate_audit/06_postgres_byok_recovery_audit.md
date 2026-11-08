# Critical Audit D — PostgreSQL BYOK Restore Implementation

## 1. Audit Scope & Verification

Inspected:
- `backend/app/core/crypto.py`
- `backend/app/commands/drill_postgres_recovery.py`
- `infrastructure/scripts/drill-live-postgres-backup-restore.sh`
- Assistant model and migrations.

## 2. Security Boundaries & In-Memory Decryption Verification

| Check | Requirement | Audit Evidence | Result |
|---|---|---|---|
| **1. Canonical Aliases** | `encrypt_credential` & `decrypt_credential` must be real canonical wrappers | Directly aliased to `encrypt_secret` and `decrypt_secret` in `crypto.py` | **PASS** |
| **2. Exception Preservation** | Preserve existing behavior and exceptions | Uses standard Fernet/MultiFernet with logging and clean `None` returns | **PASS** |
| **3. Synthetic Token** | Disposable token must be synthetic | Value: `sk-antigravity-m05-disposable-token-20261108` | **PASS** |
| **4. Zero Secrets in Logs** | Token never printed or logged | Test `test_postgres_drill_no_secrets_in_logs` passed | **PASS** |
| **5. Context Permissions** | Context file uses restrictive permissions | Sets `0o600` on context file creation | **PASS** |
| **6. Non-Destructive Source** | Source DB is never restore target | `PERMITTED_SOURCE_DB = 'm05_integration'`; target is separate | **PASS** |
| **7. Restore Target Guard** | Target is exactly `m05_restore_drill_disposable` | Enforced by `PERMITTED_RESTORE_DB` guard | **PASS** |
| **8. Pre-Execution DB Guards** | DB-name guards execute before actions | Checks execute before engine or connection initialization | **PASS** |
| **9. Restored Ciphertext** | Ciphertext read from restored DB | Query: `SELECT byok_encrypted_key FROM assistants WHERE id = :aid AND tenant_id = :tid` | **PASS** |
| **10. Real Crypto Decryption** | Decrypt using actual application crypto | Uses `decrypt_credential(restored_ciphertext)` | **PASS** |
| **11. In-Memory Comparison** | Plaintext comparison in memory | Compared directly in Python memory; never written to disk | **PASS** |
| **12. Failure Testing** | Tampered ciphertext, wrong keys fail | Unit tests `test_postgres_drill_wrong_key_fails_safely` & `test_postgres_drill_tampered_ciphertext_fails_safely` pass | **PASS** |
| **13. Scoped Cleanup** | Cleanup removes only drill resources | Restored database dropped via guarded cleanup | **PASS** |
| **14. Source Integrity** | Source record counts unchanged | Step 5 asserts `src_count == 1` and `SOURCE_DB_UNMODIFIED_PASS` | **PASS** |

## 3. Forward Migration Integration

The restored database schema adheres to forward migration `0005_add_assistant_byok_encrypted_key.py`. Restored assistant records have valid column structure and composite tenant isolation.
