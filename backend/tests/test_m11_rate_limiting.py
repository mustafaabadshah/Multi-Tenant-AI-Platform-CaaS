"""M11 Part 2 remediation: in-process, dependency-free rate limiting tests."""

import hashlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.assistant_runtime.runtime import AssistantRuntime
from app.core import rate_limit
from app.core.config import settings
from app.core.rate_limit import (
    SlidingWindowLimiter,
    client_identity,
    enforce_rate_limit,
    limiter,
)
from app.models.assistant import Assistant

RATE_LIMIT_DETAIL = "Too many requests. Please try again later."


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


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


# ---------------------------------------------------------------------------
# Unit: sliding-window limiter behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allows_up_to_limit_then_denies_with_retry_after():
    local = SlidingWindowLimiter()
    for _ in range(3):
        allowed, retry_after = await local.check("key-a", 3, 60)
        assert allowed is True
        assert retry_after == 0

    allowed, retry_after = await local.check("key-a", 3, 60)
    assert allowed is False
    assert retry_after > 0


@pytest.mark.asyncio
async def test_window_expiry_allows_again(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(rate_limit, "_now", lambda: clock["now"])
    local = SlidingWindowLimiter()

    assert (await local.check("key-a", 2, 60))[0] is True
    assert (await local.check("key-a", 2, 60))[0] is True
    assert (await local.check("key-a", 2, 60))[0] is False

    clock["now"] += 61.0
    allowed, retry_after = await local.check("key-a", 2, 60)
    assert allowed is True
    assert retry_after == 0


@pytest.mark.asyncio
async def test_keys_are_isolated():
    local = SlidingWindowLimiter()
    assert (await local.check("key-a", 1, 60))[0] is True
    assert (await local.check("key-a", 1, 60))[0] is False
    assert (await local.check("key-b", 1, 60))[0] is True


@pytest.mark.asyncio
async def test_reset_clears_state():
    local = SlidingWindowLimiter()
    assert (await local.check("key-a", 1, 60))[0] is True
    assert (await local.check("key-a", 1, 60))[0] is False

    local.reset()
    assert (await local.check("key-a", 1, 60))[0] is True


@pytest.mark.asyncio
async def test_key_storage_is_bounded():
    local = SlidingWindowLimiter(max_keys=2)
    assert (await local.check("oldest", 1, 60))[0] is True
    assert (await local.check("middle", 1, 60))[0] is True
    assert (await local.check("newest", 1, 60))[0] is True

    # The oldest key was evicted to honour the bound, so it starts fresh.
    allowed, _ = await local.check("oldest", 1, 60)
    assert allowed is True


# ---------------------------------------------------------------------------
# Unit: client identity resolution (proxy trust)
# ---------------------------------------------------------------------------


def test_untrusted_client_ignores_forwarded_header(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "")
    request = _request("198.51.100.7", {"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})
    assert client_identity(request) == "198.51.100.7"


def test_trusted_proxy_uses_first_forwarded_hop(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "10.0.0.5, 198.51.100.7")
    request = _request("198.51.100.7", {"X-Forwarded-For": " 203.0.113.9 , 10.0.0.5"})
    assert client_identity(request) == "203.0.113.9"


def test_trusted_proxy_with_empty_forwarded_value_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "198.51.100.7")
    request = _request("198.51.100.7", {"X-Forwarded-For": "   "})
    assert client_identity(request) == "198.51.100.7"


# ---------------------------------------------------------------------------
# Unit: hashed keys and disabled mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enforced_key_is_hashed_and_contains_no_raw_identity(monkeypatch):
    captured: dict[str, str] = {}

    async def capture(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        captured["key"] = key
        return True, 0

    monkeypatch.setattr(rate_limit.limiter, "check", capture)

    raw_ip = "198.51.100.42"
    email = "victim@example.com"
    await enforce_rate_limit("auth.login", f"{raw_ip}:{email}", 10, 60)

    stored = captured["key"]
    assert stored == hashlib.sha256(f"auth.login:{raw_ip}:{email}".encode("utf-8")).hexdigest()
    assert len(stored) == 64
    assert raw_ip not in stored
    assert email not in stored


@pytest.mark.asyncio
async def test_disabled_rate_limiting_never_raises(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    for _ in range(100):
        await enforce_rate_limit("auth.login", "203.0.113.1:user@example.com", 1, 60)


# ---------------------------------------------------------------------------
# API: login / register enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_rate_limit_returns_429_with_retry_after(
    client: AsyncClient, seed_data: dict, monkeypatch
):
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_PER_MINUTE", 2)
    bad_login = {"email": "owner_a@companya.com", "password": "WrongPassword!"}

    for _ in range(2):
        resp = await client.post("/api/v1/auth/login", json=bad_login)
        assert resp.status_code == 401

    limited = await client.post("/api/v1/auth/login", json=bad_login)
    assert limited.status_code == 429
    assert limited.json()["detail"] == RATE_LIMIT_DETAIL
    assert int(limited.headers["Retry-After"]) > 0

    # A different email shares the IP but has an independent counter.
    other_email = await client.post(
        "/api/v1/auth/login",
        json={"email": "owner_b@companyb.com", "password": "WrongPassword!"},
    )
    assert other_email.status_code == 401


@pytest.mark.asyncio
async def test_register_rate_limit_returns_429(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_REGISTRATION", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_REGISTER_PER_HOUR", 1)

    first = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rate_first@example.com",
            "password": "Password123!",
            "full_name": "Rate First",
        },
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rate_second@example.com",
            "password": "Password123!",
            "full_name": "Rate Second",
        },
    )
    assert second.status_code == 429
    assert second.json()["detail"] == RATE_LIMIT_DETAIL
    assert int(second.headers["Retry-After"]) > 0


# ---------------------------------------------------------------------------
# API: public chat enforcement precedes sessions/provider calls
# ---------------------------------------------------------------------------


async def _create_published_assistant(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    name: str = "Rate Limited Public Asst",
) -> str:
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=seed_data["tenant_a"].id,
        name=name,
        slug=name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:6],
        description="Rate limit test assistant",
        system_prompt="You are a helpful assistant.",
        llm_provider="mock",
        default_model="mock-gpt",
        temperature=0.5,
        max_tokens=256,
        retrieval_mode="hybrid",
        top_k=3,
    )
    db_session.add(asst)
    await db_session.commit()
    await db_session.refresh(asst)

    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }
    resp = await client.post(
        f"/api/v1/assistants/{asst.id}/publish",
        json={"visibility": "PUBLIC", "allowed_domains": ["*"]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["public_id"]


@pytest.mark.asyncio
async def test_public_chat_rate_limit_blocks_before_provider_call(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    monkeypatch,
):
    public_id = await _create_published_assistant(client, seed_data, db_session)
    monkeypatch.setattr(settings, "RATE_LIMIT_PUBLIC_MESSAGE_PER_MINUTE", 1)

    runtime_calls: list[uuid.UUID] = []

    async def fake_stream(
        self, conversation_id, user_message, is_public=False, traffic_type="internal"
    ):
        runtime_calls.append(conversation_id)
        yield "event: message_done\ndata: {}\n\n"

    monkeypatch.setattr(AssistantRuntime, "stream_chat", fake_stream)

    url = f"/api/v1/public/assistants/{public_id}/chat"
    first = await client.post(
        url,
        json={"message": "Hello", "session_token": "sess_rate_limit_first_000001"},
    )
    assert first.status_code == 200
    assert first.headers.get("x-session-token")

    # A brand-new session token must not bypass the IP-level limit.
    second = await client.post(
        url,
        json={"message": "Hello again", "session_token": "sess_rate_limit_second_000002"},
    )
    assert second.status_code == 429
    assert second.json()["detail"] == RATE_LIMIT_DETAIL
    assert int(second.headers["Retry-After"]) > 0
    assert len(runtime_calls) == 1, "denied request must not reach the runtime/provider"