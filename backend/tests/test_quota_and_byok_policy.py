"""Acceptance and Security Test Suite for Stage 4: Quota Concurrency, Reservations, and BYOK Policy."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant_runtime.runtime import AssistantRuntime
from app.models.assistant import Assistant
from app.models.conversation import Conversation
from app.services.quota_service import QuotaService


@pytest.mark.asyncio
async def test_concurrent_quota_reservation_enforcement(seed_data: dict, db_session: AsyncSession):
    """Test that atomic in-flight reservations prevent concurrent requests from bypassing quotas."""
    tenant = seed_data["tenant_a"]
    quota_svc = QuotaService(db_session, tenant.id)

    # 1. Update quota to tight limit: 1,000 monthly tokens
    quota = await quota_svc.get_or_create_quota()
    quota.monthly_token_limit = 1_000
    await db_session.commit()

    # 2. Request A reserves 600 tokens (succeeds)
    res_a = await quota_svc.reserve_quota(estimated_tokens=600)
    assert res_a.startswith("res_")

    # 3. Concurrent Request B attempts to reserve 600 tokens (would total 1200 > 1000) -> 429
    with pytest.raises(HTTPException) as exc_info:
        await quota_svc.reserve_quota(estimated_tokens=600)
    assert exc_info.value.status_code == 429
    assert "Monthly token limit exceeded" in exc_info.value.detail

    # 4. Request A completes and commits actual usage (550 tokens)
    await quota_svc.record_usage(
        provider_name="mock",
        model_name="mock-model",
        prompt_tokens=400,
        completion_tokens=150,
        reservation_id=res_a,
    )

    # 5. Now Request C attempts to reserve 300 tokens (550 used + 300 = 850 <= 1000) -> succeeds
    res_c = await quota_svc.reserve_quota(estimated_tokens=300)
    assert res_c.startswith("res_")

    # Clean up
    quota_svc.release_reservation(res_c)


@pytest.mark.asyncio
async def test_failed_request_reservation_release(seed_data: dict, db_session: AsyncSession):
    """Test that a failed or cancelled request releases its reservation without burning quota."""
    tenant = seed_data["tenant_b"]
    quota_svc = QuotaService(db_session, tenant.id)

    quota = await quota_svc.get_or_create_quota()
    quota.monthly_token_limit = 500
    await db_session.commit()

    # Reserve 400 tokens
    res_id = await quota_svc.reserve_quota(estimated_tokens=400)

    # Subsequent request for 200 tokens fails
    with pytest.raises(HTTPException):
        await quota_svc.reserve_quota(estimated_tokens=200)

    # Request errors out and releases reservation
    quota_svc.release_reservation(res_id)

    # Now the 200 token reservation succeeds because the 400 reservation was released
    res_retry = await quota_svc.reserve_quota(estimated_tokens=200)
    assert res_retry.startswith("res_")
    quota_svc.release_reservation(res_retry)


@pytest.mark.asyncio
async def test_strict_byok_policy_no_silent_fallback(seed_data: dict, db_session: AsyncSession):
    """Verify that assistants using commercial providers without a BYOK key immediately fail with an actionable error.
    
    The platform must NEVER silently fall back to platform-funded credentials.
    """
    tenant = seed_data["tenant_a"]
    user = seed_data["user_a_owner"]

    # Create assistant configured with commercial provider "openai" but NO byok key in vault
    asst = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Uncredentialed Bot",
        slug="uncredentialed-bot-" + uuid.uuid4().hex[:6],
        llm_provider="openai",
        default_model="gpt-4o",
        temperature=0.7,
        max_tokens=256,
    )
    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        assistant_id=asst.id,
        user_id=user.id,
    )
    db_session.add_all([asst, conv])
    await db_session.commit()

    runtime = AssistantRuntime(
        session=db_session,
        tenant_id=tenant.id,
        user_id=user.id,
        is_admin=True,
    )

    events = []
    async for frame in runtime.stream_chat(
        conversation_id=conv.id,
        user_message="Hello, can you help me?",
    ):
        events.append(frame)

    # Verify that stream yields an error explaining BYOK is required and does NOT make paid calls
    error_events = [e for e in events if "message_error" in e]
    assert len(error_events) >= 1
    assert "Provider 'openai' is not configured with an active BYOK credential" in error_events[0]
