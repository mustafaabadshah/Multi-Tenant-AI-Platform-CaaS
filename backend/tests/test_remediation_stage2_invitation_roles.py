"""Stage 2 remediation tests — SEC-1: invitation role contract consistency.

Backend role validation is canonical (SystemRole registry). These tests lock
the contract so the frontend can only submit supported roles, and verify
escalation and tenant boundaries.
"""

import pytest
from httpx import AsyncClient

from app.core.constants import SystemRole
from app.core.security import create_access_token, hash_password
from app.repositories.member_repository import MemberRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository

CANONICAL_ASSIGNABLE_ROLES = [
    SystemRole.EMPLOYEE.value,
    SystemRole.VIEWER.value,
    SystemRole.KNOWLEDGE_EDITOR.value,
    SystemRole.ASSISTANT_MANAGER.value,
    SystemRole.DEPT_ADMIN.value,
    SystemRole.ORG_ADMIN.value,
]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_role", ["manager", "admin", "super_admin", "ROOT", "org-owner"])
async def test_invite_with_unsupported_role_values_rejected(client: AsyncClient, seed_data: dict, bad_role: str):
    resp = await client.post(
        "/api/v1/members/invite",
        headers={"Authorization": f"Bearer {seed_data['token_a_owner']}", "X-Tenant-ID": str(seed_data["tenant_a"].id)},
        json={"email": f"bad_{bad_role.replace('-', '_')}@companya.com", "role": bad_role},
    )
    assert resp.status_code == 400
    assert "does not exist" in resp.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", CANONICAL_ASSIGNABLE_ROLES)
async def test_invite_with_canonical_roles_accepted(client: AsyncClient, seed_data: dict, role: str):
    resp = await client.post(
        "/api/v1/members/invite",
        headers={"Authorization": f"Bearer {seed_data['token_a_owner']}", "X-Tenant-ID": str(seed_data["tenant_a"].id)},
        json={"email": f"invite_{role}@companya.com", "role": role},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == role
    assert body["tenant_id"] == str(seed_data["tenant_a"].id)


@pytest.mark.asyncio
async def test_invite_defaults_to_employee_role(client: AsyncClient, seed_data: dict):
    resp = await client.post(
        "/api/v1/members/invite",
        headers={"Authorization": f"Bearer {seed_data['token_a_owner']}", "X-Tenant-ID": str(seed_data["tenant_a"].id)},
        json={"email": "defaultrole@companya.com"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == SystemRole.EMPLOYEE.value


@pytest.mark.asyncio
async def test_non_owner_cannot_assign_owner_or_superadmin_via_invite(
    client: AsyncClient, seed_data: dict, db_session
):
    tenant_a = seed_data["tenant_a"]
    user_repo = UserRepository(db_session)
    role_repo = RoleRepository(db_session)
    member_repo = MemberRepository(db_session, tenant_a.id)

    org_admin_user = await user_repo.create(
        email="orgadmin@companya.com",
        hashed_password=hash_password("Password123!"),
        full_name="Ora Admin",
    )
    org_admin_role = await role_repo.get_by_name(SystemRole.ORG_ADMIN.value)
    await member_repo.create(user_id=org_admin_user.id, role_id=org_admin_role.id)
    await db_session.commit()

    token = create_access_token(
        str(org_admin_user.id),
        {"email": org_admin_user.email, "tenant_id": str(tenant_a.id)},
    )

    for privileged in (SystemRole.TENANT_OWNER.value, SystemRole.PLATFORM_SUPERADMIN.value):
        resp = await client.post(
            "/api/v1/members/invite",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": str(tenant_a.id)},
            json={"email": f"escalate_{privileged}@companya.com", "role": privileged},
        )
        assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_invite_creates_membership_only_in_inviting_tenant(client: AsyncClient, seed_data: dict):
    resp = await client.post(
        "/api/v1/members/invite",
        headers={"Authorization": f"Bearer {seed_data['token_b_owner']}", "X-Tenant-ID": str(seed_data["tenant_b"].id)},
        json={"email": "scoped@companyb.com", "role": SystemRole.EMPLOYEE.value},
    )
    assert resp.status_code == 201, resp.text
    new_member_id = resp.json()["id"]

    list_a = await client.get(
        "/api/v1/members",
        headers={"Authorization": f"Bearer {seed_data['token_a_owner']}", "X-Tenant-ID": str(seed_data["tenant_a"].id)},
    )
    assert list_a.status_code == 200
    assert all(m["id"] != new_member_id for m in list_a.json())

    list_b = await client.get(
        "/api/v1/members",
        headers={"Authorization": f"Bearer {seed_data['token_b_owner']}", "X-Tenant-ID": str(seed_data["tenant_b"].id)},
    )
    assert list_b.status_code == 200
    assert any(m["id"] == new_member_id for m in list_b.json())


@pytest.mark.asyncio
async def test_employee_cannot_invite_members(client: AsyncClient, seed_data: dict):
    resp = await client.post(
        "/api/v1/members/invite",
        headers={"Authorization": f"Bearer {seed_data['token_a_employee']}", "X-Tenant-ID": str(seed_data["tenant_a"].id)},
        json={"email": "nope@companya.com", "role": SystemRole.EMPLOYEE.value},
    )
    assert resp.status_code == 403
