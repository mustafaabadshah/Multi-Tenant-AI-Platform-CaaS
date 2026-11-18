"""M28 Message Feedback and Quality Telemetry Test Suite."""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message, MessageFeedback
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.feedback import (
    FeedbackCategory,
    FeedbackRating,
    FeedbackStatus,
    MessageFeedbackCreate,
)
from app.services.feedback_service import FeedbackService


@pytest.fixture
async def setup_feedback_environment(db_session: AsyncSession):
    """Sets up an isolated tenant, assistant, conversation, and messages."""
    tenant_a = Tenant(id=uuid.uuid4(), name="Tenant Alpha", slug=f"alpha-{uuid.uuid4().hex[:8]}")
    tenant_b = Tenant(id=uuid.uuid4(), name="Tenant Beta", slug=f"beta-{uuid.uuid4().hex[:8]}")
    
    user_a = User(
        id=uuid.uuid4(),
        email="user_a@example.com",
        hashed_password="mocked_password_hash",
        full_name="User Alpha",
        status="ACTIVE",
    )
    user_b = User(
        id=uuid.uuid4(),
        email="user_b@example.com",
        hashed_password="mocked_password_hash",
        full_name="User Beta",
        status="ACTIVE",
    )
    
    asst_a = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Support Assistant Alpha",
        slug="support-assistant-alpha",
        status="ACTIVE",
    )
    
    conv_a = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_a.id,
        assistant_id=asst_a.id,
        title="Test Conversation",
        status="ACTIVE",
    )
    
    msg_user = Message(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        conversation_id=conv_a.id,
        sender_type="user",
        content="Hello assistant, can you help me?",
    )
    
    msg_asst = Message(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        conversation_id=conv_a.id,
        sender_type="assistant",
        content="Yes, I am happy to help you with your account.",
    )
    
    db_session.add_all([tenant_a, tenant_b, user_a, user_b, asst_a, conv_a, msg_user, msg_asst])
    await db_session.commit()
    
    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_a": user_a,
        "user_b": user_b,
        "asst_a": asst_a,
        "conv_a": conv_a,
        "msg_user": msg_user,
        "msg_asst": msg_asst,
    }


@pytest.mark.asyncio
async def test_submit_thumbs_up_feedback(db_session: AsyncSession, setup_feedback_environment):
    env = setup_feedback_environment
    svc = FeedbackService(
        session=db_session,
        tenant_id=env["tenant_a"].id,
        user_id=env["user_a"].id,
        is_admin=False,
    )
    
    payload = MessageFeedbackCreate(rating=FeedbackRating.THUMBS_UP)
    fb = await svc.submit_feedback(
        conversation_id=env["conv_a"].id,
        message_id=env["msg_asst"].id,
        payload=payload,
    )
    
    assert fb.id is not None
    assert fb.rating == "THUMBS_UP"
    assert fb.category is None
    assert fb.status == "NEW"
    assert fb.tenant_id == env["tenant_a"].id
    assert fb.user_id == env["user_a"].id
    assert fb.assistant_id == env["asst_a"].id


@pytest.mark.asyncio
async def test_update_feedback_idempotent(db_session: AsyncSession, setup_feedback_environment):
    env = setup_feedback_environment
    svc = FeedbackService(
        session=db_session,
        tenant_id=env["tenant_a"].id,
        user_id=env["user_a"].id,
        is_admin=False,
    )
    
    # Initial submission: Thumbs Up
    fb1 = await svc.submit_feedback(
        conversation_id=env["conv_a"].id,
        message_id=env["msg_asst"].id,
        payload=MessageFeedbackCreate(rating=FeedbackRating.THUMBS_UP),
    )
    
    # Update to Thumbs Down with category and comment
    fb2 = await svc.submit_feedback(
        conversation_id=env["conv_a"].id,
        message_id=env["msg_asst"].id,
        payload=MessageFeedbackCreate(
            rating=FeedbackRating.THUMBS_DOWN,
            category=FeedbackCategory.HALLUCINATION,
            comment="The response hallucinated the account fee policy.",
        ),
    )
    
    assert fb1.id == fb2.id  # Must update the existing row, not create duplicate
    assert fb2.rating == "THUMBS_DOWN"
    assert fb2.category == "HALLUCINATION"
    assert fb2.comment == "The response hallucinated the account fee policy."


@pytest.mark.asyncio
async def test_feedback_on_user_message_rejected(db_session: AsyncSession, setup_feedback_environment):
    env = setup_feedback_environment
    svc = FeedbackService(
        session=db_session,
        tenant_id=env["tenant_a"].id,
        user_id=env["user_a"].id,
        is_admin=False,
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await svc.submit_feedback(
            conversation_id=env["conv_a"].id,
            message_id=env["msg_user"].id,
            payload=MessageFeedbackCreate(rating=FeedbackRating.THUMBS_UP),
        )
    assert exc_info.value.status_code == 400
    assert "assistant messages" in exc_info.value.detail


@pytest.mark.asyncio
async def test_cross_tenant_feedback_denied(db_session: AsyncSession, setup_feedback_environment):
    env = setup_feedback_environment
    # Attempting to submit feedback using Tenant B's context for Tenant A's message
    svc = FeedbackService(
        session=db_session,
        tenant_id=env["tenant_b"].id,
        user_id=env["user_b"].id,
        is_admin=False,
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await svc.submit_feedback(
            conversation_id=env["conv_a"].id,
            message_id=env["msg_asst"].id,
            payload=MessageFeedbackCreate(rating=FeedbackRating.THUMBS_UP),
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_feedback_telemetry_accuracy(db_session: AsyncSession, setup_feedback_environment):
    env = setup_feedback_environment
    svc = FeedbackService(
        session=db_session,
        tenant_id=env["tenant_a"].id,
        user_id=env["user_a"].id,
        is_admin=True,
    )
    
    # 0 feedback initially
    t0 = await svc.get_feedback_telemetry()
    assert t0.total_feedback_count == 0
    assert t0.positive_percentage is None
    assert t0.is_sparse_sample is True
    
    # Add 1 positive
    await svc.submit_feedback(
        conversation_id=env["conv_a"].id,
        message_id=env["msg_asst"].id,
        payload=MessageFeedbackCreate(rating=FeedbackRating.THUMBS_UP),
    )
    
    t1 = await svc.get_feedback_telemetry()
    assert t1.total_feedback_count == 1
    assert t1.positive_count == 1
    assert t1.negative_count == 0
    assert t1.positive_percentage == 100.0
    assert t1.is_sparse_sample is True  # < 5


@pytest.mark.asyncio
async def test_admin_feedback_stream_and_status_lifecycle(db_session: AsyncSession, setup_feedback_environment):
    env = setup_feedback_environment
    # Submit feedback
    user_svc = FeedbackService(
        session=db_session,
        tenant_id=env["tenant_a"].id,
        user_id=env["user_a"].id,
        is_admin=False,
    )
    fb = await user_svc.submit_feedback(
        conversation_id=env["conv_a"].id,
        message_id=env["msg_asst"].id,
        payload=MessageFeedbackCreate(
            rating=FeedbackRating.THUMBS_DOWN,
            category=FeedbackCategory.INCOMPLETE,
            comment="Needs more details on reset procedure.",
        ),
    )
    
    # Non-admin cannot list stream
    with pytest.raises(HTTPException) as exc_info:
        await user_svc.list_feedback()
    assert exc_info.value.status_code == 403
    
    # Admin can list stream
    admin_svc = FeedbackService(
        session=db_session,
        tenant_id=env["tenant_a"].id,
        user_id=env["user_a"].id,
        is_admin=True,
    )
    items = await admin_svc.list_feedback()
    assert len(items) == 1
    assert items[0]["id"] == fb.id
    assert items[0]["rating"] == "THUMBS_DOWN"
    assert items[0]["category"] == "INCOMPLETE"
    assert items[0]["status"] == "NEW"
    
    # Admin updates status to REVIEWED
    updated = await admin_svc.update_feedback_status(
        feedback_id=fb.id,
        new_status=FeedbackStatus.REVIEWED.value,
        admin_notes="Reviewed by QA team. Passed to prompt engineering.",
    )
    assert updated.status == "REVIEWED"
    assert updated.admin_notes == "Reviewed by QA team. Passed to prompt engineering."
