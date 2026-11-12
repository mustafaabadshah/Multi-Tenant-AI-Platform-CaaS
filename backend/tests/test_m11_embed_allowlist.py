"""M11 Part 1 remediation: embed allowlist enforcement (fail closed)."""

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant
from app.services.publishing_service import is_origin_allowed


def _raw(domains: list[str]) -> str:
    return json.dumps(domains)


@pytest.mark.parametrize(
    ("origin", "domains", "expected"),
    [
        ("https://example.com", ["example.com"], True),
        ("https://evil.com", ["example.com"], False),
        (None, ["example.com"], False),
        ("", ["example.com"], False),
        (None, ["*"], True),
        ("malformed-origin", ["example.com"], False),
        ("https://evil-example.com", ["example.com"], False),
        ("https://sub.example.com", ["example.com"], False),
        ("https://example.com", ["*.example.com"], False),
        ("https://sub.example.com", ["*.example.com"], True),
        ("https://a.b.example.com", ["*.example.com"], True),
        ("https://evil-example.com", ["*.example.com"], False),
        ("https://example.com:8443", ["example.com"], True),
        ("http://example.com:8080", ["example.com"], True),
        ("https://example.com:8443", ["example.com:8443"], True),
        ("https://example.com:9443", ["example.com:8443"], False),
        ("https://example.com", ["example.com:8443"], False),
        ("http://example.com", ["example.com"], True),
        ("https://example.com/path?q=1", ["example.com"], True),
        ("ftp://example.com", ["example.com"], False),
        ("https://EXAMPLE.com", ["Example.COM"], True),
        ("https://example.com", ["example.com", "other.org"], True),
    ],
)
def test_origin_allowlist_matrix(origin, domains, expected):
    """Host, wildcard-subdomain, scheme, port, and malformed-input behavior."""
    assert is_origin_allowed(origin, _raw(domains)) is expected


@pytest.mark.parametrize("raw", [None, "", "[]"])
def test_empty_allowlist_is_unrestricted(raw):
    """An empty allowlist intentionally allows every origin."""
    assert is_origin_allowed(None, raw) is True


def test_wildcard_allows_missing_origin():
    """An explicit wildcard entry allows non-browser/direct requests."""
    assert is_origin_allowed(None, _raw(["*"])) is True


def test_malformed_allowlist_config_fails_closed():
    """A corrupt stored allowlist must not silently become a wildcard."""
    assert is_origin_allowed("https://example.com", "{not valid json") is False


async def _create_assistant(db: AsyncSession, tenant_id: uuid.UUID, name: str) -> Assistant:
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        slug=name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:6],
        description="Embed allowlist test assistant",
        system_prompt="You are a helpful assistant.",
        llm_provider="mock",
        default_model="mock-gpt",
        temperature=0.5,
        max_tokens=256,
        retrieval_mode="hybrid",
        top_k=3,
    )
    db.add(asst)
    await db.commit()
    await db.refresh(asst)
    return asst


@pytest.mark.asyncio
async def test_public_chat_enforces_allowlist_and_embed_config_stays_public(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "Embed Allowlist Bot")
    auth_headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    pub_resp = await client.post(
        f"/api/v1/assistants/{asst.id}/publish",
        json={"visibility": "PUBLIC", "allowed_domains": ["example.com"]},
        headers=auth_headers,
    )
    assert pub_resp.status_code == 200
    public_id = pub_resp.json()["public_id"]

    metadata_resp = await client.get(f"/api/v1/public/assistants/{public_id}")
    assert metadata_resp.status_code == 200

    embed_resp = await client.get(f"/api/v1/public/embed/{public_id}/config")
    assert embed_resp.status_code == 200

    allowed = await client.post(
        f"/api/v1/public/assistants/{public_id}/chat",
        json={"message": "Hello from the allowlisted site"},
        headers={"Origin": "https://example.com"},
    )
    assert allowed.status_code == 200

    blocked = await client.post(
        f"/api/v1/public/assistants/{public_id}/chat",
        json={"message": "Hello from an untrusted site"},
        headers={"Origin": "https://evil.com"},
    )
    assert blocked.status_code == 403
    assert "not permitted" in blocked.json()["detail"]

    missing_origin = await client.post(
        f"/api/v1/public/assistants/{public_id}/chat",
        json={"message": "No origin header"},
    )
    assert missing_origin.status_code == 403
    assert "not permitted" in missing_origin.json()["detail"]
