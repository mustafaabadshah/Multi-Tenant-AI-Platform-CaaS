"""Tests for M23 Speech-to-Text (STT) and Text-to-Speech (TTS) subsystem."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SystemRole
from app.core.security import create_access_token
from app.models.membership import TenantMembership
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.services.speech.mock import create_mock_wav


@pytest.fixture
async def speech_test_context(db_session: AsyncSession):
    tenant = Tenant(id=uuid.uuid4(), name="Speech Tenant", slug=f"speech-{uuid.uuid4().hex[:6]}")
    user = User(id=uuid.uuid4(), email=f"speech_user_{uuid.uuid4().hex[:6]}@example.com", hashed_password="pw", full_name="Speech User")
    db_session.add_all([tenant, user])
    await db_session.flush()

    role = (await db_session.execute(select(Role).where(Role.name == SystemRole.TENANT_OWNER.value))).scalars().first()
    mem = TenantMembership(id=uuid.uuid4(), tenant_id=tenant.id, user_id=user.id, role_id=role.id)
    db_session.add(mem)
    await db_session.commit()

    token = create_access_token(str(user.id), {"email": user.email, "tenant_id": str(tenant.id)})
    return {"tenant": tenant, "user": user, "token": token}


@pytest.mark.asyncio
async def test_transcribe_audio_endpoint(client: AsyncClient, speech_test_context):
    ctx = speech_test_context
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Tenant-ID": str(ctx["tenant"].id)}

    wav_bytes = create_mock_wav(duration_seconds=1.5)
    files = {"file": ("recording.wav", wav_bytes, "audio/wav")}

    resp = await client.post("/api/v1/speech/transcribe", headers=headers, files=files)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "transcript" in body
    assert body["confidence"] > 0.9
    assert body["language"] == "en-US"


@pytest.mark.asyncio
async def test_transcribe_audio_validation_errors(client: AsyncClient, speech_test_context):
    ctx = speech_test_context
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Tenant-ID": str(ctx["tenant"].id)}

    # 1. Empty audio
    files = {"file": ("empty.wav", b"", "audio/wav")}
    resp = await client.post("/api/v1/speech/transcribe", headers=headers, files=files)
    assert resp.status_code == 400

    # 2. Unsupported audio format
    files = {"file": ("bad.exe", b"not-audio", "application/x-msdownload")}
    resp = await client.post("/api/v1/speech/transcribe", headers=headers, files=files)
    assert resp.status_code == 400
    assert "Unsupported audio format" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_synthesize_speech_endpoint(client: AsyncClient, speech_test_context):
    ctx = speech_test_context
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Tenant-ID": str(ctx["tenant"].id)}

    payload = {
        "text": "Welcome to the Multi-Tenant AI Platform. Your workspace is ready.",
        "voice": "mock-natural-en",
        "language": "en-US",
        "speech_rate": 1.0,
    }
    resp = await client.post("/api/v1/speech/synthesize", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "audio/wav"
    audio_content = resp.content
    assert len(audio_content) > 44  # Valid WAV header + data
    assert audio_content[:4] == b"RIFF"
    assert audio_content[8:12] == b"WAVE"


@pytest.mark.asyncio
async def test_voice_preferences_lifecycle(client: AsyncClient, speech_test_context):
    ctx = speech_test_context
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Tenant-ID": str(ctx["tenant"].id)}

    # 1. Fetch default preferences
    get_resp = await client.get("/api/v1/speech/preferences", headers=headers)
    assert get_resp.status_code == 200
    pref = get_resp.json()
    assert pref["voice_mode"] == "TEXT"
    assert pref["auto_read"] is False
    assert pref["speech_rate"] == 1.0

    # 2. Update preferences
    update_payload = {
        "voice_mode": "VOICE_CONVERSATION",
        "auto_read": True,
        "speech_rate": 1.25,
        "preferred_voice": "mock-natural-en",
        "preferred_language": "en-US",
    }
    put_resp = await client.put("/api/v1/speech/preferences", headers=headers, json=update_payload)
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["voice_mode"] == "VOICE_CONVERSATION"
    assert updated["auto_read"] is True
    assert updated["speech_rate"] == 1.25


@pytest.mark.asyncio
async def test_list_voices_endpoint(client: AsyncClient, speech_test_context):
    ctx = speech_test_context
    headers = {"Authorization": f"Bearer {ctx['token']}", "X-Tenant-ID": str(ctx["tenant"].id)}

    resp = await client.get("/api/v1/speech/voices", headers=headers)
    assert resp.status_code == 200
    voices = resp.json()
    assert len(voices) >= 1
    assert any(v["id"] == "mock-natural-en" for v in voices)
