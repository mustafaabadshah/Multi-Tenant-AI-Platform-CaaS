"""Tests for M28.13 Knowledge Base Data Integrity, Assistant-KB Routing, Promotion Security & Multi-Tenant Isolation.
"""

import io
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SystemRole
from app.core.security import create_access_token
from app.models.assistant import Assistant, AssistantKnowledgeBase
from app.models.conversation import Conversation, ConversationAttachment, ConversationAttachmentChunk
from app.models.knowledge import KnowledgeBase, Document, DocumentChunk
from app.models.membership import TenantMembership
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.services.conversation_attachment_service import ConversationAttachmentService


@pytest.fixture
async def setup_m28_13_env(db_session: AsyncSession):
    # 1. Tenant Alpha (PF vs Cricket scenario)
    tenant_a = Tenant(id=uuid.uuid4(), name="Tenant Alpha", slug=f"alpha-{uuid.uuid4().hex[:6]}")
    user_a = User(id=uuid.uuid4(), email=f"user_a_{uuid.uuid4().hex[:6]}@alpha.com", hashed_password="pw", full_name="User Alpha")
    db_session.add_all([tenant_a, user_a])
    await db_session.flush()

    admin_role = (await db_session.execute(select(Role).where(Role.name == SystemRole.TENANT_OWNER.value))).scalars().first()
    mem_a = TenantMembership(id=uuid.uuid4(), tenant_id=tenant_a.id, user_id=user_a.id, role_id=admin_role.id)
    db_session.add(mem_a)

    # KB 1: PF
    kb_pf = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="PF", status="ACTIVE")
    # KB 2: Cricket
    kb_cricket = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Cricket", status="ACTIVE")
    # KB 3: Inactive KB
    kb_archived = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_a.id, name="Archived KB", status="ARCHIVED")
    db_session.add_all([kb_pf, kb_cricket, kb_archived])

    # Assistant: Notes & Textbook Q&A Assistant, connected to PF ONLY
    asst_notes = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Notes & Textbook Q&A Assistant",
        slug=f"notes-asst-{uuid.uuid4().hex[:6]}",
        system_prompt="You are a helpful assistant.",
        llm_provider="omniroute",
    )
    db_session.add(asst_notes)
    await db_session.flush()

    # Link asst_notes strictly to kb_pf
    link_notes_pf = AssistantKnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        assistant_id=asst_notes.id,
        knowledge_base_id=kb_pf.id,
    )
    db_session.add(link_notes_pf)

    # Conversation under Notes Assistant
    conv_a = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_a.id,
        assistant_id=asst_notes.id,
        title="Solar Irradiance Discussion",
    )
    db_session.add(conv_a)

    # Attachment in conv_a
    att = ConversationAttachment(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        conversation_id=conv_a.id,
        uploader_user_id=user_a.id,
        filename="solar_paper.pdf",
        file_size=2048,
        file_path="mock/path/solar_paper.pdf",
        content_type="application/pdf",
        file_hash="hash_solar_123",
        extracted_text="Solar irradiance forecasting with neural architectures.",
        status="READY",
        is_promoted=False,
    )
    db_session.add(att)
    await db_session.flush()

    chunk1 = ConversationAttachmentChunk(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        conversation_id=conv_a.id,
        attachment_id=att.id,
        chunk_index=0,
        content="Solar irradiance forecasting requires accurate baseline models.",
        token_count=12,
        page_number=1,
    )
    db_session.add(chunk1)

    # 2. Tenant Beta (Cross-tenant security)
    tenant_b = Tenant(id=uuid.uuid4(), name="Tenant Beta", slug=f"beta-{uuid.uuid4().hex[:6]}")
    user_b = User(id=uuid.uuid4(), email=f"user_b_{uuid.uuid4().hex[:6]}@beta.com", hashed_password="pw", full_name="User Beta")
    db_session.add_all([tenant_b, user_b])
    await db_session.flush()

    mem_b = TenantMembership(id=uuid.uuid4(), tenant_id=tenant_b.id, user_id=user_b.id, role_id=admin_role.id)
    kb_beta = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_b.id, name="Beta Core KB", status="ACTIVE")
    db_session.add_all([mem_b, kb_beta])

    await db_session.commit()

    token_a = create_access_token(str(user_a.id), {"email": user_a.email, "tenant_id": str(tenant_a.id)})
    token_b = create_access_token(str(user_b.id), {"email": user_b.email, "tenant_id": str(tenant_b.id)})

    return {
        "tenant_a": tenant_a,
        "user_a": user_a,
        "token_a": token_a,
        "kb_pf": kb_pf,
        "kb_cricket": kb_cricket,
        "kb_archived": kb_archived,
        "asst_notes": asst_notes,
        "conv_a": conv_a,
        "att": att,
        "chunk1": chunk1,
        "tenant_b": tenant_b,
        "user_b": user_b,
        "token_b": token_b,
        "kb_beta": kb_beta,
    }


@pytest.mark.asyncio
async def test_promotion_valid_explicit_destination(client: AsyncClient, setup_m28_13_env, db_session: AsyncSession):
    """Scenario 1 & 2: User explicitly selects PF KB and attachment promotes successfully."""
    env = setup_m28_13_env
    headers = {"Authorization": f"Bearer {env['token_a']}", "X-Tenant-ID": str(env["tenant_a"].id)}

    payload = {
        "knowledge_base_id": str(env["kb_pf"].id),
        "title": "Solar Paper - PF Edition",
    }
    resp = await client.post(
        f"/api/v1/conversations/{env['conv_a'].id}/attachments/{env['att'].id}/promote",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "PROMOTED"
    assert data["knowledge_base_id"] == str(env["kb_pf"].id)
    assert data["document_id"] is not None

    # Verify Document and chunks in DB belong to kb_pf
    doc = (await db_session.execute(select(Document).where(Document.id == uuid.UUID(data["document_id"])))).scalar_one_or_none()
    assert doc is not None
    assert doc.knowledge_base_id == env["kb_pf"].id
    assert doc.filename == "Solar Paper - PF Edition"
    assert doc.status == "READY"
    assert doc.total_chunks == 1


@pytest.mark.asyncio
async def test_repeated_promotion_is_rejected(client: AsyncClient, setup_m28_13_env):
    """Scenario 10: Repeated promotion of an already-promoted attachment is rejected with HTTP 400."""
    env = setup_m28_13_env
    headers = {"Authorization": f"Bearer {env['token_a']}", "X-Tenant-ID": str(env["tenant_a"].id)}

    payload = {"knowledge_base_id": str(env["kb_pf"].id)}
    
    # First call succeeds
    resp1 = await client.post(
        f"/api/v1/conversations/{env['conv_a'].id}/attachments/{env['att'].id}/promote",
        headers=headers,
        json=payload,
    )
    assert resp1.status_code == 200

    # Second call must be rejected
    resp2 = await client.post(
        f"/api/v1/conversations/{env['conv_a'].id}/attachments/{env['att'].id}/promote",
        headers=headers,
        json=payload,
    )
    assert resp2.status_code == 400
    assert "already promoted" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_promotion_cross_kb_repromotion_blocked(client: AsyncClient, setup_m28_13_env):
    """Attempting to promote an already-promoted attachment to a DIFFERENT KB is rejected."""
    env = setup_m28_13_env
    headers = {"Authorization": f"Bearer {env['token_a']}", "X-Tenant-ID": str(env["tenant_a"].id)}

    # Promote to PF first
    resp1 = await client.post(
        f"/api/v1/conversations/{env['conv_a'].id}/attachments/{env['att'].id}/promote",
        headers=headers,
        json={"knowledge_base_id": str(env["kb_pf"].id)},
    )
    assert resp1.status_code == 200

    # Attempt to promote same attachment to Cricket
    resp2 = await client.post(
        f"/api/v1/conversations/{env['conv_a'].id}/attachments/{env['att'].id}/promote",
        headers=headers,
        json={"knowledge_base_id": str(env["kb_cricket"].id)},
    )
    assert resp2.status_code == 400
    assert "already promoted" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_promotion_cross_tenant_kb_rejected(client: AsyncClient, setup_m28_13_env):
    """Scenario 3: User in Tenant Alpha attempts to promote to a KB belonging to Tenant Beta."""
    env = setup_m28_13_env
    headers = {"Authorization": f"Bearer {env['token_a']}", "X-Tenant-ID": str(env["tenant_a"].id)}

    payload = {"knowledge_base_id": str(env["kb_beta"].id)}
    resp = await client.post(
        f"/api/v1/conversations/{env['conv_a'].id}/attachments/{env['att'].id}/promote",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == 400
    assert "access denied" in resp.json()["detail"].lower() or "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_promotion_mismatched_duplicate_target_fields_rejected(client: AsyncClient, setup_m28_13_env):
    """Scenario 13: Payload provides both knowledge_base_id and target_knowledge_base_id with conflicting values."""
    env = setup_m28_13_env
    headers = {"Authorization": f"Bearer {env['token_a']}", "X-Tenant-ID": str(env["tenant_a"].id)}

    payload = {
        "knowledge_base_id": str(env["kb_pf"].id),
        "target_knowledge_base_id": str(env["kb_cricket"].id),
    }
    resp = await client.post(
        f"/api/v1/conversations/{env['conv_a'].id}/attachments/{env['att'].id}/promote",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == 400
    assert "conflicting target knowledge base ids" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_promotion_nonexistent_kb_rejected(client: AsyncClient, setup_m28_13_env):
    """Scenario 7: Nonexistent KB UUID is rejected."""
    env = setup_m28_13_env
    headers = {"Authorization": f"Bearer {env['token_a']}", "X-Tenant-ID": str(env["tenant_a"].id)}

    payload = {"knowledge_base_id": str(uuid.uuid4())}
    resp = await client.post(
        f"/api/v1/conversations/{env['conv_a'].id}/attachments/{env['att'].id}/promote",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower() or "access denied" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_promotion_archived_kb_rejected(client: AsyncClient, setup_m28_13_env):
    """Scenario 8: Archived/inactive KB is rejected."""
    env = setup_m28_13_env
    headers = {"Authorization": f"Bearer {env['token_a']}", "X-Tenant-ID": str(env["tenant_a"].id)}

    payload = {"knowledge_base_id": str(env["kb_archived"].id)}
    resp = await client.post(
        f"/api/v1/conversations/{env['conv_a'].id}/attachments/{env['att'].id}/promote",
        headers=headers,
        json=payload,
    )
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower() or "access denied" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_promotion_unauthorized_user_rejected(client: AsyncClient, setup_m28_13_env):
    """Scenario 4: User without tenant access is rejected."""
    env = setup_m28_13_env
    headers_b = {"Authorization": f"Bearer {env['token_b']}", "X-Tenant-ID": str(env["tenant_b"].id)}

    payload = {"knowledge_base_id": str(env["kb_beta"].id)}
    resp = await client.post(
        f"/api/v1/conversations/{env['conv_a'].id}/attachments/{env['att'].id}/promote",
        headers=headers_b,
        json=payload,
    )
    assert resp.status_code == 404
