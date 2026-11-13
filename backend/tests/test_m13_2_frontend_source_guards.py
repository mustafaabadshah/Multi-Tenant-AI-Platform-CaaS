"""M13.2 UX-1/OPS-4: embed origin safety and frontend source guards."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.config import settings

FRONTEND_ROOT = Path(__file__).resolve().parents[2] / "frontend"
LOGIN_PAGE = FRONTEND_ROOT / "app" / "login" / "page.tsx"
API_LIB = FRONTEND_ROOT / "lib" / "api.ts"
EMBED_PAGE = FRONTEND_ROOT / "app" / "embed" / "[publicId]" / "page.tsx"

EMBED_SCRIPT_URL = "/api/v1/public/embed.js"


# ---------------------------------------------------------------------------
# OPS-4: no demo credentials or quick-login shortcuts in the login page
# ---------------------------------------------------------------------------


def test_login_page_has_no_demo_credentials_or_quick_login():
    text = LOGIN_PAGE.read_text(encoding="utf-8")

    assert "Password123!" not in text
    assert "handleQuickFill" not in text
    assert "demoEmail" not in text
    assert "Quick demo" not in text
    assert "owner_a@companya.com" not in text
    assert "owner_b@companyb.com" not in text

    # The real login form and invite-based onboarding entry point remain.
    assert 'type="password"' in text
    assert "await login(email, password)" in text
    assert "/register" in text


def test_api_base_resolution_has_no_production_localhost_fallback():
    text = API_LIB.read_text(encoding="utf-8")

    assert "http://localhost" not in text
    assert "export const API_BASE = getApiBase();" in text
    assert "NEXT_PUBLIC_API_BASE_URL is not configured for production" in text

    production_guard = text.index('if (process.env.NODE_ENV === "production") {')
    local_fallback = text.index('return "http://127.0.0.1:8000";')
    assert production_guard < local_fallback
    assert 'return "";' in text[production_guard:local_fallback]


def test_embed_page_uses_backend_api_client_without_localhost():
    text = EMBED_PAGE.read_text(encoding="utf-8")

    assert "http://localhost" not in text
    assert "api.getPublicAssistant(publicId)" in text
    assert "api.streamPublicChat(" in text


# ---------------------------------------------------------------------------
# UX-1: embed loader targets FRONTEND_URL, never the backend script origin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embed_loader_uses_configured_frontend_origin(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(settings, "PUBLIC_PUBLISHING_ENABLED", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://chat.example.com/")

    resp = await client.get(EMBED_SCRIPT_URL)
    assert resp.status_code == 200
    body = resp.text

    assert 'var embedBase = "https://chat.example.com";' in body
    assert "embedBase + '/embed/'" in body
    assert "scriptTag.src" not in body
    assert "window.location.origin" not in body
    assert "localhost" not in body.lower()


@pytest.mark.asyncio
async def test_embed_loader_is_inert_when_publishing_disabled(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(settings, "PUBLIC_PUBLISHING_ENABLED", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://chat.example.com")

    resp = await client.get(EMBED_SCRIPT_URL)
    assert resp.status_code == 200
    body = resp.text

    assert "iframe" not in body
    assert "/embed/" not in body
    assert "mmaip-widget-container" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frontend_url", ["", "   ", "not-a-url", "ftp://chat.example.com"]
)
async def test_embed_loader_is_inert_for_missing_or_invalid_frontend_url(
    client: AsyncClient, monkeypatch, frontend_url: str
):
    monkeypatch.setattr(settings, "PUBLIC_PUBLISHING_ENABLED", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "FRONTEND_URL", frontend_url)

    resp = await client.get(EMBED_SCRIPT_URL)
    assert resp.status_code == 200
    assert "iframe" not in resp.text
    assert "/embed/" not in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frontend_url",
    [
        "http://localhost:3000",
        "http://chat.example.com",
        "https://localhost:3000",
    ],
)
async def test_embed_loader_requires_https_and_rejects_localhost_outside_dev(
    client: AsyncClient, monkeypatch, frontend_url: str
):
    monkeypatch.setattr(settings, "PUBLIC_PUBLISHING_ENABLED", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "FRONTEND_URL", frontend_url)

    resp = await client.get(EMBED_SCRIPT_URL)
    assert resp.status_code == 200
    assert "iframe" not in resp.text
    assert "/embed/" not in resp.text
    assert "localhost" not in resp.text.lower()


@pytest.mark.asyncio
async def test_embed_loader_accepts_https_frontend_origin_in_production(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(settings, "PUBLIC_PUBLISHING_ENABLED", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://chat.example.com")

    resp = await client.get(EMBED_SCRIPT_URL)
    assert resp.status_code == 200
    assert 'var embedBase = "https://chat.example.com";' in resp.text
    assert "scriptTag.src" not in resp.text
