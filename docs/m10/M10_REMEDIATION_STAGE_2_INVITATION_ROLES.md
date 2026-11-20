# M10 Remediation — Stage 2: SEC-1 Invitation Role Consistency

**Date:** 2026-11-11
**Finding:** SEC-1 — frontend invite dropdown submitted `manager` / `admin`, values absent from the backend canonical role registry, causing HTTP 400 on invitation.

---

## 1. Investigation

- **Canonical role enum:** `backend/app/core/constants.py` `SystemRole` — `platform_superadmin, tenant_owner, org_admin, dept_admin, assistant_manager, knowledge_editor, employee, viewer`. Seeded via `RoleRepository.seed_system_roles_and_permissions()`.
- **Invite validation:** `backend/app/api/v1/members.py` resolves `payload.role` via `role_repo.get_by_name` → unknown role = controlled 400 `Role '...' does not exist`. Owner/superadmin assignment by non-owners = 403.
- **Frontend regression:** the M10 Stage 4 rewrite replaced the original canonical dropdown (employee, org_admin, dept_admin, assistant_manager, knowledge_editor, viewer — verified at `git show HEAD`) with `employee | manager | admin`.

## 2. Remediation decision — Option A (frontend correction)

The backend role model is canonical and correct. No new roles were invented. The frontend now exposes only registry-backed roles:

| UI label | Canonical value |
|---|---|
| Employee (Standard Access) | `employee` |
| Organization Admin | `org_admin` |
| Department Admin | `dept_admin` |
| Assistant Manager | `assistant_manager` |
| Knowledge Editor | `knowledge_editor` |
| Viewer (Read Only) | `viewer` |

Owner/superadmin are deliberately excluded from the dropdown (assignment requires owner privilege and is enforced server-side).

## 3. Files changed

| File | Change |
|---|---|
| `frontend/app/dashboard/employees/page.tsx` | invite role options restored to canonical values; role badge variant mapping updated to canonical roles |

## 4. Tests added (`backend/tests/test_remediation_stage2_invitation_roles.py`, 15 tests)

| Requirement | Test(s) | Result |
|---|---|---|
| Unsupported role values → controlled validation error | `test_invite_with_unsupported_role_values_rejected` (5 values: manager, admin, super_admin, ROOT, org-owner) | 5 PASS |
| Every displayed frontend role accepted by backend | `test_invite_with_canonical_roles_accepted` (6 roles) | 6 PASS |
| Default role | `test_invite_defaults_to_employee_role` | PASS |
| No privilege escalation via invite | `test_non_owner_cannot_assign_owner_or_superadmin_via_invite` | PASS |
| Cross-tenant isolation of created memberships | `test_invite_creates_membership_only_in_inviting_tenant` | PASS |
| RBAC (employee cannot invite) | `test_employee_cannot_invite_members` | PASS |

Existing coverage referenced (not duplicated): `tests/test_m05_security_audit.py` (owner/superadmin invite 403), `tests/test_rbac_permissions.py` (employee invite 403).

**N/A documented:** invitation lifecycle endpoints (expired/revoked/already-used invitations) do not exist in the current API — `POST /members/invite` creates the membership directly (no pending-invitation state machine). No tests invented for non-existent endpoints.

## 5. Verification

```text
pytest tests/test_remediation_stage2_invitation_roles.py => 15 passed (28.27s)
```

## 6. Residual risks

None known for this finding. The dropdown label→value mapping lives in one component; a backend role-catalog change would require updating this dropdown (documented coupling).

---

```text
STAGE_2_STATUS = PASS
```
