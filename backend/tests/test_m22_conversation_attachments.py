"""Tests for M22 Conversation Attachments, Chunk Extraction, and KB Promotion."""

import io
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SystemRole
from app.core.security import create_access_token
from app.models.assistant import Assistant
from app.models.conversation import Conversation, ConversationAttachment
from app.models.knowledge import KnowledgeBase
from app.models.membership import TenantMembership
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.services.conversation_attachment_service import ConversationAttachmentService


@pytest.fixture
async def setup_tenants_and_conversations(db_session: AsyncSession):
    # Tenant A
    tenant_a = Tenant(id=uuid.uuid4(), name="Tenant Alpha", slug=f"alpha-{uuid.uuid4().hex[:6]}")
    user_a = User(id=uuid.uuid4(), email=f"user_a_{uuid.uuid4().hex[:6]}@alpha.com", hashed_password="pw", full_name="User Alpha")
    db_session.add_all([tenant_a, user_a])
    await db_session.flush()

    admin_role = (await db_session.execute(select(Role).where(Role.name == SystemRole.TENANT_OWNER.value))).scalars().first()
    mem_a = TenantMembership(id=uuid.uuid4(), tenant_id=tenant_a.id, user_id=user_a.id, role_id=admin_role.id)
    db_session.add(mem_a)

    asst_a = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Alpha Assistant",
        slug=f"alpha-asst-{uuid.uuid4().hex[:6]}",
        system_prompt="You are a helpful assistant.",
        llm_provider="mock",
    )
    conv_a = Conversation(id=uuid.uuid4(), tenant_id=tenant_a.id, user_id=user_a.id, assistant_id=asst_a.id, title="Alpha Chat")
    conv_a2 = Conversation(id=uuid.uuid4(), tenant_id=tenant_a.id, user_id=user_a.id, assistant_id=asst_a.id, title="Alpha Chat 2")
    kb_a = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Alpha Core KB", status="ACTIVE")
    db_session.add_all([asst_a, conv_a, conv_a2, kb_a])

    # Tenant B
    tenant_b = Tenant(id=uuid.uuid4(), name="Tenant Beta", slug=f"beta-{uuid.uuid4().hex[:6]}")
    user_b = User(id=uuid.uuid4(), email=f"user_b_{uuid.uuid4().hex[:6]}@beta.com", hashed_password="pw", full_name="User Beta")
    db_session.add_all([tenant_b, user_b])
    await db_session.flush()

    mem_b = TenantMembership(id=uuid.uuid4(), tenant_id=tenant_b.id, user_id=user_b.id, role_id=admin_role.id)
    db_session.add(mem_b)

    asst_b = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        name="Beta Assistant",
        slug=f"beta-asst-{uuid.uuid4().hex[:6]}",
        system_prompt="Beta assistant.",
        llm_provider="mock",
    )
    conv_b = Conversation(id=uuid.uuid4(), tenant_id=tenant_b.id, user_id=user_b.id, assistant_id=asst_b.id, title="Beta Chat")
    db_session.add_all([asst_b, conv_b])

    await db_session.commit()

    token_a = create_access_token(str(user_a.id), {"email": user_a.email, "tenant_id": str(tenant_a.id)})
    token_b = create_access_token(str(user_b.id), {"email": user_b.email, "tenant_id": str(tenant_b.id)})

    return {
        "tenant_a": tenant_a,
        "user_a": user_a,
        "conv_a": conv_a,
        "conv_a2": conv_a2,
        "kb_a": kb_a,
        "token_a": token_a,
        "tenant_b": tenant_b,
        "user_b": user_b,
        "conv_b": conv_b,
        "token_b": token_b,
    }


@pytest.mark.asyncio
async def test_upload_attachment_and_chunk_extraction(client: AsyncClient, setup_tenants_and_conversations):
    data = setup_tenants_and_conversations
    headers = {"Authorization": f"Bearer {data['token_a']}", "X-Tenant-ID": str(data["tenant_a"].id)}

    doc_content = b"Financial Q3 Report: Revenue grew by 42 percent reaching 10 million dollars in net operating profits."
    files = {"file": ("q3_financial_report.txt", doc_content, "text/plain")}

    resp = await client.post(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["filename"] == "q3_financial_report.txt"
    assert body["status"] == "READY"
    assert body["total_chunks"] >= 1
    assert body["is_promoted"] is False
    attachment_id = body["id"]

    # Verify listing
    list_resp = await client.get(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments",
        headers=headers,
    )
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["id"] == attachment_id

    # Verify download
    down_resp = await client.get(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments/{attachment_id}/download",
        headers=headers,
    )
    assert down_resp.status_code == 200
    assert down_resp.content == doc_content


@pytest.mark.asyncio
async def test_cross_tenant_and_cross_conversation_attachment_isolation(client: AsyncClient, setup_tenants_and_conversations):
    data = setup_tenants_and_conversations
    headers_a = {"Authorization": f"Bearer {data['token_a']}", "X-Tenant-ID": str(data["tenant_a"].id)}
    headers_b = {"Authorization": f"Bearer {data['token_b']}", "X-Tenant-ID": str(data["tenant_b"].id)}

    # Upload attachment in Tenant A
    files = {"file": ("secret_plans.txt", b"Confidential strategy for Tenant Alpha only.", "text/plain")}
    resp = await client.post(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments",
        headers=headers_a,
        files=files,
    )
    assert resp.status_code == 201
    att_id = resp.json()["id"]

    # Tenant B tries to access Tenant A's attachment -> 404
    cross_resp = await client.get(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments/{att_id}",
        headers=headers_b,
    )
    assert cross_resp.status_code in (403, 404)

    # Tenant B tries to download Tenant A's attachment -> 404
    cross_down = await client.get(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments/{att_id}/download",
        headers=headers_b,
    )
    assert cross_down.status_code in (403, 404)

    # Even in Tenant A, another conversation cannot access this attachment ID directly
    cross_conv_resp = await client.get(
        f"/api/v1/conversations/{data['conv_a2'].id}/attachments/{att_id}",
        headers=headers_a,
    )
    assert cross_conv_resp.status_code == 404


@pytest.mark.asyncio
async def test_attachment_promotion_to_knowledge_base(client: AsyncClient, setup_tenants_and_conversations):
    data = setup_tenants_and_conversations
    headers = {"Authorization": f"Bearer {data['token_a']}", "X-Tenant-ID": str(data["tenant_a"].id)}

    # 1. Upload attachment
    files = {"file": ("onboarding_guide.txt", b"Step 1: Create your credentials. Step 2: Set your team permissions.", "text/plain")}
    resp = await client.post(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 201
    att_id = resp.json()["id"]

    # 2. Promote to KB
    promo_resp = await client.post(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments/{att_id}/promote",
        headers=headers,
        json={"knowledge_base_id": str(data["kb_a"].id)},
    )
    assert promo_resp.status_code == 200, promo_resp.text
    promo_data = promo_resp.json()
    assert promo_data["status"] == "PROMOTED"
    assert promo_data["document_id"] is not None

    # Verify attachment is marked promoted
    get_att = await client.get(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments/{att_id}",
        headers=headers,
    )
    assert get_att.json()["is_promoted"] is True
    assert get_att.json()["promoted_knowledge_base_id"] == str(data["kb_a"].id)


@pytest.mark.asyncio
async def test_chat_scoped_attachment_search_relevance(db_session: AsyncSession, setup_tenants_and_conversations):
    data = setup_tenants_and_conversations
    svc = ConversationAttachmentService(db_session, data["tenant_a"].id)

    # Upload attachment with distinctive text
    att = await svc.upload_attachment(
        conversation_id=data["conv_a"].id,
        uploader_user_id=data["user_a"].id,
        filename="solar_energy_specs.txt",
        content=b"Photovoltaic solar panels operating at 22 percent efficiency with microinverters.",
    )
    assert att.status == "READY"

    # Search for matching query
    results = await svc.search_attachment_chunks(data["conv_a"].id, "efficiency of solar panels", top_k=2)
    assert len(results) >= 1
    assert "photovoltaic" in results[0].content.lower()
    assert results[0].document_title == "solar_energy_specs.txt"

    # Search for unrelated query
    no_results = await svc.search_attachment_chunks(data["conv_a"].id, "quantum computing superconductivity", top_k=2)
    assert len(no_results) == 0
