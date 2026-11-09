"""Acceptance and Security Test Suite for M08: Assistant Publishing, Embeds, and Developer API Keys."""

import hashlib
import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant, AssistantKnowledgeBase
from app.models.knowledge import Document, DocumentChunk, KnowledgeBase
from app.models.publishing import APIKey, AssistantPublication
from app.models.provider import ProviderUsageLog
from app.services.api_key_service import APIKeyService, hash_api_key
from app.services.publishing_service import PublishingService, is_origin_allowed


async def _create_test_assistant(db: AsyncSession, tenant_id: uuid.UUID, name: str = "Test Assistant") -> Assistant:
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        slug=name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:6],
        description="Test assistant description",
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
async def test_publication_lifecycle(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Test full assistant publication lifecycle: get default, publish, update, and unpublish."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_test_assistant(db_session, tenant_a.id, "Lifecycle Assistant")
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # 1. Fetch initial publication status (auto-initializes as PRIVATE)
    resp = await client.get(f"/api/v1/assistants/{asst.id}/publication", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["assistant_id"] == str(asst.id)
    assert data["visibility"] == "PRIVATE"
    assert data["is_active"] is False
    assert data["public_id"].startswith("pub_")

    # 2. Publish assistant
    pub_payload = {
        "visibility": "PUBLIC",
        "allowed_domains": ["example.com", "app.example.com"],
        "custom_greeting": "Welcome to Acme Support!",
        "brand_color": "#0ea5e9",
    }
    resp = await client.post(f"/api/v1/assistants/{asst.id}/publish", json=pub_payload, headers=headers)
    assert resp.status_code == 200
    pub_data = resp.json()
    assert pub_data["is_active"] is True
    assert pub_data["visibility"] == "PUBLIC"
    assert "example.com" in pub_data["allowed_domains"]
    assert pub_data["custom_greeting"] == "Welcome to Acme Support!"

    # 3. Update publication settings
    update_payload = {"custom_greeting": "Updated greeting message"}
    resp = await client.patch(f"/api/v1/assistants/{asst.id}/publication", json=update_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["custom_greeting"] == "Updated greeting message"

    # 4. Unpublish assistant
    resp = await client.post(f"/api/v1/assistants/{asst.id}/unpublish", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_public_metadata_endpoint(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Verify public metadata endpoint reflects active publication state without leaking internal data."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_test_assistant(db_session, tenant_a.id, "Public Metadata Assistant")
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # Publish assistant
    pub_payload = {
        "visibility": "PUBLIC",
        "allowed_domains": ["*"],
        "custom_greeting": "Hello visitor!",
        "brand_color": "#0284c7",
    }
    resp = await client.post(f"/api/v1/assistants/{asst.id}/publish", json=pub_payload, headers=headers)
    assert resp.status_code == 200
    public_id = resp.json()["public_id"]

    # Unauthenticated client queries public metadata
    unauth_resp = await client.get(f"/api/v1/public/assistants/{public_id}")
    assert unauth_resp.status_code == 200
    meta = unauth_resp.json()
    assert meta["public_id"] == public_id
    assert meta["name"] == "Public Metadata Assistant"
    assert meta["custom_greeting"] == "Hello visitor!"
    assert meta["brand_color"] == "#0284c7"
    # Ensure tenant_id, database IDs, and system prompts are NOT leaked
    assert "tenant_id" not in meta
    assert "system_prompt" not in meta

    # Unpublish and verify immediate 404
    await client.post(f"/api/v1/assistants/{asst.id}/unpublish", headers=headers)
    revoked_resp = await client.get(f"/api/v1/public/assistants/{public_id}")
    assert revoked_resp.status_code == 404


@pytest.mark.asyncio
async def test_public_chat_origin_domain_restriction(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Verify that requests from disallowed origins are rejected with HTTP 403."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_test_assistant(db_session, tenant_a.id, "Domain Guard Assistant")
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # Publish with domain whitelist restricted to 'trusted.org'
    pub_payload = {
        "visibility": "PUBLIC",
        "allowed_domains": ["trusted.org"],
        "custom_greeting": "Welcome",
        "brand_color": "#0284c7",
    }
    resp = await client.post(f"/api/v1/assistants/{asst.id}/publish", json=pub_payload, headers=headers)
    assert resp.status_code == 200
    public_id = resp.json()["public_id"]

    # 1. Request from disallowed origin
    bad_resp = await client.post(
        f"/api/v1/public/assistants/{public_id}/chat",
        json={"message": "Hello"},
        headers={"Origin": "https://malicious-site.com"},
    )
    assert bad_resp.status_code == 403
    assert "not permitted" in bad_resp.json()["detail"]

    # 2. Request from allowed origin
    good_resp = await client.post(
        f"/api/v1/public/assistants/{public_id}/chat",
        json={"message": "Hello"},
        headers={"Origin": "https://trusted.org"},
    )
    assert good_resp.status_code == 200
    assert "text/event-stream" in good_resp.headers["content-type"]


@pytest.mark.asyncio
async def test_public_chat_private_knowledge_isolation(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Critical security test: public chat must NEVER retrieve documents with access_level != 'PUBLIC'."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_test_assistant(db_session, tenant_a.id, "Secured Assistant")
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # 1. Create a Knowledge Base attached to assistant
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Security Test KB",
        status="ACTIVE",
    )
    db_session.add(kb)
    await db_session.flush()

    # Document 1: INTERNAL (Secret)
    internal_doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="executive_compensation.pdf",
        safe_filename="executive_compensation.pdf",
        file_path="storage/executive_compensation.pdf",
        file_size=1024,
        mime_type="application/pdf",
        file_hash="h1",
        access_level="INTERNAL",
        status="PROCESSED",
    )
    internal_chunk = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=internal_doc.id,
        chunk_index=0,
        content="EXECUTIVE_CONFIDENTIAL_SALARY_FIGURE_999999",
        page_number=1,
    )

    # Document 2: PUBLIC (Allowed)
    public_doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="public_faq.pdf",
        safe_filename="public_faq.pdf",
        file_path="storage/public_faq.pdf",
        file_size=1024,
        mime_type="application/pdf",
        file_hash="h2",
        access_level="PUBLIC",
        status="PROCESSED",
    )
    public_chunk = DocumentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        document_id=public_doc.id,
        chunk_index=0,
        content="PUBLIC_HANDBOOK_BENEFITS_STANDARD_VACATION",
        page_number=1,
    )

    db_session.add_all([internal_doc, internal_chunk, public_doc, public_chunk])
    await db_session.commit()

    # Link KB to assistant
    link = AssistantKnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        assistant_id=asst.id,
        knowledge_base_id=kb.id,
    )
    db_session.add(link)
    await db_session.commit()

    # Publish assistant
    pub_payload = {
        "visibility": "PUBLIC",
        "allowed_domains": ["*"],
    }
    resp = await client.post(f"/api/v1/assistants/{asst.id}/publish", json=pub_payload, headers=headers)
    assert resp.status_code == 200
    public_id = resp.json()["public_id"]

    # Public visitor queries for the secret
    chat_resp = await client.post(
        f"/api/v1/public/assistants/{public_id}/chat",
        json={"message": "What is the executive confidential salary?"},
    )
    assert chat_resp.status_code == 200
    stream_content = chat_resp.text
    # Ensure internal secret text is NOT present in returned stream
    assert "EXECUTIVE_CONFIDENTIAL_SALARY_FIGURE_999999" not in stream_content


@pytest.mark.asyncio
async def test_developer_api_key_lifecycle(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Test developer API key generation, hashing, listing, and revocation."""
    tenant_a = seed_data["tenant_a"]
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }
    await _create_test_assistant(db_session, tenant_a.id, "Dev Assistant")

    # 1. Create API key
    key_payload = {
        "name": "Integration-Key-1",
        "scopes": ["assistant:read", "assistant:chat"],
        "expires_days": 30,
    }
    create_resp = await client.post("/api/v1/developer/api-keys", json=key_payload, headers=headers)
    assert create_resp.status_code == 201
    key_data = create_resp.json()
    assert "raw_key" in key_data
    raw_key = key_data["raw_key"]
    key_id = key_data["id"]

    assert raw_key.startswith("mmaip_live_")
    assert key_data["key_prefix"] == "mmaip_live_"
    assert key_data["name"] == "Integration-Key-1"
    assert "assistant:chat" in key_data["scopes"]

    # 2. Verify hash stored in database matches sha256(raw_key)
    expected_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    from sqlalchemy import select
    key_row = (await db_session.execute(select(APIKey).where(APIKey.id == uuid.UUID(key_id)))).scalar_one()
    assert key_row.key_hash == expected_hash

    # 3. List API keys (raw_key must NEVER be returned again)
    list_resp = await client.get("/api/v1/developer/api-keys", headers=headers)
    assert list_resp.status_code == 200
    keys_list = list_resp.json()
    matching = [k for k in keys_list if k["id"] == key_id]
    assert len(matching) == 1
    assert "raw_key" not in matching[0]

    # 4. Use raw key to authenticate against developer endpoint
    dev_headers = {"Authorization": f"Bearer {raw_key}"}
    dev_resp = await client.get("/api/v1/developer/assistants", headers=dev_headers)
    assert dev_resp.status_code == 200
    assert len(dev_resp.json()) >= 1

    # 5. Revoke key
    del_resp = await client.delete(f"/api/v1/developer/api-keys/{key_id}", headers=headers)
    assert del_resp.status_code == 200

    # 6. Verify revoked key fails authentication immediately
    revoked_dev_resp = await client.get("/api/v1/developer/assistants", headers=dev_headers)
    assert revoked_dev_resp.status_code == 401


@pytest.mark.asyncio
async def test_developer_api_scope_enforcement(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Verify that API keys lacking required scopes are rejected with HTTP 403."""
    tenant_a = seed_data["tenant_a"]
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }
    asst = await _create_test_assistant(db_session, tenant_a.id, "Scoped Assistant")

    # Create read-only API key (lacks 'assistant:chat')
    key_payload = {
        "name": "ReadOnly-Key",
        "scopes": ["assistant:read"],
    }
    create_resp = await client.post("/api/v1/developer/api-keys", json=key_payload, headers=headers)
    assert create_resp.status_code == 201
    raw_key = create_resp.json()["raw_key"]

    dev_headers = {"Authorization": f"Bearer {raw_key}"}

    # Reading assistants succeeds
    read_resp = await client.get("/api/v1/developer/assistants", headers=dev_headers)
    assert read_resp.status_code == 200

    # Chat execution is rejected with HTTP 403 Forbidden
    chat_resp = await client.post(
        f"/api/v1/developer/assistants/{asst.id}/chat",
        json={"message": "Hello via read-only key"},
        headers=dev_headers,
    )
    assert chat_resp.status_code == 403
    assert "lacks required permission scope" in chat_resp.json()["detail"]


@pytest.mark.asyncio
async def test_developer_api_cross_tenant_isolation(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Verify that Tenant A's API key cannot access Tenant B's assistant."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]

    asst_b = await _create_test_assistant(db_session, tenant_b.id, "Tenant B Assistant")

    # Tenant A creates an API key
    key_payload = {
        "name": "Tenant-A-Key",
        "scopes": ["assistant:read", "assistant:chat"],
    }
    create_resp = await client.post(
        "/api/v1/developer/api-keys",
        json=key_payload,
        headers={"Authorization": f"Bearer {seed_data['token_a_owner']}", "X-Tenant-ID": str(tenant_a.id)},
    )
    assert create_resp.status_code == 201
    raw_key_a = create_resp.json()["raw_key"]

    # Attempt to chat with Tenant B's assistant using Tenant A's key
    dev_headers = {"Authorization": f"Bearer {raw_key_a}"}

    cross_resp = await client.post(
        f"/api/v1/developer/assistants/{asst_b.id}/chat",
        json={"message": "Cross-tenant intrusion attempt"},
        headers=dev_headers,
    )
    assert cross_resp.status_code == 404
    assert "not found in authorized organization" in cross_resp.json()["detail"]


@pytest.mark.asyncio
async def test_embed_config_and_script_loader(client: AsyncClient, seed_data: dict, db_session: AsyncSession):
    """Verify public embed config endpoint and javascript loader."""
    tenant_a = seed_data["tenant_a"]
    asst = await _create_test_assistant(db_session, tenant_a.id, "Embed Assistant")
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # Publish
    pub_payload = {
        "visibility": "PUBLIC",
        "allowed_domains": ["*"],
        "custom_greeting": "Howdy! Need assistance?",
        "brand_color": "#10b981",
    }
    resp = await client.post(f"/api/v1/assistants/{asst.id}/publish", json=pub_payload, headers=headers)
    public_id = resp.json()["public_id"]

    # Fetch embed config
    cfg_resp = await client.get(f"/api/v1/public/embed/{public_id}/config")
    assert cfg_resp.status_code == 200
    cfg = cfg_resp.json()
    assert cfg["public_id"] == public_id
    assert cfg["brand_color"] == "#10b981"
    assert cfg["custom_greeting"] == "Howdy! Need assistance?"

    # Fetch embed.js
    script_resp = await client.get("/api/v1/public/embed.js")
    assert script_resp.status_code == 200
    assert "application/javascript" in script_resp.headers["content-type"]
    assert "mmaip-widget-container" in script_resp.text
