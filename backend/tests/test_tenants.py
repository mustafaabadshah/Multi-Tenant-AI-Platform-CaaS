import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_and_create_tenants(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['token_a_owner']}"}

    # List tenants for Alice
    res = await client.get("/api/v1/tenants", headers=headers)
    assert res.status_code == 200
    workspaces = res.json()
    assert len(workspaces) == 1
    assert workspaces[0]["tenant_name"] == "Company A"

    # Alice creates a secondary research workspace
    create_payload = {
        "name": "Alice Research Lab",
        "type": "INDIVIDUAL",
    }
    create_res = await client.post("/api/v1/tenants", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    lab = create_res.json()
    assert lab["name"] == "Alice Research Lab"

    # Alice now has 2 workspaces
    list_res = await client.get("/api/v1/tenants", headers=headers)
    assert len(list_res.json()) == 2


@pytest.mark.asyncio
async def test_workspace_switch(client: AsyncClient, seed_data: dict):
    headers = {"Authorization": f"Bearer {seed_data['token_a_owner']}"}

    # Create secondary workspace
    create_res = await client.post(
        "/api/v1/tenants",
        json={"name": "Alice Second Org", "type": "ORGANIZATION"},
        headers=headers,
    )
    second_tenant_id = create_res.json()["id"]

    # Switch workspace
    switch_res = await client.post(
        f"/api/v1/tenants/{second_tenant_id}/switch",
        headers=headers,
    )
    assert switch_res.status_code == 200
    new_token = switch_res.json()["access_token"]
    assert new_token is not None
