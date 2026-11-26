"""Comprehensive acceptance test suite for M06: Assistant Studio, Templates & Versioning."""

import pytest
from httpx import AsyncClient

from app.templates.registry import get_template_registry


@pytest.mark.asyncio
async def test_template_registry_data_driven_initial_collection():
    """Verify all 12 initial templates exist with required schemas, categories, and parameters."""
    registry = get_template_registry()
    templates = registry.get_all()

    assert len(templates) == 12, f"Expected 12 templates, got {len(templates)}"

    expected_ids = {
        "exam_prep",
        "subject_tutor",
        "mcq_generator",
        "notes_textbook",
        "hr_handbook",
        "company_knowledge",
        "customer_support",
        "sop_operations",
        "personal_vault",
        "research_assistant",
        "sports_coach",
        "custom_domain",
    }
    actual_ids = {t.id for t in templates}
    assert expected_ids == actual_ids

    # Verify categories
    categories = registry.get_categories()
    assert set(categories) == {"Education", "Business", "Personal", "Domain"}

    for t in templates:
        assert len(t.name) > 3
        assert len(t.description) > 10
        assert len(t.default_instructions) > 20
        assert t.requires_knowledge is False, "Knowledge must be optional for all templates"
        assert len(t.suggested_starter_questions) >= 2


@pytest.mark.asyncio
async def test_templates_api_endpoints(
    client: AsyncClient,
    seed_data: dict,
):
    """Verify GET /api/v1/templates and GET /api/v1/templates/{id}."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    resp = await client.get("/api/v1/templates", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 12
    assert len(data["templates"]) == 12
    assert len(data["categories"]) == 4

    # Get single template
    resp_single = await client.get("/api/v1/templates/exam_prep", headers=headers)
    assert resp_single.status_code == 200
    t_data = resp_single.json()
    assert t_data["id"] == "exam_prep"
    assert t_data["category"] == "Education"
    assert t_data["default_response_style"] == "socratic"

    # Non-existent template
    resp_404 = await client.get("/api/v1/templates/non_existent_123", headers=headers)
    assert resp_404.status_code == 404


@pytest.mark.asyncio
async def test_assistant_creation_from_template_with_optional_knowledge(
    client: AsyncClient,
    seed_data: dict,
):
    """Verify creating an assistant from a template with zero knowledge bases attached."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    payload = {
        "name": "Biology Exam Buddy",
        "template_id": "exam_prep",
        "audience_level": "undergraduate",
        "response_style": "socratic",
        "uncertainty_behavior": "admit",
        "citation_style": "strict",
        "llm_provider": "mock",
        "default_model": "mock-model",
        "temperature": 0.3,
        "max_tokens": 512,
        "retrieval_mode": "hybrid",
        "top_k": 5,
        "system_prompt": "You are a specialized molecular genetics tutor.",
        "knowledge_base_ids": [],  # Knowledge is optional!
    }

    resp = await client.post("/api/v1/assistants", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    created = resp.json()

    assert created["name"] == "Biology Exam Buddy"
    assert created["template_id"] == "exam_prep"
    assert created["audience_level"] == "undergraduate"
    assert created["response_style"] == "socratic"
    assert created["current_version_num"] == 1
    assert created["connected_kb_ids"] == []

    assistant_id = created["id"]

    # Verify Version 1 snapshot was automatically created
    v_resp = await client.get(f"/api/v1/assistants/{assistant_id}/versions", headers=headers)
    assert v_resp.status_code == 200
    versions = v_resp.json()
    assert len(versions) == 1
    v1 = versions[0]
    assert v1["version_num"] == 1
    assert v1["config_snapshot"]["template_id"] == "exam_prep"
    assert v1["config_snapshot"]["audience_level"] == "undergraduate"
    assert v1["config_snapshot"]["knowledge_base_ids"] == []


@pytest.mark.asyncio
async def test_assistant_configuration_update_creates_version_snapshot(
    client: AsyncClient,
    seed_data: dict,
):
    """Verify that updating configuration settings increments version_num and preserves snapshot."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    # 1. Create assistant
    create_payload = {
        "name": "HR Policy Assistant",
        "template_id": "hr_handbook",
        "llm_provider": "mock",
        "default_model": "mock-model",
        "system_prompt": "Initial HR guidelines.",
    }
    c_resp = await client.post("/api/v1/assistants", json=create_payload, headers=headers)
    assert c_resp.status_code == 201
    assistant_id = c_resp.json()["id"]

    # 2. Update configuration
    update_payload = {
        "name": "Acme People & Culture Guide",
        "system_prompt": "Updated HR guidelines with parental leave additions.",
        "temperature": 0.2,
        "response_style": "professional",
        "change_summary": "Added parental leave guidance and tuned temperature.",
    }
    u_resp = await client.put(f"/api/v1/assistants/{assistant_id}", json=update_payload, headers=headers)
    assert u_resp.status_code == 200
    updated = u_resp.json()
    assert updated["name"] == "Acme People & Culture Guide"
    assert updated["current_version_num"] == 2

    # 3. Verify version history has 2 versions
    v_resp = await client.get(f"/api/v1/assistants/{assistant_id}/versions", headers=headers)
    assert v_resp.status_code == 200
    versions = v_resp.json()
    assert len(versions) == 2

    # Versions are ordered descending (v2 first, v1 second)
    assert versions[0]["version_num"] == 2
    assert versions[0]["change_summary"] == "Added parental leave guidance and tuned temperature."
    assert versions[0]["config_snapshot"]["name"] == "Acme People & Culture Guide"

    assert versions[1]["version_num"] == 1
    assert versions[1]["config_snapshot"]["name"] == "HR Policy Assistant"


@pytest.mark.asyncio
async def test_auditable_configuration_rollback(
    client: AsyncClient,
    seed_data: dict,
):
    """Verify that rollback restores target snapshot, creates a new forward version, and preserves past records."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    # 1. Create assistant (v1)
    c_resp = await client.post(
        "/api/v1/assistants",
        json={"name": "Assistant V1", "system_prompt": "Prompt V1", "llm_provider": "mock"},
        headers=headers,
    )
    assistant_id = c_resp.json()["id"]

    # 2. Update to v2
    await client.put(
        f"/api/v1/assistants/{assistant_id}",
        json={"name": "Assistant V2", "system_prompt": "Prompt V2"},
        headers=headers,
    )

    # 3. Rollback to v1
    rb_payload = {
        "target_version_num": 1,
        "change_summary": "Reverting accidental changes back to version 1",
    }
    rb_resp = await client.post(
        f"/api/v1/assistants/{assistant_id}/rollback",
        json=rb_payload,
        headers=headers,
    )
    assert rb_resp.status_code == 200
    restored = rb_resp.json()

    # Crucial acceptance criteria:
    # 1. Configuration is restored to V1
    assert restored["name"] == "Assistant V1"
    assert restored["system_prompt"] == "Prompt V1"
    # 2. Version number is incremented to 3 (NOT rolled back to 1 destructively!)
    assert restored["current_version_num"] == 3

    # 3. All 3 versions exist in history
    v_resp = await client.get(f"/api/v1/assistants/{assistant_id}/versions", headers=headers)
    versions = v_resp.json()
    assert len(versions) == 3
    version_numbers = [v["version_num"] for v in versions]
    assert version_numbers == [3, 2, 1]


@pytest.mark.asyncio
async def test_cross_tenant_isolation_on_versions_and_rollback(
    client: AsyncClient,
    seed_data: dict,
):
    """Verify that Tenant B cannot access, view, or rollback Tenant A's assistant versions."""
    headers_a = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }
    headers_b = {
        "Authorization": f"Bearer {seed_data['token_b_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_b"].id),
    }

    # Tenant A creates an assistant
    c_resp = await client.post(
        "/api/v1/assistants",
        json={"name": "Tenant A Secret Bot", "llm_provider": "mock"},
        headers=headers_a,
    )
    assert c_resp.status_code == 201
    assistant_id = c_resp.json()["id"]

    # Tenant B attempts to read Tenant A's versions
    neg_v_resp = await client.get(
        f"/api/v1/assistants/{assistant_id}/versions",
        headers=headers_b,
    )
    assert neg_v_resp.status_code in (404, 403)

    # Tenant B attempts to rollback Tenant A's assistant
    neg_rb_resp = await client.post(
        f"/api/v1/assistants/{assistant_id}/rollback",
        json={"target_version_num": 1},
        headers=headers_b,
    )
    assert neg_rb_resp.status_code in (400, 404, 403)


@pytest.mark.asyncio
async def test_assistant_preview_test_streaming(
    client: AsyncClient,
    seed_data: dict,
):
    """Verify POST /api/v1/assistants/preview-test streams live test tokens for wizard step 5."""
    headers = {
        "Authorization": f"Bearer {seed_data['token_a_owner']}",
        "X-Tenant-ID": str(seed_data["tenant_a"].id),
    }

    payload = {
        "message": "Hello, testing preview stream!",
        "system_prompt": "You are a preview test coach.",
        "temperature": 0.5,
        "max_tokens": 128,
        "retrieval_mode": "hybrid",
        "top_k": 3,
        "knowledge_base_ids": [],
    }

    resp = await client.post(
        "/api/v1/assistants/preview-test",
        json=payload,
        headers=headers,
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    content = resp.text
    assert "event: message_start" in content
    assert "event: token" in content
    assert "event: message_complete" in content
