"""M11 Part 1 remediation: public metadata exposes only PUBLIC publications."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant

WHITELISTED_FIELDS = {
    "public_id",
    "name",
    "description",
    "custom_greeting",
    "brand_color",
    "avatar_url",
    "visibility",
    "citation_style",
}
FORBIDDEN_FIELDS = {"tenant_id", "assistant_id", "id", "system_prompt", "allowed_domains"}


async def _create_assistant(db: AsyncSession, tenant_id: uuid.UUID, name: str) -> Assistant:
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        slug=name.lower().replace(" ", "-") + "-" + uuid.uuid4().hex[:6],
        description="Metadata test assistant",
        system_prompt="SECRET_SYSTEM_PROMPT_MUST_NOT_LEAK",
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


async def _publish(client: AsyncClient, seed_data: dict, assistant_id: uuid.UUID, visibility: str):
    return await client.post(
        f"/api/v1/assistants/{assistant_id}/publish",
        headers={
            "Authorization": f"Bearer {seed_data['token_a_owner']}",
            "X-Tenant-ID": str(seed_data["tenant_a"].id),
        },
        json={"visibility": visibility, "allowed_domains": ["*"]},
    )


@pytest.mark.asyncio
async def test_public_active_metadata_is_whitelisted_only(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    asst = await _create_assistant(db_session, seed_data["tenant_a"].id, "Public Metadata Bot")
    pub_resp = await _publish(client, seed_data, asst.id, "PUBLIC")
    assert pub_resp.status_code == 200
    public_id = pub_resp.json()["public_id"]

    resp = await client.get(f"/api/v1/public/assistants/{public_id}")
    assert resp.status_code == 200
    meta = resp.json()
    assert set(meta.keys()) == WHITELISTED_FIELDS
    assert not (FORBIDDEN_FIELDS & set(meta.keys()))
    assert "SECRET_SYSTEM_PROMPT_MUST_NOT_LEAK" not in resp.text
    assert meta["public_id"] == public_id
    assert meta["name"] == "Public Metadata Bot"
    assert meta["visibility"] == "PUBLIC"


@pytest.mark.asyncio
async def test_workspace_visibility_is_not_public(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    asst = await _create_assistant(db_session, seed_data["tenant_a"].id, "Workspace Only Bot")
    pub_resp = await _publish(client, seed_data, asst.id, "WORKSPACE")
    assert pub_resp.status_code == 200
    public_id = pub_resp.json()["public_id"]

    resp = await client.get(f"/api/v1/public/assistants/{public_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_inactive_publication_is_not_public(
    client: AsyncClient, seed_data: dict, db_session: AsyncSession
):
    asst = await _create_assistant(db_session, seed_data["tenant_a"].id, "Revoked Bot")
    pub_resp = await _publish(client, seed_data, asst.id, "PUBLIC")
    assert pub_resp.status_code == 200
    public_id = pub_resp.json()["public_id"]

    unpub_resp = await client.post(
        f"/api/v1/assistants/{asst.id}/unpublish",
        headers={
            "Authorization": f"Bearer {seed_data['token_a_owner']}",
            "X-Tenant-ID": str(seed_data["tenant_a"].id),
        },
    )
    assert unpub_resp.status_code == 200

    resp = await client.get(f"/api/v1/public/assistants/{public_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unknown_public_id_returns_404(client: AsyncClient):
    resp = await client.get("/api/v1/public/assistants/pub_does_not_exist")
    assert resp.status_code == 404
