"""M13.2 SEC-1/SEC-2/SEC-3: public publishing and developer API kill switches.

Verifies default-off feature gates, public route non-bypass, developer API
authentication blocking, and developer conversation scoping.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message
from app.models.publishing import APIKey, AssistantPublication, PublicChatSession
from app.services.publishing_service import generate_opaque_public_id

PUBLIC_ID = "pub_existing_publication_0000000000000000"


def _headers(seed_data: dict, tenant_key: str = "tenant_a") -> dict[str, str]:
    tenant = seed_data[tenant_key]
    token_key = "token_a_owner" if tenant_key == "tenant_a" else "token_b_owner"
    return {
        "Authorization": f"Bearer {seed_data[token_key]}",
        "X-Tenant-ID": str(tenant.id),
    }


async def _create_assistant(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    name: str = "M13.2 Assistant",
) -> Assistant:
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        slug=name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:6],
        description="M13.2 security test assistant",
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


async def _create_publication(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    assistant_id: uuid.UUID,
    *,
    visibility: str = "PUBLIC",
    is_active: bool = True,
    public_id: str | None = None,
) -> AssistantPublication:
    pub = AssistantPublication(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        assistant_id=assistant_id,
        public_id=public_id or generate_opaque_public_id(),
        visibility=visibility,
        is_active=is_active,
        allowed_domains='["*"]',
        brand_color="#0284c7",
    )
    db.add(pub)
    await db.commit()
    await db.refresh(pub)
    return pub


async def _create_api_key(
    client: AsyncClient,
    seed_data: dict,
    *,
    name: str,
    scopes: list[str] | None = None,
    assistant_id: uuid.UUID | None = None,
    tenant_key: str = "tenant_a",
) -> tuple[str, str]:
    payload: dict = {"name": name, "scopes": scopes or ["assistant:read", "assistant:chat"]}
    if assistant_id is not None:
        payload["assistant_id"] = str(assistant_id)
    resp = await client.post(
        "/api/v1/developer/api-keys",
        json=payload,
        headers=_headers(seed_data, tenant_key),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return data["raw_key"], data["id"]


def _dev_headers(raw_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_key}"}


def _assert_streaming_chat(response) -> None:
    assert response.status_code == 200, response.text
    assert "text/event-stream" in response.headers["content-type"]
    assert "event: message_start" in response.text
    assert "event: token" in response.text
    assert "event: message_complete" in response.text


async def _create_conversation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    assistant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    title: str = "Scoped Conversation",
) -> Conversation:
    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        assistant_id=assistant_id,
        user_id=user_id,
        title=title,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def _count(db: AsyncSession, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for column, value in filters.items():
        stmt = stmt.where(getattr(model, column) == value)
    return int((await db.execute(stmt)).scalar_one())


# ==============================================================================
# SEC-1: GLOBAL PUBLIC PUBLISHING KILL SWITCH
# ==============================================================================


def test_feature_flags_default_to_false_without_configuration(monkeypatch):
    """Both feature gates must default to disabled when no configuration is supplied."""
    monkeypatch.delenv("PUBLIC_PUBLISHING_ENABLED", raising=False)
    monkeypatch.delenv("DEVELOPER_API_ENABLED", raising=False)
    fresh = Settings(_env_file=None)
    assert fresh.PUBLIC_PUBLISHING_ENABLED is False
    assert fresh.DEVELOPER_API_ENABLED is False


@pytest.mark.asyncio
async def test_explicit_disabled_blocks_every_public_path_and_session_reuse(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    monkeypatch,
):
    """Publishing, metadata, chat, embed config, and existing sessions are all blocked."""
    monkeypatch.setattr(settings, "PUBLIC_PUBLISHING_ENABLED", False)
    tenant_a = seed_data["tenant_a"]
    headers = _headers(seed_data)
    asst = await _create_assistant(db_session, tenant_a.id, "Disabled Public Bot")

    publish_resp = await client.post(
        f"/api/v1/assistants/{asst.id}/publish",
        json={"visibility": "PUBLIC", "allowed_domains": ["*"]},
        headers=headers,
    )
    assert publish_resp.status_code == 403
    assert publish_resp.json()["detail"] == "Public publishing is disabled"
    assert await _count(db_session, AssistantPublication, tenant_id=tenant_a.id) == 0

    # Simulate a publication that already existed before the kill switch was flipped.
    pub = await _create_publication(db_session, tenant_a.id, asst.id, public_id=PUBLIC_ID)
    now = datetime.now(UTC)
    existing_session = PublicChatSession(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        publication_id=pub.id,
        session_token="sess_existing_m13_2_session_0001",
        expires_at=now + timedelta(days=1),
    )
    db_session.add(existing_session)
    await db_session.commit()

    metadata_resp = await client.get(f"/api/v1/public/assistants/{PUBLIC_ID}")
    assert metadata_resp.status_code == 404

    for path in (f"/api/v1/public/embed/{PUBLIC_ID}/config", f"/api/v1/public/assistants/{PUBLIC_ID}/embed-config"):
        embed_resp = await client.get(path)
        assert embed_resp.status_code == 404

    script_resp = await client.get("/api/v1/public/embed.js")
    assert script_resp.status_code == 200
    assert "application/javascript" in script_resp.headers["content-type"]

    existing_session_resp = await client.post(
        f"/api/v1/public/assistants/{PUBLIC_ID}/chat",
        json={"message": "Reuse session", "session_token": "sess_existing_m13_2_session_0001"},
    )
    assert existing_session_resp.status_code == 403
    assert existing_session_resp.json()["detail"] == "Public publishing is disabled"

    new_session_resp = await client.post(
        f"/api/v1/public/assistants/{PUBLIC_ID}/chat",
        json={"message": "Create session", "session_token": "sess_new_m13_2_session_0002"},
    )
    assert new_session_resp.status_code == 403
    assert new_session_resp.json()["detail"] == "Public publishing is disabled"

    assert await _count(db_session, PublicChatSession, tenant_id=tenant_a.id) == 1
    assert await _count(db_session, Conversation, tenant_id=tenant_a.id) == 0


@pytest.mark.asyncio
async def test_enabled_allows_publish_metadata_and_public_chat(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """Opting in restores the normal publish, metadata, and public chat flow."""
    tenant_a = seed_data["tenant_a"]
    headers = _headers(seed_data)
    asst = await _create_assistant(db_session, tenant_a.id, "Enabled Public Bot")

    publish_resp = await client.post(
        f"/api/v1/assistants/{asst.id}/publish",
        json={"visibility": "PUBLIC", "allowed_domains": ["*"]},
        headers=headers,
    )
    assert publish_resp.status_code == 200, publish_resp.text
    public_id = publish_resp.json()["public_id"]

    metadata_resp = await client.get(f"/api/v1/public/assistants/{public_id}")
    assert metadata_resp.status_code == 200
    assert metadata_resp.json()["public_id"] == public_id

    chat_resp = await client.post(
        f"/api/v1/public/assistants/{public_id}/chat",
        json={"message": "Hello from the public"},
    )
    _assert_streaming_chat(chat_resp)


@pytest.mark.asyncio
async def test_disabled_still_allows_unpublish_and_private_updates(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    monkeypatch,
):
    """Withdrawal operations must always work; enabling public exposure must not."""
    monkeypatch.setattr(settings, "PUBLIC_PUBLISHING_ENABLED", False)
    tenant_a = seed_data["tenant_a"]
    headers = _headers(seed_data)
    asst = await _create_assistant(db_session, tenant_a.id, "Withdrawal Bot")
    await _create_publication(db_session, tenant_a.id, asst.id)

    private_resp = await client.patch(
        f"/api/v1/assistants/{asst.id}/publication",
        json={"visibility": "PRIVATE"},
        headers=headers,
    )
    assert private_resp.status_code == 200
    assert private_resp.json()["visibility"] == "PRIVATE"

    greeting_resp = await client.patch(
        f"/api/v1/assistants/{asst.id}/publication",
        json={"custom_greeting": "Maintenance in progress"},
        headers=headers,
    )
    assert greeting_resp.status_code == 200
    assert greeting_resp.json()["custom_greeting"] == "Maintenance in progress"

    deactivate_resp = await client.patch(
        f"/api/v1/assistants/{asst.id}/publication",
        json={"is_active": False},
        headers=headers,
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    enable_resp = await client.patch(
        f"/api/v1/assistants/{asst.id}/publication",
        json={"visibility": "PUBLIC"},
        headers=headers,
    )
    assert enable_resp.status_code == 403
    assert enable_resp.json()["detail"] == "Public publishing is disabled"

    reactivate_resp = await client.patch(
        f"/api/v1/assistants/{asst.id}/publication",
        json={"is_active": True},
        headers=headers,
    )
    assert reactivate_resp.status_code == 403

    unpublish_resp = await client.post(f"/api/v1/assistants/{asst.id}/unpublish", headers=headers)
    assert unpublish_resp.status_code == 200
    assert unpublish_resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_disabled_does_not_affect_private_workspace_chat(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    monkeypatch,
):
    """Authenticated workspace chat is independent of the public publishing gate."""
    monkeypatch.setattr(settings, "PUBLIC_PUBLISHING_ENABLED", False)
    tenant_a = seed_data["tenant_a"]
    headers = _headers(seed_data)
    asst = await _create_assistant(db_session, tenant_a.id, "Private Chat Bot")

    create_resp = await client.post(
        "/api/v1/conversations",
        json={"assistant_id": str(asst.id), "title": "Private Thread"},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    conv_id = create_resp.json()["id"]

    stream_resp = await client.post(
        f"/api/v1/conversations/{conv_id}/messages/stream",
        json={"content": "Hello private workspace"},
        headers=headers,
    )
    _assert_streaming_chat(stream_resp)


# ==============================================================================
# SEC-3: DEVELOPER API KILL SWITCH
# ==============================================================================


@pytest.mark.asyncio
async def test_developer_api_disabled_blocks_creation_auth_and_chat(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    monkeypatch,
    enable_public_features,
):
    """Disabling the developer API rejects new keys, existing keys, and inference."""
    tenant_a = seed_data["tenant_a"]
    headers = _headers(seed_data)
    asst = await _create_assistant(db_session, tenant_a.id, "Developer Gate Bot")
    raw_key, key_id = await _create_api_key(client, seed_data, name="Gate-Key")

    monkeypatch.setattr(settings, "DEVELOPER_API_ENABLED", False)

    create_resp = await client.post(
        "/api/v1/developer/api-keys",
        json={"name": "Blocked-Key", "scopes": ["assistant:read"]},
        headers=headers,
    )
    assert create_resp.status_code == 403
    assert create_resp.json()["detail"] == "Developer API is disabled"

    auth_resp = await client.get("/api/v1/developer/assistants", headers=_dev_headers(raw_key))
    assert auth_resp.status_code == 403
    assert auth_resp.json()["detail"] == "Developer API is disabled"

    missing_header_resp = await client.get("/api/v1/developer/assistants")
    assert missing_header_resp.status_code == 403

    chat_resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "Disabled developer chat"},
        headers=_dev_headers(raw_key),
    )
    assert chat_resp.status_code == 403

    key_record = await db_session.get(APIKey, uuid.UUID(key_id))
    assert key_record is not None
    assert key_record.is_active is True


@pytest.mark.asyncio
async def test_developer_api_disabled_does_not_affect_private_chat(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    monkeypatch,
):
    """Private workspace chat remains available while the developer API is disabled."""
    monkeypatch.setattr(settings, "DEVELOPER_API_ENABLED", False)
    tenant_a = seed_data["tenant_a"]
    headers = _headers(seed_data)
    asst = await _create_assistant(db_session, tenant_a.id, "Private Developer Gate Bot")
    conv = await _create_conversation(db_session, tenant_a.id, asst.id, seed_data["user_a_owner"].id)

    stream_resp = await client.post(
        f"/api/v1/conversations/{conv.id}/messages/stream",
        json={"content": "Private chat unaffected"},
        headers=headers,
    )
    _assert_streaming_chat(stream_resp)


@pytest.mark.asyncio
async def test_developer_api_enabled_allows_key_creation_auth_and_chat(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """Enabled path preserves key management, authentication, and inference."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "Enabled Developer Bot")
    raw_key, _key_id = await _create_api_key(client, seed_data, name="Enabled-Key")

    list_resp = await client.get("/api/v1/developer/assistants", headers=_dev_headers(raw_key))
    assert list_resp.status_code == 200
    assert any(item["id"] == str(asst.id) for item in list_resp.json())

    chat_resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "Hello enabled developer API"},
        headers=_dev_headers(raw_key),
    )
    _assert_streaming_chat(chat_resp)


# ==============================================================================
# SEC-2: DEVELOPER API CONVERSATION SCOPING
# ==============================================================================


@pytest.mark.asyncio
async def test_developer_chat_authorized_key_and_assistant(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """1. An authorized key may chat with the assistant it is permitted to use."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "Authorized Developer Bot")
    raw_key, _ = await _create_api_key(client, seed_data, name="Authorized-Key", assistant_id=asst.id)

    resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "Authorized request"},
        headers=_dev_headers(raw_key),
    )
    _assert_streaming_chat(resp)


@pytest.mark.asyncio
async def test_developer_key_restricted_to_another_assistant_is_rejected(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """2. A key restricted to assistant A cannot request assistant B."""
    tenant_a = seed_data["tenant_a"]
    asst_allowed = await _create_assistant(db_session, tenant_a.id, "Allowed Dev Bot")
    asst_blocked = await _create_assistant(db_session, tenant_a.id, "Blocked Dev Bot")
    raw_key, _ = await _create_api_key(
        client, seed_data, name="Restricted-Key", assistant_id=asst_allowed.id
    )

    resp = await client.post(
        f"/api/v1/developer/assistants/{asst_blocked.id}/chat",
        json={"message": "Wrong assistant"},
        headers=_dev_headers(raw_key),
    )
    assert resp.status_code == 403
    assert "restricted to assistant" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_developer_conversation_for_another_assistant_returns_404(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """3. A conversation bound to assistant B cannot be continued through assistant A."""
    tenant_a = seed_data["tenant_a"]
    asst_a = await _create_assistant(db_session, tenant_a.id, "Conversation Owner Bot")
    asst_b = await _create_assistant(db_session, tenant_a.id, "Other Assistant Bot")
    conv_b = await _create_conversation(
        db_session, tenant_a.id, asst_b.id, seed_data["user_a_owner"].id
    )
    raw_key, _ = await _create_api_key(client, seed_data, name="Scoped-Key", assistant_id=asst_a.id)

    resp = await client.post(
        f"/api/v1/developer/assistants/{asst_a.id}/chat",
        json={"message": "Cross assistant continuation", "conversation_id": str(conv_b.id)},
        headers=_dev_headers(raw_key),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Conversation not found in authorized organization"
    assert await _count(db_session, Message, conversation_id=conv_b.id) == 0


@pytest.mark.asyncio
async def test_developer_conversation_for_another_user_returns_404(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """4. A key created by user A cannot continue user B's conversation."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "User Scoped Bot")
    conv = await _create_conversation(
        db_session, tenant_a.id, asst.id, seed_data["user_a_employee"].id
    )
    raw_key, _ = await _create_api_key(client, seed_data, name="Owner-Key")

    resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "Other user's thread", "conversation_id": str(conv.id)},
        headers=_dev_headers(raw_key),
    )
    assert resp.status_code == 404
    assert await _count(db_session, Message, conversation_id=conv.id) == 0


@pytest.mark.asyncio
async def test_developer_cross_tenant_conversation_returns_404(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """5. A tenant A key cannot continue a tenant B conversation."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    asst_a = await _create_assistant(db_session, tenant_a.id, "Tenant A Dev Bot")
    asst_b = await _create_assistant(db_session, tenant_b.id, "Tenant B Dev Bot")
    conv_b = await _create_conversation(
        db_session, tenant_b.id, asst_b.id, seed_data["user_b_owner"].id
    )
    raw_key, _ = await _create_api_key(client, seed_data, name="Tenant-A-Key")

    resp = await client.post(
        f"/api/v1/developer/assistants/{asst_a.id}/chat",
        json={"message": "Cross tenant thread", "conversation_id": str(conv_b.id)},
        headers=_dev_headers(raw_key),
    )
    assert resp.status_code == 404
    assert await _count(db_session, Message, conversation_id=conv_b.id) == 0


@pytest.mark.asyncio
async def test_developer_unknown_conversation_id_returns_404(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """6. A non-existent conversation ID is rejected without existence disclosure."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "Unknown Conversation Bot")
    raw_key, _ = await _create_api_key(client, seed_data, name="Unknown-Conversation-Key")

    resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "No such conversation", "conversation_id": str(uuid.uuid4())},
        headers=_dev_headers(raw_key),
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Conversation not found in authorized organization"


@pytest.mark.asyncio
async def test_developer_new_conversation_is_scoped_to_authorized_assistant(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """7. Omitting conversation_id creates a conversation under the path assistant."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "New Conversation Bot")
    raw_key, _ = await _create_api_key(client, seed_data, name="New-Conversation-Key")

    resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "Start a fresh developer chat"},
        headers=_dev_headers(raw_key),
    )
    _assert_streaming_chat(resp)

    stmt = select(Conversation).where(
        Conversation.tenant_id == tenant_a.id,
        Conversation.assistant_id == asst.id,
    )
    conversations = list((await db_session.execute(stmt)).scalars().all())
    assert len(conversations) == 1
    assert conversations[0].user_id == seed_data["user_a_owner"].id


@pytest.mark.asyncio
async def test_developer_existing_conversation_continuation(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """8. A previously owned conversation can be continued by the same key."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "Continuation Bot")
    conv = await _create_conversation(
        db_session, tenant_a.id, asst.id, seed_data["user_a_owner"].id
    )
    raw_key, _ = await _create_api_key(client, seed_data, name="Continuation-Key")

    resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "Continue this thread", "conversation_id": str(conv.id)},
        headers=_dev_headers(raw_key),
    )
    _assert_streaming_chat(resp)
    assert await _count(db_session, Message, conversation_id=conv.id) == 2


@pytest.mark.asyncio
async def test_developer_streaming_response_contract(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """9. Developer inference streams SSE frames without buffering."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "Streaming Contract Bot")
    raw_key, _ = await _create_api_key(client, seed_data, name="Streaming-Key")

    resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "Stream this response"},
        headers=_dev_headers(raw_key),
    )
    _assert_streaming_chat(resp)
    assert resp.headers.get("cache-control") == "no-cache"


@pytest.mark.asyncio
async def test_developer_retry_or_regeneration_endpoint_not_implemented(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """10. N/A: this milestone exposes no developer retry/regeneration route."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "Retry Surface Bot")
    conv = await _create_conversation(
        db_session, tenant_a.id, asst.id, seed_data["user_a_owner"].id
    )
    raw_key, _ = await _create_api_key(client, seed_data, name="Retry-Probe-Key")

    for suffix in ("retry", "regenerate"):
        resp = await client.post(
            f"/api/v1/developer/assistants/{asst.id}/chat/{conv.id}/{suffix}",
            json={"message": "Retry attempt"},
            headers=_dev_headers(raw_key),
        )
        assert resp.status_code in (404, 405)


@pytest.mark.asyncio
async def test_developer_expired_key_is_rejected(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """11. Expired keys cannot authenticate or invoke developer inference."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "Expired Key Bot")
    raw_key, key_id = await _create_api_key(client, seed_data, name="Expired-Key")

    key_record = await db_session.get(APIKey, uuid.UUID(key_id))
    assert key_record is not None
    key_record.expires_at = datetime.now(UTC) - timedelta(minutes=5)
    await db_session.commit()

    auth_resp = await client.get("/api/v1/developer/assistants", headers=_dev_headers(raw_key))
    assert auth_resp.status_code == 401
    assert auth_resp.json()["detail"] == "API key has expired."

    chat_resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "Expired key chat"},
        headers=_dev_headers(raw_key),
    )
    assert chat_resp.status_code == 401


@pytest.mark.asyncio
async def test_developer_revoked_key_is_rejected(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """12. Revoked keys cannot authenticate or invoke developer inference."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "Revoked Key Bot")
    raw_key, key_id = await _create_api_key(client, seed_data, name="Revoked-Key")

    revoke_resp = await client.delete(
        f"/api/v1/developer/api-keys/{key_id}", headers=_headers(seed_data)
    )
    assert revoke_resp.status_code == 200

    auth_resp = await client.get("/api/v1/developer/assistants", headers=_dev_headers(raw_key))
    assert auth_resp.status_code == 401

    chat_resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "Revoked key chat"},
        headers=_dev_headers(raw_key),
    )
    assert chat_resp.status_code == 401


@pytest.mark.asyncio
async def test_developer_key_with_insufficient_scope_is_rejected(
    client: AsyncClient,
    seed_data: dict,
    db_session: AsyncSession,
    enable_public_features,
):
    """13. Read-only keys cannot invoke developer chat inference."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_assistant(db_session, tenant_a.id, "Insufficient Scope Bot")
    raw_key, _ = await _create_api_key(
        client, seed_data, name="Read-Only-Key", scopes=["assistant:read"]
    )

    read_resp = await client.get("/api/v1/developer/assistants", headers=_dev_headers(raw_key))
    assert read_resp.status_code == 200

    chat_resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "Missing chat scope"},
        headers=_dev_headers(raw_key),
    )
    assert chat_resp.status_code == 403
    assert "lacks required permission scope" in chat_resp.json()["detail"]
