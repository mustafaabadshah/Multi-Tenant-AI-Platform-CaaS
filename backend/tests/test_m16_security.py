"""M16 Security Test Suite: Durable Sessions, Token Rotation, Replay Detection, and Invitation Integrity."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MembershipStatus
from app.models.membership import TenantMembership
from app.models.session import AuthSession


@pytest.mark.asyncio
async def test_session_creation_and_rotation(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Test that login creates a durable session and refresh rotates the token."""
    # 1. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner_a@companya.com", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    access_token_1 = data["access_token"]
    refresh_token_1 = data["refresh_token"]
    assert access_token_1 and refresh_token_1

    # Verify session persisted in DB
    user_a = seed_data["user_a_owner"]
    stmt = select(AuthSession).where(AuthSession.user_id == user_a.id, AuthSession.is_revoked.is_(False))
    sessions = (await db_session.execute(stmt)).scalars().all()
    assert len(sessions) >= 1

    # 2. Refresh token (First rotation)
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_1},
    )
    assert refresh_res.status_code == 200
    refreshed_data = refresh_res.json()
    assert refreshed_data["access_token"]
    refresh_token_2 = refreshed_data["refresh_token"]
    assert refresh_token_2 != refresh_token_1


    # 3. Use new refresh token (Second rotation)
    refresh_res_2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_2},
    )
    assert refresh_res_2.status_code == 200
    refreshed_data_2 = refresh_res_2.json()
    assert refreshed_data_2["refresh_token"] != refresh_token_2


@pytest.mark.asyncio
async def test_refresh_token_replay_detection(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Test that replaying a previously rotated refresh token triggers security revocation."""
    # 1. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner_a@companya.com", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    initial_refresh = tokens["refresh_token"]

    # 2. Rotate to obtain a second refresh token
    rotate_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert rotate_res.status_code == 200
    second_refresh = rotate_res.json()["refresh_token"]
    assert second_refresh != initial_refresh

    # 3. REPLAY: Attempt to use the original (already rotated) refresh token again!
    replay_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )
    assert replay_res.status_code == 401
    assert "reuse detected" in replay_res.json()["detail"].lower()

    # 4. Verify that the newer token from that session family is NOW ALSO REVOKED
    follow_up_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second_refresh},
    )
    assert follow_up_res.status_code == 401
    assert "revoked" in follow_up_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_session_logout_and_revocation(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Test that logout revokes the server-side session."""
    # 1. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner_a@companya.com", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    data = login_res.json()
    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    # 2. Call /auth/logout with the bearer token
    logout_res = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Successfully logged out"

    # 3. Attempting to refresh using the revoked session's token fails with 401
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 401
    assert "revoked" in refresh_res.json()["detail"].lower()

    # 4. Attempting to use the revoked access token on protected endpoints fails with 401
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_res.status_code == 401
    assert "revoked" in me_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_logout_all_sessions(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Test logging out all devices/sessions at once."""
    # Create 3 logins
    refresh_tokens = []

    for _ in range(3):
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "owner_a@companya.com", "password": "Password123!"},
        )
        assert res.status_code == 200
        refresh_tokens.append(res.json()["refresh_token"])

    latest_access = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": "owner_a@companya.com", "password": "Password123!"},
        )
    ).json()["access_token"]

    # Call logout-all
    logout_all_res = await client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {latest_access}"},
    )
    assert logout_all_res.status_code == 200

    # All refresh tokens should now fail
    for rf in refresh_tokens:
        check_res = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": rf},
        )
        assert check_res.status_code == 401


@pytest.mark.asyncio
async def test_invitation_lifecycle_and_tenant_gating(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Test that invited members cannot access tenant resources until accepting their invitation."""
    tenant_a = seed_data["tenant_a"]
    token_a_owner = seed_data["token_a_owner"]

    new_email = "new_developer@companya.com"

    # 1. Invite a new member
    invite_res = await client.post(
        "/api/v1/members/invite",
        headers={"Authorization": f"Bearer {token_a_owner}", "X-Tenant-ID": str(tenant_a.id)},
        json={"email": new_email, "role": "employee", "title": "Junior Dev"},
    )
    assert invite_res.status_code == 201
    invite_data = invite_res.json()
    assert invite_data["status"] == "INVITED"
    raw_token = invite_data["invitation_token"]
    assert raw_token is not None

    # Verify membership status in DB is INVITED
    m_stmt = select(TenantMembership).where(TenantMembership.id == uuid.UUID(invite_data["id"]))
    membership = (await db_session.execute(m_stmt)).scalar_one()
    assert membership.status == MembershipStatus.INVITED.value

    # 2. List pending invitations
    invites_list_res = await client.get(
        "/api/v1/members/invitations",
        headers={"Authorization": f"Bearer {token_a_owner}", "X-Tenant-ID": str(tenant_a.id)},
    )
    assert invites_list_res.status_code == 200
    invites = invites_list_res.json()
    assert any(inv["email"] == new_email for inv in invites)

    # 3. Accept invitation
    accept_res = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": raw_token, "password": "NewSecurePassword123!"},
    )
    assert accept_res.status_code == 200
    auth_data = accept_res.json()
    new_user_token = auth_data["access_token"]
    assert new_user_token is not None

    # Verify membership status in DB is now ACTIVE
    await db_session.refresh(membership)
    assert membership.status == MembershipStatus.ACTIVE.value

    # 4. New member can now access workspace
    asst_res = await client.get(
        "/api/v1/assistants",
        headers={"Authorization": f"Bearer {new_user_token}", "X-Tenant-ID": str(tenant_a.id)},
    )
    assert asst_res.status_code == 200

    # 5. Cannot re-accept the same invitation token (single use)
    reaccept_res = await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": raw_token, "password": "AnotherPassword123!"},
    )
    assert reaccept_res.status_code == 400


@pytest.mark.asyncio
async def test_invitation_cancellation(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Test cancelling a pending invitation removes the pending membership."""
    tenant_a = seed_data["tenant_a"]
    token_a_owner = seed_data["token_a_owner"]
    email_to_cancel = "cancelled_dev@companya.com"

    # 1. Invite
    invite_res = await client.post(
        "/api/v1/members/invite",
        headers={"Authorization": f"Bearer {token_a_owner}", "X-Tenant-ID": str(tenant_a.id)},
        json={"email": email_to_cancel, "role": "employee"},
    )
    assert invite_res.status_code == 201

    # 2. Get invitation ID
    invites_res = await client.get(
        "/api/v1/members/invitations",
        headers={"Authorization": f"Bearer {token_a_owner}", "X-Tenant-ID": str(tenant_a.id)},
    )
    assert invites_res.status_code == 200
    target_invite = next(i for i in invites_res.json() if i["email"] == email_to_cancel)

    # 3. Cancel invitation
    cancel_res = await client.delete(
        f"/api/v1/members/invitations/{target_invite['id']}",
        headers={"Authorization": f"Bearer {token_a_owner}", "X-Tenant-ID": str(tenant_a.id)},
    )
    assert cancel_res.status_code == 204

    # 4. Invitation no longer appears in pending list
    fresh_list_res = await client.get(
        "/api/v1/members/invitations",
        headers={"Authorization": f"Bearer {token_a_owner}", "X-Tenant-ID": str(tenant_a.id)},
    )
    assert all(i["id"] != target_invite["id"] for i in fresh_list_res.json())


@pytest.mark.asyncio
async def test_cross_tenant_invitation_denial(client: AsyncClient, seed_data: dict):
    """Test that tenant administrators cannot view or cancel invitations belonging to other tenants."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    token_a_owner = seed_data["token_a_owner"]
    token_b_owner = seed_data["token_b_owner"]

    # 1. Tenant A creates invitation
    invite_res = await client.post(
        "/api/v1/members/invite",
        headers={"Authorization": f"Bearer {token_a_owner}", "X-Tenant-ID": str(tenant_a.id)},
        json={"email": "target_a@companya.com", "role": "employee"},
    )
    assert invite_res.status_code == 201

    invites_res = await client.get(
        "/api/v1/members/invitations",
        headers={"Authorization": f"Bearer {token_a_owner}", "X-Tenant-ID": str(tenant_a.id)},
    )
    inv_id = invites_res.json()[0]["id"]

    # 2. Tenant B admin attempts to cancel Tenant A's invitation using Tenant B's context
    cross_cancel_res = await client.delete(
        f"/api/v1/members/invitations/{inv_id}",
        headers={"Authorization": f"Bearer {token_b_owner}", "X-Tenant-ID": str(tenant_b.id)},
    )
    assert cross_cancel_res.status_code == 404
