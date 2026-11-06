import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_employee_permission_restrictions(client: AsyncClient, seed_data: dict):
    tenant_a_id = str(seed_data["tenant_a"].id)
    # Andy is an employee in Company A (does not have department.create or member.invite)
    emp_headers = {
        "Authorization": f"Bearer {seed_data['token_a_employee']}",
        "X-Tenant-ID": tenant_a_id,
    }

    # 1. Attempt to create department as employee -> Expect 403 Forbidden
    create_dept_res = await client.post(
        "/api/v1/departments",
        json={"name": "Rogue Dept"},
        headers=emp_headers,
    )
    assert create_dept_res.status_code == 403
    assert "Insufficient permissions" in create_dept_res.json()["detail"]

    # 2. Attempt to invite new member as employee -> Expect 403 Forbidden
    invite_res = await client.post(
        "/api/v1/members/invite",
        json={"email": "hacker@test.com", "role": "org_admin"},
        headers=emp_headers,
    )
    assert invite_res.status_code == 403

    # 3. Reading departments as employee -> Permitted (department.read)
    list_depts_res = await client.get("/api/v1/departments", headers=emp_headers)
    assert list_depts_res.status_code == 200
