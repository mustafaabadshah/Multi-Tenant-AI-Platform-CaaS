"""Stage 1 remediation tests — D11: development-only CORS configuration.

Verifies the centralized CORS policy through the real middleware behavior
(CORSMiddleware preflight responses) and the application factory.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

DEV_SETTINGS = dict(ENVIRONMENT="development", DEBUG=True)
PROD_SETTINGS = dict(
    ENVIRONMENT="production",
    DEBUG=False,
    FRONTEND_URL="https://app.example.com",
    ALLOWED_ORIGINS="",
    CORS_ORIGIN_REGEX=r"^https://app(-[a-zA-Z0-9_-]+)?\.example\.com$",
)


def _client(**overrides) -> TestClient:
    app = create_app(Settings(**overrides))
    return TestClient(app)


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


def test_dev_localhost_origin_accepted():
    client = _client(**DEV_SETTINGS)
    resp = _preflight(client, "http://localhost:3000")
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_dev_explicitly_configured_lan_origin_accepted():
    client = _client(**DEV_SETTINGS, ALLOWED_ORIGINS="http://192.168.1.50:3000")
    resp = _preflight(client, "http://192.168.1.50:3000")
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://192.168.1.50:3000"


def test_dev_unconfigured_lan_origin_rejected():
    client = _client(**DEV_SETTINGS)
    resp = _preflight(client, "http://192.168.1.77:3000")
    assert resp.status_code == 400
    assert resp.headers.get("access-control-allow-origin") is None


def test_dev_lan_regex_active_when_explicitly_opted_in():
    client = _client(**DEV_SETTINGS, ALLOW_DEV_LAN_ORIGINS=True)
    resp = _preflight(client, "http://192.168.1.77:3000")
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://192.168.1.77:3000"


def test_prod_trusted_origin_accepted():
    client = _client(**PROD_SETTINGS)
    resp = _preflight(client, "https://app.example.com")
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://app.example.com"


def test_prod_untrusted_origin_rejected():
    client = _client(**PROD_SETTINGS)
    resp = _preflight(client, "https://evil.example.net")
    assert resp.status_code == 400
    assert resp.headers.get("access-control-allow-origin") is None


def test_dev_regex_not_applied_in_production():
    client = _client(**PROD_SETTINGS)
    resp = _preflight(client, "http://192.168.1.77:3000")
    assert resp.status_code == 400
    assert resp.headers.get("access-control-allow-origin") is None


def test_wildcard_origin_with_credentials_rejected():
    with pytest.raises(RuntimeError, match="wildcard"):
        _client(ENVIRONMENT="production", DEBUG=False, FRONTEND_URL="*", CORS_ORIGIN_REGEX="")


def test_missing_production_origin_configuration_fails_clearly():
    with pytest.raises(RuntimeError, match="no trusted origins"):
        _client(
            ENVIRONMENT="production",
            DEBUG=False,
            FRONTEND_URL="",
            ALLOWED_ORIGINS="",
            CORS_ORIGIN_REGEX="",
        )


def test_local_origin_rejected_in_production_configuration():
    with pytest.raises(RuntimeError, match="localhost"):
        _client(
            ENVIRONMENT="production",
            DEBUG=False,
            FRONTEND_URL="http://localhost:3000",
            ALLOWED_ORIGINS="",
            CORS_ORIGIN_REGEX="",
        )
