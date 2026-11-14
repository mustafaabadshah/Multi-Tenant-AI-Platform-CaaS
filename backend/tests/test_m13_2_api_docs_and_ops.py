"""M13.2 OPS-1/OPS-2/OPS-3: docs gating, readiness safety, and proxy identity."""

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

import app.main as main_module
from app.core import rate_limit
from app.core.config import Settings, settings
from app.core.rate_limit import client_identity, enforce_rate_limit
from app.database.session import get_db
from app.main import app, create_app

READY_DETAIL = "Database service unavailable"


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def _production(enable_docs: bool | None = None) -> Settings:
    return _settings(
        ENVIRONMENT="production",
        DEBUG=False,
        FRONTEND_URL="https://app.example.com",
        ALLOWED_ORIGINS="",
        ENABLE_API_DOCS=enable_docs,
    )


def _docs_client(cfg: Settings) -> TestClient:
    return TestClient(create_app(cfg))


# ---------------------------------------------------------------------------
# OPS-3: API documentation exposure is environment-gated
# ---------------------------------------------------------------------------


def test_docs_enabled_by_default_in_development():
    client = _docs_client(_settings(ENVIRONMENT="development", ENABLE_API_DOCS=None))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200, path


def test_docs_disabled_by_default_in_staging():
    client = _docs_client(
        _settings(
            ENVIRONMENT="staging",
            FRONTEND_URL="https://staging.example.com",
            ALLOWED_ORIGINS="",
            ENABLE_API_DOCS=None,
        )
    )
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_docs_disabled_by_default_in_production():
    client = _docs_client(_production(enable_docs=None))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_explicit_enable_docs_overrides_production_default():
    client = _docs_client(_production(enable_docs=True))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 200, path


def test_explicit_disable_docs_overrides_development_default():
    client = _docs_client(
        _settings(ENVIRONMENT="development", ENABLE_API_DOCS=False)
    )
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


@pytest.mark.asyncio
async def test_authenticated_api_route_works_when_docs_disabled(db_session, seed_data):
    docs_off_app = create_app(_production(enable_docs=False))

    async def override_get_db():
        yield db_session

    docs_off_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=docs_off_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/openapi.json")).status_code == 404

        me = await client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {seed_data['token_a_owner']}",
                "X-Tenant-ID": str(seed_data["tenant_a"].id),
            },
        )
        assert me.status_code == 200, me.text
        assert me.json()["email"] == "owner_a@companya.com"


def test_docs_disablement_does_not_affect_cors():
    client = _docs_client(_production(enable_docs=False))
    resp = client.options(
        "/health",
        headers={
            "Origin": "https://app.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://app.example.com"


# ---------------------------------------------------------------------------
# OPS-2: liveness stays DB-free and readiness never leaks connection details
# ---------------------------------------------------------------------------


def test_health_does_not_query_the_database(monkeypatch):
    async def fail_if_called():
        raise AssertionError("/health must not touch the database")

    monkeypatch.setattr(main_module, "check_db_connection", fail_if_called)
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_ready_returns_generic_503_when_database_unavailable(monkeypatch):
    async def unavailable() -> bool:
        return False

    monkeypatch.setattr(main_module, "check_db_connection", unavailable)
    resp = TestClient(app).get("/ready")
    assert resp.status_code == 503
    assert resp.json() == {"detail": READY_DETAIL}
    body = resp.text
    assert settings.DATABASE_URL not in body
    for fragment in ("postgres", "postgresql", "asyncpg", "Traceback", "dsn"):
        assert fragment.lower() not in body.lower()


def test_ready_returns_200_when_database_available(monkeypatch):
    async def available() -> bool:
        return True

    monkeypatch.setattr(main_module, "check_db_connection", available)
    resp = TestClient(app).get("/ready")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ready"
    assert payload["database"] == "connected"


def test_ready_probe_errors_are_masked_as_generic_503(monkeypatch):
    async def explode():
        raise RuntimeError(f"connect failed for {settings.DATABASE_URL}")

    monkeypatch.setattr(main_module, "check_db_connection", explode)
    resp = TestClient(app).get("/ready")
    assert resp.status_code == 503
    assert resp.json() == {"detail": READY_DETAIL}
    assert settings.DATABASE_URL not in resp.text
    assert "RuntimeError" not in resp.text


# ---------------------------------------------------------------------------
# OPS-1: trusted-proxy identity resolution and stable limiter keys
# ---------------------------------------------------------------------------


def _request(peer: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": raw_headers,
            "client": (peer, 43210),
            "server": ("testserver", 80),
        }
    )


def test_trusted_proxy_uses_forwarded_client(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "10.0.0.5")
    request = _request("10.0.0.5", {"X-Forwarded-For": "203.0.113.9"})
    assert client_identity(request) == "203.0.113.9"


def test_untrusted_peer_ignores_spoofed_forwarded_header(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "10.0.0.5")
    request = _request("198.51.100.7", {"X-Forwarded-For": "203.0.113.9"})
    assert client_identity(request) == "198.51.100.7"


def test_missing_forwarded_header_falls_back_to_peer(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "10.0.0.5")
    request = _request("10.0.0.5")
    assert client_identity(request) == "10.0.0.5"


def test_multiple_forwarded_hops_use_the_first(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "10.0.0.5, 10.0.0.6")
    request = _request(
        "10.0.0.6",
        {"X-Forwarded-For": "198.51.100.10, 10.0.0.5, 10.0.0.6"},
    )
    assert client_identity(request) == "198.51.100.10"


@pytest.mark.asyncio
async def test_rate_limit_keys_are_stable_and_action_scoped(monkeypatch):
    captured: list[str] = []

    async def capture(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        captured.append(key)
        return True, 0

    monkeypatch.setattr(rate_limit.limiter, "check", capture)

    await enforce_rate_limit("public_chat.message", "203.0.113.9", 10, 60)
    await enforce_rate_limit("public_chat.message", "203.0.113.9", 10, 60)
    await enforce_rate_limit("auth.login", "203.0.113.9", 10, 60)

    assert captured[0] == captured[1]
    assert captured[0] != captured[2]
    assert "203.0.113.9" not in captured[0]
    assert len(captured[0]) == 64
