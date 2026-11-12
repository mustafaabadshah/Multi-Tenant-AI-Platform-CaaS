"""M11 Part 1 remediation: invitation-based onboarding without open registration."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.invitation import Invitation

INVALID_DETAIL = "Invalid or expired invitation"


async def _invite(client: AsyncClient, seed_data: dict, email: str, role: str = "employee"):
    return await client.post(
        "/api/v1/members/invite",
        headers={
            "Authorization": f"Bearer {seed_data['token_a_owner']}",
            "X-Tenant-ID": str(seed_data["tenant_a"].id),
        },
        json={"email": email, "role": role},
    )


async def _accept(client: AsyncClient, token: str, password: str = "NewPassword123!"):
    return await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": token, "password": password},
    )


async def _get_invitation(db_session: AsyncSession, email: str) -> Invitation | None:
    stmt = (
        select(Invitation)
        .where(Invitation.email == email)
        .order_by(Invitation.created_at.desc())
    )
    return (await db_session.execute(stmt)).scalars().first()


@pytest.mark.asyncio
async def test_invite_new_user_issues_token_and_accept_enables_login(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    email = "newhire@companya.com"
    invite_resp = await _invite(client, seed_data, email)
    assert invite_resp.status_code == 201, invite_resp.text
    body = invite_resp.json()
    raw_token = body["invitation_token"]
    assert raw_token
    assert body["invitation_expires_at"]

    invitation = await _get_invitation(db_session, email)
    assert invitation is not None
    assert invitation.token == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert invitation.token != raw_token
    assert invitation.accepted_at is None
    assert invitation.tenant_id == seed_data["tenant_a"].id

    accept_resp = await _accept(client, raw_token)
    assert accept_resp.status_code == 200, accept_resp.text
    assert "access_token" in accept_resp.json()

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "NewPassword123!"},
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_resp.json()['access_token']}"},
    )
    assert me_resp.status_code == 200
    workspaces = me_resp.json()["workspaces"]
    assert len(workspaces) == 1
    assert workspaces[0]["tenant_id"] == str(seed_data["tenant_a"].id)
    assert workspaces[0]["role"] == "employee"


@pytest.mark.asyncio
async def test_invitation_token_is_single_use(client: AsyncClient, seed_data: dict):
    email = "singleuse@companya.com"
    invite_resp = await _invite(client, seed_data, email)
    assert invite_resp.status_code == 201
    raw_token = invite_resp.json()["invitation_token"]

    first = await _accept(client, raw_token, "FirstPassword123!")
    assert first.status_code == 200

    second = await _accept(client, raw_token, "SecondPassword123!")
    assert second.status_code == 400
    assert second.json()["detail"] == INVALID_DETAIL

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "FirstPassword123!"},
    )
    assert login_resp.status_code == 200


@pytest.mark.asyncio
async def test_expired_invitation_rejected(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    email = "expired@companya.com"
    invite_resp = await _invite(client, seed_data, email)
    assert invite_resp.status_code == 201
    raw_token = invite_resp.json()["invitation_token"]

    invitation = await _get_invitation(db_session, email)
    assert invitation is not None
    invitation.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()

    resp = await _accept(client, raw_token)
    assert resp.status_code == 400
    assert resp.json()["detail"] == INVALID_DETAIL


@pytest.mark.asyncio
async def test_garbage_token_rejected(client: AsyncClient):
    resp = await _accept(client, "not-a-real-invitation-token")
    assert resp.status_code == 400
    assert resp.json()["detail"] == INVALID_DETAIL


@pytest.mark.asyncio
async def test_invited_membership_is_tenant_scoped(client: AsyncClient, seed_data: dict):
    email = "scopedhire@companya.com"
    invite_resp = await _invite(client, seed_data, email)
    assert invite_resp.status_code == 201
    accept_resp = await _accept(client, invite_resp.json()["invitation_token"])
    assert accept_resp.status_code == 200
    access_token = accept_resp.json()["access_token"]

    cross_tenant = await client.get(
        "/api/v1/members",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Tenant-ID": str(seed_data["tenant_b"].id),
        },
    )
    assert cross_tenant.status_code == 403

    own_tenant = await client.get(
        "/api/v1/members",
        headers={
            "Authorization": f"Bearer {access_token}",
            "X-Tenant-ID": str(seed_data["tenant_a"].id),
        },
    )
    assert own_tenant.status_code == 200


@pytest.mark.asyncio
async def test_existing_user_invite_has_no_token(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    email = "emp_b@companyb.com"
    resp = await _invite(client, seed_data, email)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["invitation_token"] is None
    assert body["invitation_expires_at"] is None
    assert await _get_invitation(db_session, email) is None


@pytest.mark.asyncio
async def test_accept_invite_allowed_when_registration_disabled(
    client: AsyncClient, seed_data: dict, monkeypatch
):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_REGISTRATION", False)

    email = "closedreg@companya.com"
    invite_resp = await _invite(client, seed_data, email)
    assert invite_resp.status_code == 201
    raw_token = invite_resp.json()["invitation_token"]

    accept_resp = await _accept(client, raw_token)
    assert accept_resp.status_code == 200

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "NewPassword123!"},
    )
    assert login_resp.status_code == 200

    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "blocked@companya.com",
            "password": "Password123!",
            "full_name": "Blocked User",
        },
    )
    assert register_resp.status_code == 403
