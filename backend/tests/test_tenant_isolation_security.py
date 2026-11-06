import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cross_tenant_department_access_blocked(client: AsyncClient, seed_data: dict):
    """Company A owner creates HR department.

    Company B employee attempts to access it using various attack vectors.
    """
    tenant_a_id = str(seed_data["tenant_a"].id)
    tenant_b_id = str(seed_data["tenant_b"].id)

    # 1. Alice (Company A) creates confidential HR department
    a_headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": tenant_a_id,
    }
    create_res = await client.post(
        "/api/v1/departments",
        json={"name": "HR & Payroll", "description": "Confidential compensation details"},
        headers=a_headers,
    )
    assert create_res.status_code == 201
    hr_dept_id = create_res.json()["id"]

    # Attack Vector 1: Bob (Company B) sends request with X-Tenant-ID of Company A
    # Expected: 403 Forbidden (Bob is not a member of Company A)
    spoofed_header = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": tenant_a_id,
    }
    attack_res_1 = await client.get(f"/api/v1/departments/{hr_dept_id}", headers=spoofed_header)
    assert attack_res_1.status_code == 403
    assert "Access denied" in attack_res_1.json()["detail"]

    # Attack Vector 2: Bob uses his legitimate Tenant B context,
    # but queries the guessed UUID of Company A's HR department
    # Expected: 404 Not Found (department does not exist in Tenant B context, zero metadata leaked)
    b_legit_header = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": tenant_b_id,
    }
    attack_res_2 = await client.get(f"/api/v1/departments/{hr_dept_id}", headers=b_legit_header)
    assert attack_res_2.status_code == 404
    assert "Department not found in active workspace" in attack_res_2.json()["detail"]


@pytest.mark.asyncio
async def test_cross_tenant_department_update_and_delete_blocked(
    client: AsyncClient, seed_data: dict
):
    """Company B attempts to update or delete Company A's department."""
    tenant_a_id = str(seed_data["tenant_a"].id)
    tenant_b_id = str(seed_data["tenant_b"].id)

    # Alice creates Legal department
    a_headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": tenant_a_id,
    }
    create_res = await client.post(
        "/api/v1/departments",
        json={"name": "Legal & Compliance", "description": "Corporate filings"},
        headers=a_headers,
    )
    dept_id = create_res.json()["id"]

    # Bob attempts to rename Company A Legal department
    b_headers = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": tenant_b_id,
    }
    update_res = await client.patch(
        f"/api/v1/departments/{dept_id}",
        json={"name": "Hacked Department"},
        headers=b_headers,
    )
    assert update_res.status_code == 404

    # Bob attempts to delete Company A Legal department
    del_res = await client.delete(f"/api/v1/departments/{dept_id}", headers=b_headers)
    assert del_res.status_code == 404

    # Verify Company A Legal department is untouched
    verify_res = await client.get(f"/api/v1/departments/{dept_id}", headers=a_headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["name"] == "Legal & Compliance"


@pytest.mark.asyncio
async def test_cross_tenant_employee_roster_isolation(client: AsyncClient, seed_data: dict):
    """Company B cannot see Company A's employees."""
    tenant_b_id = str(seed_data["tenant_b"].id)
    b_headers = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": tenant_b_id,
    }

    members_res = await client.get("/api/v1/members", headers=b_headers)
    assert members_res.status_code == 200
    members = members_res.json()

    # Company B member list must only contain Bob and Betty, NEVER Alice or Andy
    emails = {m["email"] for m in members}
    assert "owner_b@companyb.com" in emails
    assert "emp_b@companyb.com" in emails
    assert "owner_a@companya.com" not in emails
    assert "emp_a@companya.com" not in emails


@pytest.mark.asyncio
async def test_cross_tenant_member_role_alteration_blocked(client: AsyncClient, seed_data: dict):
    """Bob (Company B) tries to alter the role or status of Andy (Company A employee)."""
    tenant_a_id = str(seed_data["tenant_a"].id)
    tenant_b_id = str(seed_data["tenant_b"].id)

    # Fetch Andy's membership ID from Tenant A
    a_headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": tenant_a_id,
    }
    members_res = await client.get("/api/v1/members", headers=a_headers)
    andy_membership = next(m for m in members_res.json() if m["email"] == "emp_a@companya.com")
    andy_id = andy_membership["id"]

    # Bob attempts to demote or suspend Andy using Tenant B context
    b_headers = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": tenant_b_id,
    }
    attack_res = await client.patch(
        f"/api/v1/members/{andy_id}",
        json={"role": "viewer", "status": "SUSPENDED"},
        headers=b_headers,
    )
    assert attack_res.status_code == 404

    # Bob attempts to delete Andy from Company A using Tenant B context
    del_res = await client.delete(f"/api/v1/members/{andy_id}", headers=b_headers)
    assert del_res.status_code == 404

    # Verify Andy's membership in Company A is untouched
    verify_res = await client.get("/api/v1/members", headers=a_headers)
    fresh_andy = next(m for m in verify_res.json() if m["id"] == andy_id)
    assert fresh_andy["role"] == "employee"
    assert fresh_andy["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_completely_guessed_uuid_returns_404(client: AsyncClient, seed_data: dict):
    """Querying a non-existent random UUID returns 404, not revealing system internals."""
    random_uuid = str(uuid.uuid4())
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    res = await client.get(f"/api/v1/departments/{random_uuid}", headers=headers)
    assert res.status_code == 404
