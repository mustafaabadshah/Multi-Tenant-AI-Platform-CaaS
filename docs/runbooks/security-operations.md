# Security Operations & Incident Response Runbook

**Scope:** Key Rotation, BYOK Secrets, Tenant Boundary Auditing, Incident Response

---

## 1. BYOK Secret Management & Rotation

### Multi-Key Fernet Rotation Procedure
When rotating `SECRET_ENCRYPTION_KEY`:
1. Generate new Fernet key:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
2. In production environment settings:
   * Copy current `SECRET_ENCRYPTION_KEY` to `PREVIOUS_SECRET_KEYS` (comma-separated list).
   * Update `SECRET_ENCRYPTION_KEY` to the newly generated key.
3. Deploy new environment configuration.
4. Execute batch re-encryption CLI command:
   ```bash
   python -m app.commands.rotate_encryption_keys
   ```
5. Verify all credentials decrypt cleanly.
6. Remove old key from `PREVIOUS_SECRET_KEYS` after verification.

---

## 2. Tenant Isolation Incident Response

If unauthorized cross-tenant data access is suspected:
1. **Identify Actor & Tenant:** Inspect audit logs (`GET /api/v1/audit` or `SELECT * FROM audit_logs WHERE actor_id = :id`).
2. **Immediate Session Termination:** Revoke user membership or suspend tenant via `PATCH /api/v1/tenants/{id}` with `status = SUSPENDED`.
3. **Inspect Scoping Integrity:** Confirm all repository methods use explicit `tenant_id` filtering.

---

## 3. Prompt Injection Defense Monitoring

* Assistant Runtime automatically rewrites injection tokens:
  * `<KNOWLEDGE_BASE_CONTEXT>` $\rightarrow$ `[UNTRUSTED_CONTEXT_TAG]`
  * `SYSTEM:` / `DEVELOPER:` $\rightarrow$ `[UNTRUSTED_HEADER: ...]`
* Monitor logs for high occurrences of `[UNTRUSTED_HEADER]` to identify adversarial documents.
