"""Speech-to-Text and Text-to-Speech API Router."""

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, require_permission
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.user import User
from app.schemas.conversation_attachment import (
    VoicePreferenceResponse,
    VoicePreferenceUpdateRequest,
)
from app.services.speech.service import SpeechService

router = APIRouter(prefix="/speech", tags=["Speech & Audio"])


class TranscriptionResponse(BaseModel):
    transcript: str
    confidence: float
    language: str
    duration_seconds: float | None = None


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    voice: str | None = None
    language: str = "en-US"
    speech_rate: float = Field(default=1.0, ge=0.5, le=2.0)


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_200_OK,
)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = "en-US",
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TranscriptionResponse:
    """Transcribe an uploaded audio file into text."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio file is empty")

    svc = SpeechService(db, ctx.tenant.id)
    try:
        res = await svc.transcribe_audio(
            audio_bytes=audio_bytes,
            mime_type=file.content_type or "audio/wav",
            language=language,
        )
        return TranscriptionResponse(
            transcript=res.transcript,
            confidence=res.confidence,
            language=res.language,
            duration_seconds=res.duration_seconds,
        )
    except ValueError as v_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(v_err))


@router.post(
    "/synthesize",
    status_code=status.HTTP_200_OK,
)
async def synthesize_speech(
    payload: SynthesisRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Synthesize text into speech audio bytes (WAV format)."""
    svc = SpeechService(db, ctx.tenant.id)
    try:
        res = await svc.synthesize_speech(
            text=payload.text,
            voice=payload.voice,
            language=payload.language,
            speech_rate=payload.speech_rate,
        )
        return Response(
            content=res.audio_bytes,
            media_type=res.mime_type,
            headers={
                "Content-Disposition": 'attachment; filename="synthesized_speech.wav"',
                "X-Character-Count": str(res.character_count),
            },
        )
    except ValueError as v_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(v_err))


@router.get(
    "/voices",
    response_model=list[dict],
)
async def list_voices(
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List available speech voices."""
    svc = SpeechService(db, ctx.tenant.id)
    return svc.get_supported_voices()


@router.get(
    "/preferences",
    response_model=VoicePreferenceResponse,
)
async def get_voice_preferences(
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VoicePreferenceResponse:
    """Retrieve the current user's voice and speech preferences."""
    svc = SpeechService(db, ctx.tenant.id)
    pref = await svc.get_user_voice_preference(current_user.id)
    return VoicePreferenceResponse.model_validate(pref)


@router.put(
    "/preferences",
    response_model=VoicePreferenceResponse,
)
async def update_voice_preferences(
    payload: VoicePreferenceUpdateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VoicePreferenceResponse:
    """Update the current user's voice and speech preferences."""
    svc = SpeechService(db, ctx.tenant.id)
    pref = await svc.update_user_voice_preference(
        user_id=current_user.id,
        voice_mode=payload.voice_mode,
        auto_read=payload.auto_read,
        speech_rate=payload.speech_rate,
        preferred_voice=payload.preferred_voice,
        preferred_language=payload.preferred_language,
    )
    return VoicePreferenceResponse.model_validate(pref)
