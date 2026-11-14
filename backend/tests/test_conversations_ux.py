"""Acceptance and security tests for Stage 6: Conversation management and UX completion."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant


@pytest.fixture
async def asst_a(db_session: AsyncSession, seed_data: dict) -> Assistant:
    tenant_a = seed_data["tenant_a"]
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Campus Guidance Assistant",
        slug="campus-guidance",
        description="Assists students and teachers with academic regulations",
        llm_provider="mock",
        default_model="mock-gpt",
        status="ACTIVE",
    )
    db_session.add(asst)
    await db_session.commit()
    await db_session.refresh(asst)
    return asst


@pytest.mark.asyncio
async def test_conversation_rename_and_lifecycle(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
    asst_a: Assistant,
):
    """Test creating a conversation, renaming it via PATCH, and verifying changes."""
    tenant_a = seed_data["tenant_a"]
    token_a = seed_data["token_a_owner"]
    headers = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)}

    # 1. Create conversation
    create_res = await client.post(
        "/api/v1/conversations",
        headers=headers,
        json={"assistant_id": str(asst_a.id), "title": "Initial Chat Title"},
    )
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]
    assert create_res.json()["title"] == "Initial Chat Title"

    # 2. Rename conversation via PATCH
    patch_res = await client.patch(
        f"/api/v1/conversations/{conv_id}",
        headers=headers,
        json={"title": "Updated Academic Advising Session"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Updated Academic Advising Session"

    # 3. Verify get reflects updated title
    get_res = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Updated Academic Advising Session"

    # 4. Delete conversation
    del_res = await client.delete(f"/api/v1/conversations/{conv_id}", headers=headers)
    assert del_res.status_code == 204

    # 5. Verify deleted conversation does not appear in active list
    list_res = await client.get(
        f"/api/v1/conversations?assistant_id={asst_a.id}",
        headers=headers,
    )
    assert list_res.status_code == 200
    conv_ids = [c["id"] for c in list_res.json()]
    assert conv_id not in conv_ids


@pytest.mark.asyncio
async def test_cross_tenant_conversation_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: dict,
    asst_a: Assistant,
):
    """Test that Tenant B cannot access, rename, or delete Tenant A's conversation."""
    tenant_a = seed_data["tenant_a"]
    tenant_b = seed_data["tenant_b"]
    token_a = seed_data["token_a_owner"]
    token_b = seed_data["token_b_owner"]

    headers_a = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": str(tenant_a.id)}
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Tenant-ID": str(tenant_b.id)}

    # Create conversation in Tenant A
    create_res = await client.post(
        "/api/v1/conversations",
        headers=headers_a,
        json={"assistant_id": str(asst_a.id), "title": "Confidential Tenant A Conversation"},
    )
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    # Tenant B attempts to read Tenant A's conversation -> 404
    get_res = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers_b)
    assert get_res.status_code == 404

    # Tenant B attempts to rename Tenant A's conversation -> 404
    patch_res = await client.patch(
        f"/api/v1/conversations/{conv_id}",
        headers=headers_b,
        json={"title": "Hacked Title"},
    )
    assert patch_res.status_code == 404

    # Tenant B attempts to delete Tenant A's conversation -> 404
    del_res = await client.delete(f"/api/v1/conversations/{conv_id}", headers=headers_b)
    assert del_res.status_code == 404
