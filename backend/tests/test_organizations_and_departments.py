import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_department_crud_in_organization(client: AsyncClient, seed_data: dict):
    tenant_a_id = str(seed_data["tenant_a"].id)
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": tenant_a_id,
    }

    # 1. Create Engineering department
    create_res = await client.post(
        "/api/v1/departments",
        json={"name": "Engineering", "description": "Core product team"},
        headers=headers,
    )
    assert create_res.status_code == 201
    eng_dept = create_res.json()
    assert eng_dept["name"] == "Engineering"
    dept_id = eng_dept["id"]

    # 2. Prevent duplicate name in same tenant
    dup_res = await client.post(
        "/api/v1/departments",
        json={"name": "Engineering"},
        headers=headers,
    )
    assert dup_res.status_code == 409

    # 3. List departments
    list_res = await client.get("/api/v1/departments", headers=headers)
    assert list_res.status_code == 200
    depts = list_res.json()
    assert len(depts) == 1
    assert depts[0]["name"] == "Engineering"

    # 4. Update department
    patch_res = await client.patch(
        f"/api/v1/departments/{dept_id}",
        json={"description": "Platform & Infrastructure"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["description"] == "Platform & Infrastructure"

    # 5. Delete department
    del_res = await client.delete(f"/api/v1/departments/{dept_id}", headers=headers)
    assert del_res.status_code == 204

    # 6. Verify gone
    get_res = await client.get(f"/api/v1/departments/{dept_id}", headers=headers)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_employee_groups(client: AsyncClient, seed_data: dict):
    tenant_a_id = str(seed_data["tenant_a"].id)
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": tenant_a_id,
    }

    create_res = await client.post(
        "/api/v1/groups",
        json={"name": "Frontend Guild", "description": "UI engineers across org"},
        headers=headers,
    )
    assert create_res.status_code == 201
    group_id = create_res.json()["id"]

    list_res = await client.get("/api/v1/groups", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    del_res = await client.delete(f"/api/v1/groups/{group_id}", headers=headers)
    assert del_res.status_code == 204
