# M20.5 — Live Authentication, Session & Multi-Tenant Regression Report

| Test ID | Boundary / Scenario | Target URL | Expected Behavior | Live Result | Status |
|---|---|---|---|---|---|
| **AUTH-01** | Operator Login | `/api/v1/auth/login` | Return access token, refresh token, session | 200 OK, Access (500 chars), Refresh (43 chars) | **PASS** |
| **AUTH-02** | Current User Profile | `/api/v1/auth/me` | Return user profile & authorized tenants | 200 OK, Identity confirmed | **PASS** |
| **AUTH-03** | Refresh Token Rotation | `/api/v1/auth/refresh` | Issue new access token + rotated refresh token | 200 OK, new refresh token issued | **PASS** |
| **AUTH-04** | Token Reuse Detection | `/api/v1/auth/refresh` | Immediate 401 & session revocation on replaying old token | 401 Unauthorized, token family revoked | **PASS** |
| **AUTH-05** | Post-Revocation Invalidation | `/api/v1/auth/me` | Revoked token rejected | 401 Unauthorized, immediate lockout | **PASS** |
| **TENANT-01** | Tenant Scoping | `/api/v1/assistants` | Return only active tenant's assistants | 200 OK, 1 assistant returned strictly scoped | **PASS** |
| **TENANT-02** | Tenant Header Enforcement | `/api/v1/tools` | Reject access when cross-tenant ID supplied | 403 Forbidden / tenant isolation enforced | **PASS** |

---

## 1. Refresh Token Rotation & Replay Protection Evidence

- Presenting an active refresh token generates a newly minted token pair (`access_token`, `refresh_token`).
- Immediately presenting the superseded refresh token triggers automated token family invalidation via `auth_sessions`:
  ```text
  M16 Refresh Rotation: status=200, rotated_token_received=True
  M16 Token Reuse Rejection: status=401 (Correctly rejected replayed token and revoked family)
  ```
- Sub-millisecond revocation prevents stolen token re-use.

## 2. Multi-Tenant Isolation Evidence

- All repository operations verify `WHERE tenant_id = :active_tenant_id`.
- Foreign keys and composite constraints on `auth_sessions`, `tools`, `mcp_connections`, and `assistants` strictly preserve tenant partitioning.
