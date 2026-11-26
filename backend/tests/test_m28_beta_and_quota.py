"""M28 Beta Cohort Operations and Quota Accounting Test Suite."""

import uuid
from datetime import UTC, datetime, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message, MessageFeedback
from app.models.invitation import Invitation
from app.models.knowledge import Document, KnowledgeBase
from app.models.membership import TenantMembership
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.services.quota_service import QuotaService
from app.api.v1.beta import get_beta_cohort
from app.api.deps import TenantContext


@pytest.fixture
async def setup_beta_environment(db_session: AsyncSession):
    tenant_a = Tenant(id=uuid.uuid4(), name="Beta Org", slug=f"beta-{uuid.uuid4().hex[:8]}")
    
    # Fetch seeded system roles
    from sqlalchemy import select
    from app.core.constants import SystemRole
    role_emp = (await db_session.execute(select(Role).where(Role.name == SystemRole.EMPLOYEE.value))).scalar_one()
    role_admin = (await db_session.execute(select(Role).where(Role.name == SystemRole.ORG_ADMIN.value))).scalar_one()

    user_admin = User(
        id=uuid.uuid4(),
        email="admin@beta.org",
        hashed_password="pw",
        full_name="Beta Admin",
        status="ACTIVE",
    )
    user_tester = User(
        id=uuid.uuid4(),
        email="tester@beta.org",
        hashed_password="pw",
        full_name="Beta Tester 1",
        status="ACTIVE",
    )
    db_session.add_all([tenant_a, user_admin, user_tester])
    await db_session.flush()

    # Memberships
    mem_admin = TenantMembership(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_admin.id,
        role_id=role_admin.id,
        status="ACTIVE",
    )
    mem_tester = TenantMembership(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_tester.id,
        role_id=role_emp.id,
        status="ACTIVE",
    )
    db_session.add_all([mem_admin, mem_tester])

    # Invitation (1 pending, 1 accepted)
    now = datetime.now(UTC)
    inv_pending = Invitation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="invitee2@beta.org",
        role_id=role_emp.id,
        token="tok_abc123456789",
        expires_at=now + timedelta(days=7),
    )
    inv_accepted = Invitation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        email="tester@beta.org",
        role_id=role_emp.id,
        token="tok_def987654321",
        expires_at=now + timedelta(days=7),
        accepted_at=now - timedelta(days=1),
    )
    db_session.add_all([inv_pending, inv_accepted])

    # Assistant & Knowledge Base & Document
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Beta Assistant",
        slug="beta-assistant",
        status="ACTIVE",
    )
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Beta KB",
        status="ACTIVE",
    )
    db_session.add_all([asst, kb])
    await db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        knowledge_base_id=kb.id,
        filename="user_guide.pdf",
        safe_filename="user_guide.pdf",
        file_path="/storage/user_guide.pdf",
        file_size=2048576,  # ~2 MB
        mime_type="application/pdf",
        status="READY",
    )
    db_session.add(doc)

    # Conversation, messages, feedback
    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_tester.id,
        assistant_id=asst.id,
        title="Beta Session 1",
        status="ACTIVE",
    )
    db_session.add(conv)
    await db_session.flush()

    msg_u = Message(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        conversation_id=conv.id,
        sender_type="user",
        content="Testing beta assistant response quality.",
    )
    msg_a = Message(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        conversation_id=conv.id,
        sender_type="assistant",
        content="Response quality verified.",
    )
    db_session.add_all([msg_u, msg_a])
    await db_session.flush()

    fb = MessageFeedback(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        conversation_id=conv.id,
        message_id=msg_a.id,
        assistant_id=asst.id,
        user_id=user_tester.id,
        rating="THUMBS_UP",
        status="NEW",
    )
    db_session.add(fb)
    await db_session.commit()

    return {
        "tenant": tenant_a,
        "user_admin": user_admin,
        "user_tester": user_tester,
        "mem_admin": mem_admin,
        "role_admin": role_admin,
        "asst": asst,
        "doc": doc,
    }


@pytest.mark.asyncio
async def test_quota_service_usage_summary(db_session: AsyncSession, setup_beta_environment):
    env = setup_beta_environment
    quota_svc = QuotaService(db_session, env["tenant"].id)
    summary = await quota_svc.get_usage_summary()

    assert summary["storage_bytes_used"] >= 2048576
    assert summary["storage_bytes_limit"] == 10737418240
    assert summary["document_count"] >= 1
    assert summary["active_assistants"] >= 1
    assert "measurement_timestamp" in summary
    assert "reset_timestamp" in summary


@pytest.mark.asyncio
async def test_beta_cohort_endpoint(db_session: AsyncSession, setup_beta_environment):
    env = setup_beta_environment
    
    ctx = TenantContext(
        tenant=env["tenant"],
        membership=env["mem_admin"],
        role=env["role_admin"],
        permissions={"member.read"},
    )
    
    resp = await get_beta_cohort(ctx=ctx, current_user=env["user_admin"], db=db_session)
    summary = resp.summary

    assert summary.total_invited == 2
    assert summary.pending_invitations == 1
    assert summary.accepted_invitations == 1
    assert summary.active_beta_members == 2
    assert summary.total_conversation_turns >= 1
    assert summary.total_feedback_count == 1
    assert summary.positive_feedback_count == 1
    assert summary.negative_feedback_count == 0
    assert summary.satisfaction_rate == 100.0
    assert summary.is_sparse_sample is True

    # Check invitation tokens masked
    assert len(resp.invitations) == 2
    for inv in resp.invitations:
        assert inv.token_preview.endswith("...")

    # Check members activity
    assert len(resp.members) == 2
    tester_mem = next(m for m in resp.members if m.email == "tester@beta.org")
    assert tester_mem.feedback_count == 1
    assert tester_mem.message_count >= 1
