"""Tests for M24 Multimodal Agentic Runtime integrating text, attachments, speech, and citations."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import SystemRole
from app.core.security import create_access_token
from app.models.assistant import Assistant
from app.models.conversation import Conversation, Message
from app.models.membership import TenantMembership
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.services.conversation_attachment_service import ConversationAttachmentService


@pytest.fixture
async def multimodal_test_setup(db_session: AsyncSession):
    tenant = Tenant(id=uuid.uuid4(), name="Multimodal Tenant", slug=f"multi-{uuid.uuid4().hex[:6]}")
    user = User(id=uuid.uuid4(), email=f"multi_user_{uuid.uuid4().hex[:6]}@example.com", hashed_password="pw", full_name="Multimodal User")
    db_session.add_all([tenant, user])
    await db_session.flush()

    role = (await db_session.execute(select(Role).where(Role.name == SystemRole.TENANT_OWNER.value))).scalars().first()
    mem = TenantMembership(id=uuid.uuid4(), tenant_id=tenant.id, user_id=user.id, role_id=role.id)
    db_session.add(mem)

    assistant = Assistant(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name="Multimodal Research Assistant",
        slug=f"multi-asst-{uuid.uuid4().hex[:6]}",
        system_prompt="You are a document-grounded research assistant. Ground all facts in provided context.",
        llm_provider="mock",
        default_model="mock-model",
    )
    conv = Conversation(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        assistant_id=assistant.id,
        title="Multimodal Grounded Chat",
    )
    db_session.add_all([assistant, conv])
    await db_session.commit()

    token = create_access_token(str(user.id), {"email": user.email, "tenant_id": str(tenant.id)})
    return {"tenant": tenant, "user": user, "assistant": assistant, "conv": conv, "token": token}


@pytest.mark.asyncio
async def test_assistant_chat_with_conversation_attachment_citations(
    client: AsyncClient, db_session: AsyncSession, multimodal_test_setup
):
    ctx = multimodal_test_setup
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Tenant-ID": str(ctx["tenant"].id)}

    # 1. Attach document to conversation
    att_svc = ConversationAttachmentService(db_session, ctx["tenant"].id)
    doc_text = b"Project Nebula specifications: Orbital velocity is 7.8 kilometers per second with liquid hydrogen propulsion."
    att = await att_svc.upload_attachment(
        conversation_id=ctx["conv"].id,
        uploader_user_id=ctx["user"].id,
        filename="project_nebula_specs.txt",
        content=doc_text,
    )
    assert att.status == "READY"

    # 2. Send message asking about the attached document
    chat_payload = {"content": "What is the orbital velocity of Project Nebula?"}
    chat_resp = await client.post(
        f"/api/v1/conversations/{ctx['conv'].id}/messages/stream",
        headers=headers,
        json=chat_payload,
    )
    assert chat_resp.status_code == 200
    sse_text = chat_resp.text
    assert "retrieval_complete" in sse_text
    assert "project_nebula_specs.txt" in sse_text

    # 3. Verify message and citations in database
    msg_stmt = (
        select(Message)
        .options(selectinload(Message.citations))
        .where(
            Message.conversation_id == ctx["conv"].id,
            Message.sender_type == "assistant",
        )
    )
    asst_msgs = (await db_session.execute(msg_stmt)).scalars().all()
    assert len(asst_msgs) >= 1
    last_msg = asst_msgs[-1]
    assert len(last_msg.citations) >= 1
    assert last_msg.citations[0].document_name == "project_nebula_specs.txt"


@pytest.mark.asyncio
async def test_multimodal_speech_transcription_then_stream_chat(
    client: AsyncClient, multimodal_test_setup
):
    ctx = multimodal_test_setup
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Tenant-ID": str(ctx["tenant"].id)}

    # 1. Transcribe spoken audio
    from app.services.speech.mock import create_mock_wav
    audio_wav = create_mock_wav(duration_seconds=1.0)
    transcribe_resp = await client.post(
        "/api/v1/speech/transcribe",
        headers=headers,
        files={"file": ("voice_note.wav", audio_wav, "audio/wav")},
    )
    assert transcribe_resp.status_code == 200
    spoken_text = transcribe_resp.json()["transcript"]
    assert spoken_text

    # 2. Submit transcript directly into chat stream
    stream_resp = await client.post(
        f"/api/v1/conversations/{ctx['conv'].id}/messages/stream",
        headers=headers,
        json={"content": spoken_text},
    )
    assert stream_resp.status_code == 200
    assert "message_start" in stream_resp.text
    assert "token" in stream_resp.text
    assert "message_complete" in stream_resp.text
