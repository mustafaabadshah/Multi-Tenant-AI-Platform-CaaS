"""M13.2 SEC-4: provider endpoint SSRF validation and custom-endpoint policy.

All tests are offline. DNS is monkeypatched, provider HTTP clients are either
not constructed or replaced with an in-memory stub.
"""

import ipaddress
import socket
import uuid
from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.llm.base import LLMConfig
from app.llm.endpoint_validation import (
    OFFICIAL_PROVIDER_HOSTS,
    validate_custom_provider_endpoint,
    validate_provider_endpoint,
)
from app.llm.providers.anthropic_provider import AnthropicLLMProvider
from app.llm.providers.gemini_provider import GeminiLLMProvider
from app.llm.providers.groq_provider import GroqLLMProvider
from app.llm.providers.openai_provider import OpenAICompatibleLLMProvider
from app.services.byok_vault import BYOKVaultService

PUBLIC_IP = "93.184.216.34"


def _getaddrinfo(*addresses: str):
    """Build a socket.getaddrinfo replacement returning exactly these addresses."""

    def fake(host, port, family=0, type=0, proto=0, flags=0):
        results = []
        for raw in addresses:
            ip = ipaddress.ip_address(raw)
            if ip.version == 6:
                sockaddr = (str(ip), port, 0, 0)
                fam = socket.AF_INET6
            else:
                sockaddr = (str(ip), port)
                fam = socket.AF_INET
            results.append((fam, socket.SOCK_STREAM, 6, "", sockaddr))
        return results

    return fake


@pytest.fixture(autouse=True)
def _block_real_dns(monkeypatch):
    """Fail the test if any code path attempts a real DNS lookup."""

    def unexpected(*args, **kwargs):
        raise AssertionError("test attempted a real DNS resolution")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected)


PROVIDERS = [
    OpenAICompatibleLLMProvider(
        name="openai", default_base_url="https://api.openai.com/v1"
    ),
    GroqLLMProvider(),
    AnthropicLLMProvider(),
    GeminiLLMProvider(),
]

PROVIDER_IDS = [p.provider_name for p in PROVIDERS]


# ---------------------------------------------------------------------------
# Central validator: rejection matrix
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://10.0.0.5",
        "http://172.16.0.1",
        "http://192.168.1.10",
        "http://[::1]",
        "http://[fd00::1]",
        "http://169.254.1.1",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1",
        "http://[fd00:ec2::254]/latest/meta-data/",
        "ftp://api.example.com/v1",
        "file:///etc/passwd",
        "not-a-url",
        "http://",
        "https://api example.com/v1",
        "http://user:secret@api.example.com/v1",
        "https://api.example.com:99999/v1",
        "http://api.example.com:0/v1",
    ],
)
def test_rejects_unsafe_or_malformed_endpoints(url, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo("127.0.0.1"))
    with pytest.raises(ValueError):
        validate_provider_endpoint(url)


def test_embedded_credentials_are_not_echoed():
    with pytest.raises(ValueError) as exc_info:
        validate_provider_endpoint("https://user:topsecret@api.example.com/v1")
    message = str(exc_info.value)
    assert "topsecret" not in message
    assert "user" not in message


def test_rejects_mixed_public_and_private_dns_answers(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", _getaddrinfo(PUBLIC_IP, "10.0.0.5")
    )
    with pytest.raises(ValueError, match="private"):
        validate_provider_endpoint("https://api.example.com/v1")


def test_rejects_mixed_public_and_loopback_ipv6_answers(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", _getaddrinfo(PUBLIC_IP, "::1")
    )
    with pytest.raises(ValueError, match="loopback"):
        validate_provider_endpoint("https://api.example.com/v1")


def test_rejects_unresolvable_host(monkeypatch):
    def failing(host, port, family=0, type=0, proto=0, flags=0):
        raise socket.gaierror("name resolution failed")

    monkeypatch.setattr(socket, "getaddrinfo", failing)
    with pytest.raises(ValueError, match="Could not resolve"):
        validate_provider_endpoint("https://api.example.com/v1")


# ---------------------------------------------------------------------------
# Central validator: allowed targets
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "https://api.anthropic.com/v1",
        "https://generativelanguage.googleapis.com/v1beta",
        "https://api.groq.com/openai/v1",
    ],
)
def test_allows_official_provider_domains(url, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo(PUBLIC_IP))
    assert validate_provider_endpoint(url) == url.rstrip("/")


def test_official_host_allowlist_is_documented():
    assert "api.openai.com" in OFFICIAL_PROVIDER_HOSTS
    assert "api.anthropic.com" in OFFICIAL_PROVIDER_HOSTS
    assert "generativelanguage.googleapis.com" in OFFICIAL_PROVIDER_HOSTS
    assert "api.groq.com" in OFFICIAL_PROVIDER_HOSTS


def test_allows_public_ip_with_validated_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo("8.8.8.8"))
    assert validate_provider_endpoint("https://8.8.8.8/v1") == "https://8.8.8.8/v1"


def test_allow_local_permits_operator_loopback_only(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo("127.0.0.1"))
    assert (
        validate_provider_endpoint("http://localhost:20128/v1", allow_local=True)
        == "http://localhost:20128/v1"
    )
    with pytest.raises(ValueError, match="loopback"):
        validate_provider_endpoint("http://localhost:20128/v1")


def test_allow_local_never_permits_cloud_metadata():
    with pytest.raises(ValueError, match="cloud metadata"):
        validate_provider_endpoint(
            "http://169.254.169.254/latest/meta-data/", allow_local=True
        )
    with pytest.raises(ValueError, match="cloud metadata"):
        validate_provider_endpoint(
            "http://metadata.google.internal/computeMetadata/v1", allow_local=True
        )


# ---------------------------------------------------------------------------
# Custom endpoint feature gate
# ---------------------------------------------------------------------------
def test_custom_endpoints_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "CUSTOM_PROVIDER_ENDPOINTS_ENABLED", False)
    with pytest.raises(ValueError, match="disabled"):
        validate_custom_provider_endpoint("https://api.example.com/v1")


def test_custom_endpoints_enabled_allows_public_target(monkeypatch):
    monkeypatch.setattr(settings, "CUSTOM_PROVIDER_ENDPOINTS_ENABLED", True)
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo(PUBLIC_IP))
    assert (
        validate_custom_provider_endpoint("https://api.example.com/v1")
        == "https://api.example.com/v1"
    )


def test_custom_endpoints_enabled_still_rejects_private_target(monkeypatch):
    monkeypatch.setattr(settings, "CUSTOM_PROVIDER_ENDPOINTS_ENABLED", True)
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo("192.168.1.10"))
    with pytest.raises(ValueError, match="private"):
        validate_custom_provider_endpoint("https://internal.example.com/v1")


# ---------------------------------------------------------------------------
# Provider-specific enforcement
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("provider", PROVIDERS, ids=PROVIDER_IDS)
def test_provider_defaults_validate_as_public(provider, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo(PUBLIC_IP))
    resolved = provider._resolve_base_url(LLMConfig(provider=provider.provider_name))
    assert resolved.startswith("https://")


@pytest.mark.parametrize("provider", PROVIDERS, ids=PROVIDER_IDS)
def test_provider_rejects_custom_endpoint_when_disabled(provider, monkeypatch):
    monkeypatch.setattr(settings, "CUSTOM_PROVIDER_ENDPOINTS_ENABLED", False)
    config = LLMConfig(
        provider=provider.provider_name,
        base_url="https://custom.example.com/v1",
    )
    with pytest.raises(ValueError, match="disabled"):
        provider._resolve_base_url(config)


@pytest.mark.parametrize("provider", PROVIDERS, ids=PROVIDER_IDS)
def test_provider_accepts_public_custom_endpoint_when_enabled(provider, monkeypatch):
    monkeypatch.setattr(settings, "CUSTOM_PROVIDER_ENDPOINTS_ENABLED", True)
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo(PUBLIC_IP))
    config = LLMConfig(
        provider=provider.provider_name,
        base_url="https://custom.example.com/v1",
    )
    assert (
        provider._resolve_base_url(config) == "https://custom.example.com/v1"
    )


@pytest.mark.parametrize("provider", PROVIDERS, ids=PROVIDER_IDS)
def test_provider_rejects_private_custom_endpoint_when_enabled(provider, monkeypatch):
    monkeypatch.setattr(settings, "CUSTOM_PROVIDER_ENDPOINTS_ENABLED", True)
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo("10.0.0.5"))
    config = LLMConfig(
        provider=provider.provider_name,
        base_url="https://internal.example.com/v1",
    )
    with pytest.raises(ValueError, match="private"):
        provider._resolve_base_url(config)


def test_omniroute_operator_endpoint_may_use_localhost(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo("127.0.0.1"))
    provider = OpenAICompatibleLLMProvider(
        name="omniroute", default_base_url="http://localhost:20128/v1"
    )
    assert (
        provider._resolve_base_url(LLMConfig(provider="omniroute"))
        == "http://localhost:20128/v1"
    )


def test_omniroute_tenant_supplied_endpoint_remains_gated(monkeypatch):
    monkeypatch.setattr(settings, "CUSTOM_PROVIDER_ENDPOINTS_ENABLED", False)
    provider = OpenAICompatibleLLMProvider(
        name="omniroute", default_base_url="http://localhost:20128/v1"
    )
    config = LLMConfig(provider="omniroute", base_url="http://127.0.0.1:8080/v1")
    with pytest.raises(ValueError, match="disabled"):
        provider._resolve_base_url(config)


# ---------------------------------------------------------------------------
# Redirect hardening
# ---------------------------------------------------------------------------
def test_provider_client_constructions_disable_redirects():
    provider_dir = Path(__file__).resolve().parents[1] / "app" / "llm" / "providers"
    for filename in (
        "openai_provider.py",
        "anthropic_provider.py",
        "gemini_provider.py",
        "groq_provider.py",
    ):
        lines = (provider_dir / filename).read_text(encoding="utf-8").splitlines()
        constructions = [line for line in lines if "httpx.AsyncClient(" in line]
        assert constructions, f"{filename} has no httpx client construction"
        for line in constructions:
            assert "follow_redirects=False" in line, f"{filename}: {line.strip()}"


class _StubResponse:
    status_code = 200
    text = ""

    def json(self):
        return {}


class _StubAsyncClient:
    instances: list["_StubAsyncClient"] = []

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        type(self).instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, *args, **kwargs):
        return _StubResponse()

    async def post(self, *args, **kwargs):
        return _StubResponse()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", PROVIDERS, ids=PROVIDER_IDS)
async def test_provider_clients_constructed_without_redirects(provider, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo(PUBLIC_IP))
    _StubAsyncClient.instances.clear()
    monkeypatch.setattr(httpx, "AsyncClient", _StubAsyncClient)

    config = LLMConfig(provider=provider.provider_name, api_key="sk-test-key")
    assert await provider.validate_key(config) is True
    assert _StubAsyncClient.instances
    assert all(
        client.kwargs.get("follow_redirects") is False
        for client in _StubAsyncClient.instances
    )


# ---------------------------------------------------------------------------
# BYOK enforcement before persistence / HTTP
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_byok_create_rejects_custom_endpoint_when_disabled(
    client, seed_data, monkeypatch
):
    monkeypatch.setattr(settings, "CUSTOM_PROVIDER_ENDPOINTS_ENABLED", False)
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }
    response = await client.post(
        "/api/v1/providers/credentials",
        json={
            "provider_name": "openai",
            "display_name": "Custom Endpoint Key",
            "api_key": "sk-test-custom-endpoint",
            "base_url": "https://custom.example.com/v1",
        },
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert "disabled" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enabled", "base_url", "fragment"),
    [
        (False, "https://custom.example.com/v1", "disabled"),
        (True, "http://127.0.0.1:8080/v1", "loopback"),
    ],
)
async def test_byok_test_credential_validates_before_provider_call(
    db_session, monkeypatch, enabled, base_url, fragment
):
    monkeypatch.setattr(settings, "CUSTOM_PROVIDER_ENDPOINTS_ENABLED", enabled)
    vault = BYOKVaultService(db_session, uuid.uuid4())

    class _Credential:
        encrypted_api_key = "not-decrypted"
        status = "HEALTHY"
        error_message = None
        last_tested_at = None

    credential = _Credential()
    credential.base_url = base_url

    async def get_credential(_credential_id):
        return credential

    def get_registry():
        raise AssertionError("provider call must not run for a rejected endpoint")

    monkeypatch.setattr(vault, "get_credential", get_credential)
    monkeypatch.setattr("app.services.byok_vault.get_llm_registry", get_registry)

    valid, error = await vault.test_credential(uuid.uuid4())
    assert valid is False
    assert fragment in (error or "")
    assert credential.status == "UNHEALTHY"