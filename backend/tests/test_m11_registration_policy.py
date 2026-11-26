"""M11 Part 1 remediation: secure-by-default public registration policy."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import registration_allowed, settings
from app.repositories.user_repository import UserRepository

DISABLED_DETAIL = (
    "Public registration is disabled. Ask your workspace administrator for an invitation."
)


def _payload(email: str) -> dict[str, str]:
    return {
        "email": email,
        "password": "Password123!",
        "full_name": "Registration Tester",
    }


def _configure(monkeypatch, environment: str, allow: bool | None) -> None:
    monkeypatch.setattr(settings, "ENVIRONMENT", environment)
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_REGISTRATION", allow)


@pytest.mark.asyncio
async def test_development_default_allows_registration(client: AsyncClient, monkeypatch):
    """With no explicit policy, development permits open registration."""
    _configure(monkeypatch, "development", None)
    assert registration_allowed(settings) is True

    resp = await client.post("/api/v1/auth/register", json=_payload("dev_default@example.com"))
    assert resp.status_code == 201
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_production_default_denies_registration(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
):
    """With no explicit policy, production denies open registration."""
    _configure(monkeypatch, "production", None)
    assert registration_allowed(settings) is False

    resp = await client.post("/api/v1/auth/register", json=_payload("prod_default@example.com"))
    assert resp.status_code == 403
    assert resp.json()["detail"] == DISABLED_DETAIL
    assert "traceback" not in resp.text.lower()
    assert await UserRepository(db_session).get_by_email("prod_default@example.com") is None


@pytest.mark.asyncio
async def test_explicit_true_allows_production_registration(client: AsyncClient, monkeypatch):
    """An explicit opt-in enables registration even in production."""
    _configure(monkeypatch, "production", True)
    assert registration_allowed(settings) is True

    resp = await client.post("/api/v1/auth/register", json=_payload("prod_override@example.com"))
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_explicit_false_denies_development_registration(client: AsyncClient, monkeypatch):
    """An explicit opt-out disables registration even in development."""
    _configure(monkeypatch, "development", False)
    assert registration_allowed(settings) is False

    resp = await client.post("/api/v1/auth/register", json=_payload("dev_override@example.com"))
    assert resp.status_code == 403
    assert resp.json()["detail"] == DISABLED_DETAIL


@pytest.mark.asyncio
async def test_existing_user_login_works_when_registration_disabled(
    client: AsyncClient, seed_data: dict, monkeypatch
):
    """Disabling registration must not affect login for existing users."""
    _configure(monkeypatch, "production", False)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner_a@companya.com", "password": "Password123!"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
