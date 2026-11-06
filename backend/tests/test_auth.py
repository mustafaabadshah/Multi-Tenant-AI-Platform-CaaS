import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_registration_individual_workspace(client: AsyncClient):
    payload = {
        "email": "student@university.edu",
        "password": "Password123!",
        "full_name": "Sam Student",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Verify profile via /auth/me
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "student@university.edu"
    assert me_data["full_name"] == "Sam Student"
    assert len(me_data["workspaces"]) == 1
    assert me_data["workspaces"][0]["tenant_type"] == "INDIVIDUAL"
    assert me_data["workspaces"][0]["role"] == "tenant_owner"


@pytest.mark.asyncio
async def test_user_registration_organization_workspace(client: AsyncClient):
    payload = {
        "email": "admin@enterprise.com",
        "password": "Password123!",
        "full_name": "Edward Admin",
        "organization_name": "Acme Global",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert len(me_data["workspaces"]) == 1
    assert me_data["workspaces"][0]["tenant_type"] == "ORGANIZATION"
    assert me_data["workspaces"][0]["tenant_name"] == "Acme Global"


@pytest.mark.asyncio
async def test_duplicate_registration_fails(client: AsyncClient):
    payload = {
        "email": "duplicate@test.com",
        "password": "Password123!",
        "full_name": "Duplicate User",
    }
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_login_success_and_failure(client: AsyncClient):
    payload = {
        "email": "login_user@test.com",
        "password": "CorrectPassword123!",
        "full_name": "Login Tester",
    }
    await client.post("/api/v1/auth/register", json=payload)

    # Valid credentials
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_user@test.com", "password": "CorrectPassword123!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # Invalid password
    bad_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_user@test.com", "password": "WrongPassword!"},
    )
    assert bad_res.status_code == 401

    # Non-existent email
    unknown_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "Password123!"},
    )
    assert unknown_res.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_lifecycle(client: AsyncClient):
    payload = {
        "email": "refresher@test.com",
        "password": "Password123!",
        "full_name": "Refresher User",
    }
    reg = await client.post("/api/v1/auth/register", json=payload)
    refresh_tok = reg.json()["refresh_token"]

    ref_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_tok})
    assert ref_res.status_code == 200
    assert "access_token" in ref_res.json()
    assert "refresh_token" in ref_res.json()
