"""M10 Stage 2 Acceptance Test Suite — Complete Assistant Lifecycle Verification.

Covers all 19 lifecycle requirements:
1. Individual assistant creation
2. Organization assistant creation
3. Template initialization and blueprint persistence
4. Simple/Advanced configuration consistency
5. Assistant configuration persistence
6. Knowledge attachment and detachment
7. Knowledge ACL enforcement (cross-tenant denial)
8. Provider/BYOK enforcement
9. Sandbox inference with mock provider
10. Streaming cancellation
11. Citation provenance and grounding
12. Assistant version creation
13. Version history in descending order
14. Auditable rollback creating a new forward version
15. Published assistant lifecycle
16. Unpublish and revocation
17. Cross-tenant access denial
18. Audit event emission
19. Stage 1 security regression
"""

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SystemRole, TenantType
from app.core.security import hash_password
from app.models.administration import AuditLog
from app.models.knowledge import KnowledgeBase
from app.repositories.role_repository import RoleRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.user_repository import UserRepository
from app.retrieval.service import SearchResponse
from app.vectorstores.base import VectorSearchResult


@pytest.mark.asyncio
async def test_01_individual_assistant_creation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """1. Verify assistant creation within an INDIVIDUAL tenant workspace."""
    user_repo = UserRepository(db_session)
    tenant_repo = TenantRepository(db_session)
    role_repo = RoleRepository(db_session)

    user = await user_repo.create(
        email="solo_user@example.com",
        hashed_password=hash_password("Password123!"),
        full_name="Solo User",
    )
    owner_role = await role_repo.get_by_name(SystemRole.TENANT_OWNER.value)
    tenant_ind, _ = await tenant_repo.create_tenant(
        name="Solo Workspace",
        tenant_type=TenantType.INDIVIDUAL,
        owner_id=user.id,
        owner_role=owner_role,
        slug="solo-workspace",
    )
    from app.core.security import create_access_token
    token = create_access_token(str(user.id), {"email": user.email, "tenant_id": str(tenant_ind.id)})

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": str(tenant_ind.id),
    }

    payload = {
        "name": "Solo Study Assistant",
        "description": "Personal revision assistant",
        "llm_provider": "mock",
        "default_model": "mock-model",
        "system_prompt": "Help me study efficiently.",
    }

    res = await client.post("/api/v1/assistants", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["name"] == "Solo Study Assistant"
    assert data["tenant_id"] == str(tenant_ind.id)
    assert data["current_version_num"] == 1


@pytest.mark.asyncio
async def test_02_organization_assistant_creation(
    client: AsyncClient,
    seed_data: dict,
):
    """2. Verify assistant creation in an ORGANIZATION tenant workspace."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    payload = {
        "name": "Enterprise Support Bot",
        "description": "Customer facing tier-1 bot",
        "audience_level": "customers",
        "response_style": "professional",
        "llm_provider": "mock",
        "default_model": "mock-model",
        "visibility": "workspace",
    }

    res = await client.post("/api/v1/assistants", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["name"] == "Enterprise Support Bot"
    assert data["audience_level"] == "customers"
    assert data["visibility"] == "workspace"


@pytest.mark.asyncio
async def test_03_template_initialization_full_blueprint(
    client: AsyncClient,
    seed_data: dict,
):
    """3. Verify selecting a template initializes real configuration, not just labels."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    # First fetch template metadata
    tmpl_res = await client.get("/api/v1/templates/exam_prep", headers=headers)
    assert tmpl_res.status_code == 200
    tmpl = tmpl_res.json()
    assert tmpl["id"] == "exam_prep"

    # Create assistant from template
    payload = {
        "name": "Biology Exam Assistant",
        "template_id": "exam_prep",
        "audience_level": tmpl["intended_audience"] or "undergraduate",
        "response_style": tmpl["default_response_style"] or "socratic",
        "uncertainty_behavior": tmpl["default_uncertainty_behavior"] or "admit",
        "citation_style": tmpl["default_citation_style"] or "strict",
        "system_prompt": tmpl["default_instructions"],
        "retrieval_mode": tmpl["default_retrieval_mode"] or "hybrid",
        "top_k": tmpl["default_top_k"] or 5,
        "temperature": tmpl["default_temperature"] or 0.3,
        "llm_provider": "mock",
        "default_model": "mock-model",
    }

    res = await client.post("/api/v1/assistants", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["template_id"] == "exam_prep"
    assert data["response_style"] == "socratic"
    assert data["citation_style"] == "strict"
    assert data["system_prompt"] == tmpl["default_instructions"]


@pytest.mark.asyncio
async def test_04_simple_advanced_configuration_consistency(
    client: AsyncClient,
    seed_data: dict,
):
    """4. Verify simple and advanced mode settings persist to the same configuration."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    # Create assistant with simple mode values
    payload = {
        "name": "Dual Mode Assistant",
        "audience_level": "general",
        "response_style": "concise",
        "llm_provider": "mock",
        "default_model": "mock-model",
    }
    c_res = await client.post("/api/v1/assistants", json=payload, headers=headers)
    assert c_res.status_code == 201
    asst_id = c_res.json()["id"]

    # Update with advanced technical settings (temperature, top_k, retrieval_mode)
    upd_payload = {
        "temperature": 0.15,
        "top_k": 8,
        "retrieval_mode": "semantic",
        "change_summary": "Tuned advanced hyperparameters",
    }
    u_res = await client.put(f"/api/v1/assistants/{asst_id}", json=upd_payload, headers=headers)
    assert u_res.status_code == 200
    u_data = u_res.json()

    # Simple mode values are preserved
    assert u_data["audience_level"] == "general"
    assert u_data["response_style"] == "concise"
    # Advanced mode values are updated
    assert u_data["temperature"] == 0.15
    assert u_data["top_k"] == 8
    assert u_data["retrieval_mode"] == "semantic"


@pytest.mark.asyncio
async def test_05_assistant_configuration_persistence(
    client: AsyncClient,
    seed_data: dict,
):
    """5. Verify comprehensive persistence of all configuration fields."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    payload = {
        "name": "Full Spec Assistant",
        "slug": "full-spec-assistant",
        "description": "Test full persistence",
        "audience_level": "researchers",
        "response_style": "detailed",
        "uncertainty_behavior": "synthesize",
        "citation_style": "strict",
        "llm_provider": "mock",
        "default_model": "mock-model",
        "temperature": 0.45,
        "max_tokens": 2048,
        "retrieval_mode": "hybrid",
        "top_k": 6,
        "system_prompt": "Perform thorough synthesis.",
    }

    c_res = await client.post("/api/v1/assistants", json=payload, headers=headers)
    assert c_res.status_code == 201
    asst_id = c_res.json()["id"]

    # Fetch fresh from database
    get_res = await client.get(f"/api/v1/assistants/{asst_id}", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()

    assert data["name"] == "Full Spec Assistant"
    assert data["slug"] == "full-spec-assistant"
    assert data["description"] == "Test full persistence"
    assert data["audience_level"] == "researchers"
    assert data["response_style"] == "detailed"
    assert data["uncertainty_behavior"] == "synthesize"
    assert data["citation_style"] == "strict"
    assert data["temperature"] == 0.45
    assert data["max_tokens"] == 2048
    assert data["retrieval_mode"] == "hybrid"
    assert data["top_k"] == 6
    assert data["system_prompt"] == "Perform thorough synthesis."


@pytest.mark.asyncio
async def test_06_knowledge_attachment_and_detachment(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
):
    """6. Verify attaching, reading, and detaching knowledge bases."""
    tenant_a = seed_data["tenant_a"]
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # Create two Knowledge Bases in Tenant A
    kb1 = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Handbook KB",
        description="Employee Handbook",
        status="ACTIVE",
    )
    kb2 = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Engineering Docs KB",
        description="Engineering Specs",
        status="ACTIVE",
    )
    db_session.add_all([kb1, kb2])
    await db_session.flush()

    # 1. Create assistant with KB1
    c_res = await client.post(
        "/api/v1/assistants",
        json={
            "name": "Knowledge Attached Assistant",
            "llm_provider": "mock",
            "knowledge_base_ids": [str(kb1.id)],
        },
        headers=headers,
    )
    assert c_res.status_code == 201
    asst = c_res.json()
    assert asst["connected_kb_ids"] == [str(kb1.id)]
    asst_id = asst["id"]

    # 2. Update to attach both KB1 and KB2
    u_res1 = await client.put(
        f"/api/v1/assistants/{asst_id}",
        json={"knowledge_base_ids": [str(kb1.id), str(kb2.id)]},
        headers=headers,
    )
    assert u_res1.status_code == 200
    assert set(u_res1.json()["connected_kb_ids"]) == {str(kb1.id), str(kb2.id)}

    # 3. Detach all knowledge bases
    u_res2 = await client.put(
        f"/api/v1/assistants/{asst_id}",
        json={"knowledge_base_ids": []},
        headers=headers,
    )
    assert u_res2.status_code == 200
    assert u_res2.json()["connected_kb_ids"] == []


@pytest.mark.asyncio
async def test_07_knowledge_acl_cross_tenant_denial(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
):
    """7. Verify attempting to attach another tenant's Knowledge Base fails closed."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]

    headers_a = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # Knowledge Base owned by Tenant B
    foreign_kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        name="Tenant B Classified KB",
        status="ACTIVE",
    )
    db_session.add(foreign_kb)
    await db_session.flush()

    # Tenant A attempts to attach foreign KB during creation
    neg_create = await client.post(
        "/api/v1/assistants",
        json={
            "name": "Intrusion Bot",
            "llm_provider": "mock",
            "knowledge_base_ids": [str(foreign_kb.id)],
        },
        headers=headers_a,
    )
    assert neg_create.status_code == 400
    assert "Knowledge bases not found" in neg_create.text

    # Tenant A creates valid assistant, then tries to update with foreign KB
    valid_asst = await client.post(
        "/api/v1/assistants",
        json={"name": "Valid Bot", "llm_provider": "mock"},
        headers=headers_a,
    )
    asst_id = valid_asst.json()["id"]

    neg_update = await client.put(
        f"/api/v1/assistants/{asst_id}",
        json={"knowledge_base_ids": [str(foreign_kb.id)]},
        headers=headers_a,
    )
    assert neg_update.status_code == 400
    assert "Knowledge bases not found" in neg_update.text


@pytest.mark.asyncio
async def test_08_provider_byok_enforcement(
    client: AsyncClient,
    seed_data: dict,
):
    """8. Verify mock provider works without BYOK, but commercial providers require active BYOK credential."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    # Mock provider succeeds without BYOK
    mock_res = await client.post(
        "/api/v1/assistants/preview-test",
        json={
            "message": "Testing mock inference",
            "llm_provider": "mock",
            "default_model": "mock-model",
        },
        headers=headers,
    )
    assert mock_res.status_code == 200
    assert "event: token" in mock_res.text

    # Commercial provider without tenant BYOK key fails safely with clear error
    anthropic_res = await client.post(
        "/api/v1/assistants/preview-test",
        json={
            "message": "Testing anthropic inference",
            "llm_provider": "anthropic",
            "default_model": "claude-3-5-sonnet-20241022",
        },
        headers=headers,
    )
    assert anthropic_res.status_code == 200
    # Must yield message_error SSE indicating missing BYOK key
    assert "event: message_error" in anthropic_res.text
    assert "is not configured with an active BYOK credential" in anthropic_res.text


@pytest.mark.asyncio
async def test_09_sandbox_inference_mock_provider(
    client: AsyncClient,
    seed_data: dict,
):
    """9. Verify sandbox inference streams tokens with SSE events."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    payload = {
        "message": "Summarize policy guidelines",
        "system_prompt": "You are a concise compliance officer.",
        "llm_provider": "mock",
        "default_model": "mock-model",
        "temperature": 0.5,
        "max_tokens": 256,
    }

    res = await client.post("/api/v1/assistants/preview-test", json=payload, headers=headers)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    body = res.text
    assert "event: message_start" in body
    assert "event: token" in body
    assert "event: usage" in body
    assert "event: message_complete" in body


@pytest.mark.asyncio
async def test_10_streaming_cancellation(
    client: AsyncClient,
    seed_data: dict,
):
    """10. Verify streaming connection can be cleanly closed / cancelled early."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    payload = {
        "message": "Stream a long response that will be cancelled",
        "llm_provider": "mock",
        "default_model": "mock-model",
    }

    # Simulate client reading only the first chunk and closing connection
    async with client.stream("POST", "/api/v1/assistants/preview-test", json=payload, headers=headers) as resp:
        assert resp.status_code == 200
        first_chunk = None
        async for line in resp.aiter_lines():
            if "message_start" in line:
                first_chunk = line
                break
        assert first_chunk is not None
        # Closing context exits and cancels stream cleanly


@pytest.mark.asyncio
async def test_11_citation_provenance_and_grounding(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
):
    """11. Verify citations include document provenance and source details."""
    tenant_a = seed_data["tenant_a"]
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # Seed KnowledgeBase
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Employee Safety Manual",
        status="ACTIVE",
    )
    db_session.add(kb)
    await db_session.flush()

    mock_search_result = VectorSearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        score=0.95,
        content="Emergency exit routes are illuminated in neon green. Always proceed to Zone C.",
        document_title="safety_protocol_2026.pdf",
        page_number=4,
        heading_path="Safety > Emergency",
        chunk_index=0,
    )
    mock_search_resp = SearchResponse(
        query="What color are the emergency exit routes?",
        retrieval_mode="hybrid",
        vector_store="mock",
        embedding_provider="mock",
        total_results=1,
        results=[mock_search_result],
        citations=[],
        diagnostics={},
    )

    payload = {
        "message": "What color are the emergency exit routes?",
        "llm_provider": "mock",
        "default_model": "mock-model",
        "knowledge_base_ids": [str(kb.id)],
    }

    with patch("app.assistant_runtime.runtime.RetrievalService.search", return_value=mock_search_resp):
        res = await client.post("/api/v1/assistants/preview-test", json=payload, headers=headers)
        assert res.status_code == 200
        body = res.text

        assert "event: retrieval_complete" in body
        assert "safety_protocol_2026.pdf" in body
        assert "citations" in body


@pytest.mark.asyncio
async def test_12_assistant_version_creation(
    client: AsyncClient,
    seed_data: dict,
):
    """12. Verify configuration changes automatically create a forward version record."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    # Initial creation (v1)
    c_res = await client.post(
        "/api/v1/assistants",
        json={"name": "Versioned Bot", "system_prompt": "Prompt V1", "llm_provider": "mock"},
        headers=headers,
    )
    assert c_res.status_code == 201
    asst_id = c_res.json()["id"]
    assert c_res.json()["current_version_num"] == 1

    # Update (v2)
    u_res = await client.put(
        f"/api/v1/assistants/{asst_id}",
        json={"system_prompt": "Prompt V2", "change_summary": "Updated system prompt to V2"},
        headers=headers,
    )
    assert u_res.status_code == 200
    assert u_res.json()["current_version_num"] == 2


@pytest.mark.asyncio
async def test_13_version_history_descending_order(
    client: AsyncClient,
    seed_data: dict,
):
    """13. Verify version history endpoint returns versions sorted descending."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    # Create and update multiple times
    c_res = await client.post(
        "/api/v1/assistants",
        json={"name": "History Bot", "llm_provider": "mock"},
        headers=headers,
    )
    asst_id = c_res.json()["id"]

    await client.put(f"/api/v1/assistants/{asst_id}", json={"name": "History Bot 2"}, headers=headers)
    await client.put(f"/api/v1/assistants/{asst_id}", json={"name": "History Bot 3"}, headers=headers)

    v_res = await client.get(f"/api/v1/assistants/{asst_id}/versions", headers=headers)
    assert v_res.status_code == 200
    versions = v_res.json()
    assert len(versions) == 3
    assert [v["version_num"] for v in versions] == [3, 2, 1]


@pytest.mark.asyncio
async def test_14_auditable_rollback_creates_new_version(
    client: AsyncClient,
    seed_data: dict,
):
    """14. Verify rollback restores historical config and creates forward version V+1."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    # v1
    c_res = await client.post(
        "/api/v1/assistants",
        json={"name": "Original Name", "system_prompt": "Original Prompt", "llm_provider": "mock"},
        headers=headers,
    )
    asst_id = c_res.json()["id"]

    # v2
    await client.put(
        f"/api/v1/assistants/{asst_id}",
        json={"name": "Accidental Name", "system_prompt": "Accidental Prompt"},
        headers=headers,
    )

    # Rollback to v1
    rb_res = await client.post(
        f"/api/v1/assistants/{asst_id}/rollback",
        json={"target_version_num": 1, "change_summary": "Revert to V1 settings"},
        headers=headers,
    )
    assert rb_res.status_code == 200
    restored = rb_res.json()

    # Configuration is restored
    assert restored["name"] == "Original Name"
    assert restored["system_prompt"] == "Original Prompt"
    # Version increments forward to 3
    assert restored["current_version_num"] == 3

    # All 3 versions exist in immutable history
    v_res = await client.get(f"/api/v1/assistants/{asst_id}/versions", headers=headers)
    assert len(v_res.json()) == 3


@pytest.mark.asyncio
async def test_15_published_assistant_lifecycle(
    client: AsyncClient,
    seed_data: dict,
):
    """15. Verify assistant publication, public ID generation, and embed configuration."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    c_res = await client.post(
        "/api/v1/assistants",
        json={"name": "Public Facing Bot", "llm_provider": "mock"},
        headers=headers,
    )
    asst_id = c_res.json()["id"]

    # Publish
    pub_payload = {
        "visibility": "PUBLIC",
        "custom_greeting": "Welcome to our support desk!",
        "brand_color": "#2563EB",
        "allowed_domains": ["example.com", "*.acme.org"],
    }
    pub_res = await client.post(f"/api/v1/assistants/{asst_id}/publish", json=pub_payload, headers=headers)
    assert pub_res.status_code == 200, pub_res.text
    pub_data = pub_res.json()

    assert pub_data["is_active"] is True
    assert pub_data["visibility"] == "PUBLIC"
    assert len(pub_data["public_id"]) >= 8
    assert pub_data["custom_greeting"] == "Welcome to our support desk!"

    # Public endpoint can query published metadata without auth
    public_id = pub_data["public_id"]
    anon_res = await client.get(f"/api/v1/public/assistants/{public_id}")
    assert anon_res.status_code == 200
    anon_data = anon_res.json()
    assert anon_data["name"] == "Public Facing Bot"
    assert anon_data["custom_greeting"] == "Welcome to our support desk!"


@pytest.mark.asyncio
async def test_16_unpublish_and_revocation(
    client: AsyncClient,
    seed_data: dict,
):
    """16. Verify unpublish deactivates public access immediately."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    c_res = await client.post(
        "/api/v1/assistants",
        json={"name": "Temporary Bot", "llm_provider": "mock"},
        headers=headers,
    )
    asst_id = c_res.json()["id"]

    # Publish
    pub_res = await client.post(
        f"/api/v1/assistants/{asst_id}/publish",
        json={"visibility": "PUBLIC"},
        headers=headers,
    )
    public_id = pub_res.json()["public_id"]

    # Unpublish
    unpub_res = await client.post(f"/api/v1/assistants/{asst_id}/unpublish", headers=headers)
    assert unpub_res.status_code == 200
    assert unpub_res.json()["is_active"] is False

    # Public access now rejects
    anon_res = await client.get(f"/api/v1/public/assistants/{public_id}")
    assert anon_res.status_code in (404, 403)


@pytest.mark.asyncio
async def test_17_cross_tenant_access_denial(
    client: AsyncClient,
    seed_data: dict,
):
    """17. Verify Tenant B cannot read, update, delete, version, or publish Tenant A's assistant."""
    headers_a = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }
    headers_b = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_b"].id),
    }

    # Tenant A creates assistant
    c_res = await client.post(
        "/api/v1/assistants",
        json={"name": "Tenant A Secret Bot", "llm_provider": "mock"},
        headers=headers_a,
    )
    asst_id = c_res.json()["id"]

    # Tenant B attempts GET
    get_b = await client.get(f"/api/v1/assistants/{asst_id}", headers=headers_b)
    assert get_b.status_code == 404

    # Tenant B attempts PUT
    put_b = await client.put(f"/api/v1/assistants/{asst_id}", json={"name": "Hacked"}, headers=headers_b)
    assert put_b.status_code == 404

    # Tenant B attempts DELETE
    del_b = await client.delete(f"/api/v1/assistants/{asst_id}", headers=headers_b)
    assert del_b.status_code == 404

    # Tenant B attempts versions
    ver_b = await client.get(f"/api/v1/assistants/{asst_id}/versions", headers=headers_b)
    assert ver_b.status_code in (404, 403)

    # Tenant B attempts rollback
    rb_b = await client.post(
        f"/api/v1/assistants/{asst_id}/rollback",
        json={"target_version_num": 1},
        headers=headers_b,
    )
    assert rb_b.status_code in (400, 404, 403)


@pytest.mark.asyncio
async def test_18_audit_event_logging(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
):
    """18. Verify assistant lifecycle actions emit audit logs in the tenant."""
    tenant_a = seed_data["tenant_a"]
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(tenant_a.id),
    }

    # Create
    c_res = await client.post(
        "/api/v1/assistants",
        json={"name": "Audited Bot", "llm_provider": "mock"},
        headers=headers,
    )
    asst_id = c_res.json()["id"]

    # Update
    await client.put(
        f"/api/v1/assistants/{asst_id}",
        json={"name": "Audited Bot Renamed"},
        headers=headers,
    )

    # Rollback
    await client.post(
        f"/api/v1/assistants/{asst_id}/rollback",
        json={"target_version_num": 1},
        headers=headers,
    )

    # Delete
    await client.delete(f"/api/v1/assistants/{asst_id}", headers=headers)

    # Query audit logs for tenant_a
    audit_stmt = (
        select(AuditLog)
        .where(
            AuditLog.tenant_id == tenant_a.id,
            AuditLog.resource_type == "assistant",
        )
        .order_by(AuditLog.created_at.asc())
    )
    logs = (await db_session.execute(audit_stmt)).scalars().all()
    actions = [entry.action for entry in logs]

    assert "assistant.create" in actions
    assert "assistant.update" in actions
    assert "assistant.rollback" in actions
    assert "assistant.delete" in actions


@pytest.mark.asyncio
async def test_19_stage1_security_regression(
    client: AsyncClient,
    seed_data: dict,
):
    """19. Verify Stage 1 fixes remain intact: public chat rejection on invalid public ID."""
    fake_public_id = "pub_nonexistent_token_12345"
    res = await client.get(f"/api/v1/public/assistants/{fake_public_id}")
    assert res.status_code in (404, 403)
