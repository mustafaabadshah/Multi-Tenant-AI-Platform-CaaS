"""Tests for M25 Security, Cross-Tenant Isolation, and Abuse Prevention in Multimodal Subsystems."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SystemRole
from app.core.security import create_access_token
from app.models.assistant import Assistant
from app.models.conversation import Conversation
from app.models.knowledge import KnowledgeBase
from app.models.membership import TenantMembership
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture
async def security_fixture(db_session: AsyncSession):
    # Tenant Alpha
    t_a = Tenant(id=uuid.uuid4(), name="Alpha Corp", slug=f"alpha-{uuid.uuid4().hex[:6]}")
    u_a = User(id=uuid.uuid4(), email=f"alice_{uuid.uuid4().hex[:6]}@alpha.com", hashed_password="pw", full_name="Alice Alpha")
    db_session.add_all([t_a, u_a])
    await db_session.flush()

    admin_role = (await db_session.execute(select(Role).where(Role.name == SystemRole.TENANT_OWNER.value))).scalars().first()
    db_session.add(TenantMembership(id=uuid.uuid4(), tenant_id=t_a.id, user_id=u_a.id, role_id=admin_role.id))

    asst_a = Assistant(id=uuid.uuid4(), tenant_id=t_a.id, name="Alpha Bot", slug=f"abot-{uuid.uuid4().hex[:6]}", llm_provider="mock")
    conv_a = Conversation(id=uuid.uuid4(), tenant_id=t_a.id, user_id=u_a.id, assistant_id=asst_a.id, title="Alpha Thread")
    kb_a = KnowledgeBase(id=uuid.uuid4(), tenant_id=t_a.id, name="Alpha KB", status="ACTIVE")
    db_session.add_all([asst_a, conv_a, kb_a])

    # Tenant Beta
    t_b = Tenant(id=uuid.uuid4(), name="Beta Corp", slug=f"beta-{uuid.uuid4().hex[:6]}")
    u_b = User(id=uuid.uuid4(), email=f"bob_{uuid.uuid4().hex[:6]}@beta.com", hashed_password="pw", full_name="Bob Beta")
    db_session.add_all([t_b, u_b])
    await db_session.flush()

    db_session.add(TenantMembership(id=uuid.uuid4(), tenant_id=t_b.id, user_id=u_b.id, role_id=admin_role.id))
    kb_b = KnowledgeBase(id=uuid.uuid4(), tenant_id=t_b.id, name="Beta KB", status="ACTIVE")
    db_session.add(kb_b)

    await db_session.commit()

    token_a = create_access_token(str(u_a.id), {"email": u_a.email, "tenant_id": str(t_a.id)})
    token_b = create_access_token(str(u_b.id), {"email": u_b.email, "tenant_id": str(t_b.id)})

    return {
        "tenant_a": t_a,
        "user_a": u_a,
        "conv_a": conv_a,
        "kb_a": kb_a,
        "token_a": token_a,
        "tenant_b": t_b,
        "user_b": u_b,
        "kb_b": kb_b,
        "token_b": token_b,
    }


@pytest.mark.asyncio
async def test_unauthorized_cross_tenant_promotion_rejected(client: AsyncClient, security_fixture):
    data = security_fixture
    headers_a = {"Authorization": f"Bearer {data['token_a']}", "X-Tenant-ID": str(data["tenant_a"].id)}
    headers_b = {"Authorization": f"Bearer {data['token_b']}", "X-Tenant-ID": str(data["tenant_b"].id)}

    # Upload attachment in Tenant Alpha
    files = {"file": ("alpha_report.txt", b"Alpha internal proprietary quarterly metrics.", "text/plain")}
    up_resp = await client.post(f"/api/v1/conversations/{data['conv_a'].id}/attachments", headers=headers_a, files=files)
    assert up_resp.status_code == 201
    att_id = up_resp.json()["id"]

    # 1. Tenant Beta tries to promote Tenant Alpha's attachment into Tenant Beta's KB -> 404
    attack_resp = await client.post(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments/{att_id}/promote",
        headers=headers_b,
        json={"knowledge_base_id": str(data["kb_b"].id)},
    )
    assert attack_resp.status_code in (403, 404)

    # 2. Tenant Alpha tries to promote into Tenant Beta's KB -> 400 Access Denied
    cross_kb_resp = await client.post(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments/{att_id}/promote",
        headers=headers_a,
        json={"knowledge_base_id": str(data["kb_b"].id)},
    )
    assert cross_kb_resp.status_code in (400, 403, 404)


@pytest.mark.asyncio
async def test_cross_tenant_attachment_deletion_denied(client: AsyncClient, security_fixture):
    data = security_fixture
    headers_a = {"Authorization": f"Bearer {data['token_a']}", "X-Tenant-ID": str(data["tenant_a"].id)}
    headers_b = {"Authorization": f"Bearer {data['token_b']}", "X-Tenant-ID": str(data["tenant_b"].id)}

    # Upload attachment in Alpha
    files = {"file": ("alpha_doc.txt", b"Alpha doc content.", "text/plain")}
    up_resp = await client.post(f"/api/v1/conversations/{data['conv_a'].id}/attachments", headers=headers_a, files=files)
    assert up_resp.status_code == 201
    att_id = up_resp.json()["id"]

    # Beta attempts to DELETE Alpha's attachment -> 404
    del_resp = await client.delete(
        f"/api/v1/conversations/{data['conv_a'].id}/attachments/{att_id}",
        headers=headers_b,
    )
    assert del_resp.status_code in (403, 404)

    # Verify attachment still exists in Alpha
    get_resp = await client.get(f"/api/v1/conversations/{data['conv_a'].id}/attachments/{att_id}", headers=headers_a)
    assert get_resp.status_code == 200


@pytest.mark.asyncio
async def test_oversized_audio_upload_rejected(client: AsyncClient, security_fixture):
    data = security_fixture
    headers = {"Authorization": f"Bearer {data['token_a']}", "X-Tenant-ID": str(data["tenant_a"].id)}

    # 16 MB payload (exceeds 15 MB limit)
    large_audio = b"\x00" * (16 * 1024 * 1024)
    resp = await client.post(
        "/api/v1/speech/transcribe",
        headers=headers,
        files={"file": ("too_large.wav", large_audio, "audio/wav")},
    )
    assert resp.status_code == 400
    assert "exceeds the maximum allowed limit" in resp.json()["detail"]
