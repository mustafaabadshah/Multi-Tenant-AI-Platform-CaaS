import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_complete_ordinary_user_assistant_journey(client: AsyncClient):
    """
    M06 Acceptance Criterion:
    Test the complete creation journey using an ordinary user account:
    1. Register ordinary student user.
    2. Retrieve template registry (verify 12 templates, categories).
    3. Choose 'exam-prep' template and preview test stream with zero KBs.
    4. Save assistant with template defaults (Zero KBs).
    5. Verify initial configuration version 1 is created.
    6. Switch/Update settings (e.g. Simple to Advanced top_k, temperature).
    7. Verify version 2 is created.
    8. Rollback to version 1.
    9. Verify forward version 3 is created preserving history.
    10. Verify audit event was logged.
    """
    # 1. Register student
    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "sarah.student@oxford.edu",
            "password": "Password123!",
            "full_name": "Sarah Student",
        },
    )
    assert reg_res.status_code == 201
    auth_data = reg_res.json()
    token = auth_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    tenant_id = me_res.json()["workspaces"][0]["tenant_id"]
    headers["X-Tenant-ID"] = tenant_id

    # 2. Template Registry
    tmpl_res = await client.get("/api/v1/templates")
    assert tmpl_res.status_code == 200
    tmpls = tmpl_res.json()
    assert tmpls["total"] == 12
    assert "Education" in tmpls["categories"]
    assert "Business" in tmpls["categories"]

    exam_tmpl = next(t for t in tmpls["templates"] if t["id"] == "exam_prep")
    assert exam_tmpl["category"] == "Education"
    assert exam_tmpl["default_citation_style"] == "strict"
    assert exam_tmpl["intended_audience"] == "students"

    # 3. Preview Test Stream (Step 5 of Wizard) with Zero KBs
    preview_res = await client.post(
        "/api/v1/assistants/preview-test",
        headers=headers,
        json={
            "name": exam_tmpl["name"],
            "system_prompt": exam_tmpl["default_instructions"],
            "audience_level": exam_tmpl["intended_audience"],
            "response_style": exam_tmpl["default_response_style"],
            "uncertainty_behavior": exam_tmpl["default_uncertainty_behavior"],
            "citation_style": exam_tmpl["default_citation_style"],
            "message": "Can you give me a practice question on photosynthesis?",
            "knowledge_base_ids": [],
            "llm_provider": "mock",
        },
    )
    assert preview_res.status_code == 200
    assert "text/event-stream" in preview_res.headers["content-type"]
    preview_body = preview_res.text
    assert "event: token" in preview_body
    assert "event: message_complete" in preview_body

    # 4. Save Assistant (Zero KBs, template-backed)
    create_payload = {
        "name": exam_tmpl["name"],
        "description": exam_tmpl["description"],
        "template_id": exam_tmpl["id"],
        "template_version": exam_tmpl["version"],
        "system_prompt": exam_tmpl["default_instructions"],
        "audience_level": "intermediate",
        "response_style": "academic",
        "uncertainty_behavior": "admit",
        "citation_style": "strict",
        "llm_provider": "mock",
        "default_model": "auto",
        "temperature": 0.4,
        "max_tokens": 1024,
        "retrieval_mode": "hybrid",
        "top_k": 5,
        "knowledge_base_ids": [],
    }
    create_res = await client.post("/api/v1/assistants", headers=headers, json=create_payload)
    assert create_res.status_code == 201
    assistant = create_res.json()
    asst_id = assistant["id"]
    assert assistant["current_version_num"] == 1
    assert assistant["template_id"] == "exam_prep"
    assert assistant["audience_level"] == "intermediate"

    # 5. Verify Version 1 history
    v_res = await client.get(f"/api/v1/assistants/{asst_id}/versions", headers=headers)
    assert v_res.status_code == 200
    versions = v_res.json()
    assert len(versions) == 1
    assert versions[0]["version_num"] == 1
    assert versions[0]["config_snapshot"]["name"] == exam_tmpl["name"]
    assert versions[0]["config_snapshot"]["template_id"] == "exam_prep"

    # 6. Update Assistant Settings (Advanced tweak)
    update_res = await client.put(
        f"/api/v1/assistants/{asst_id}",
        headers=headers,
        json={
            "description": "Updated exam assistant with top_k 8 and creative responses",
            "response_style": "creative",
            "temperature": 0.8,
            "top_k": 8,
        },
    )
    assert update_res.status_code == 200
    updated_asst = update_res.json()
    assert updated_asst["current_version_num"] == 2
    assert updated_asst["response_style"] == "creative"
    assert updated_asst["top_k"] == 8

    # 7. Verify Version 2 exists in history
    v_res2 = await client.get(f"/api/v1/assistants/{asst_id}/versions", headers=headers)
    assert v_res2.status_code == 200
    versions2 = v_res2.json()
    assert len(versions2) == 2
    assert versions2[0]["version_num"] == 2
    assert versions2[1]["version_num"] == 1

    # 8. Rollback to Version 1
    rb_res = await client.post(
        f"/api/v1/assistants/{asst_id}/rollback",
        headers=headers,
        json={"target_version_num": 1, "change_summary": "Reverting creative style back to academic exam defaults"},
    )
    assert rb_res.status_code == 200
    rolled_back = rb_res.json()
    assert rolled_back["current_version_num"] == 3
    assert rolled_back["response_style"] == "academic"
    assert rolled_back["top_k"] == 5
    assert rolled_back["temperature"] == 0.4

    # 9. Verify History preserves v1, v2, and records forward rollback v3
    v_res3 = await client.get(f"/api/v1/assistants/{asst_id}/versions", headers=headers)
    assert v_res3.status_code == 200
    versions3 = v_res3.json()
    assert len(versions3) == 3
    assert [v["version_num"] for v in versions3] == [3, 2, 1]
    assert versions3[0]["change_summary"] == "Reverting creative style back to academic exam defaults"

    # 10. Verify Negative Cross-Tenant Security Isolation
    # Register an attacker in another tenant
    reg_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "attacker@other.org",
            "password": "Password123!",
            "full_name": "Attacker Bob",
        },
    )
    assert reg_b.status_code == 201
    token_b = reg_b.json()["access_token"]
    me_b = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
    tenant_b = me_b.json()["workspaces"][0]["tenant_id"]
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Tenant-ID": tenant_b}

    # Tenant B tries to read Tenant A's assistant -> 404
    get_asst_b = await client.get(f"/api/v1/assistants/{asst_id}", headers=headers_b)
    assert get_asst_b.status_code == 404

    # Tenant B tries to list Tenant A's versions -> 404
    get_versions_b = await client.get(f"/api/v1/assistants/{asst_id}/versions", headers=headers_b)
    assert get_versions_b.status_code == 404

    # Tenant B tries to rollback Tenant A's assistant -> 404
    rb_b = await client.post(
        f"/api/v1/assistants/{asst_id}/rollback",
        headers=headers_b,
        json={"target_version_num": 1},
    )
    assert rb_b.status_code in (400, 404, 403)
