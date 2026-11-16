"""Speech Service managing STT transcription, TTS synthesis, and user voice preferences."""

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import VoicePreference
from app.services.speech.base import (
    SpeechToTextProvider,
    SynthesisResult,
    TextToSpeechProvider,
    TranscriptionResult,
)
from app.services.speech.mock import MockSpeechProvider

logger = logging.getLogger("mmaip.speech")

# 15 MB audio upload ceiling
MAX_AUDIO_UPLOAD_BYTES = 15 * 1024 * 1024

ALLOWED_AUDIO_MIMES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/webm",
    "audio/ogg",
    "audio/aac",
    "audio/mp4",
    "audio/x-m4a",
}


class SpeechService:
    """Enterprise Speech Service with fail-closed security and voice mode management."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        stt_provider: Optional[SpeechToTextProvider] = None,
        tts_provider: Optional[TextToSpeechProvider] = None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        # Default to deterministic mock provider unless overridden or configured
        self.stt_provider = stt_provider or MockSpeechProvider()
        self.tts_provider = tts_provider or MockSpeechProvider()

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        mime_type: str,
        language: str = "en-US",
    ) -> TranscriptionResult:
        """Validate audio bytes, enforce size ceilings, and transcribe to text."""
        if not audio_bytes:
            raise ValueError("Audio content cannot be empty.")

        if len(audio_bytes) > MAX_AUDIO_UPLOAD_BYTES:
            raise ValueError(
                f"Audio payload ({len(audio_bytes)} bytes) exceeds the maximum allowed limit of {MAX_AUDIO_UPLOAD_BYTES} bytes."
            )

        # Normalize and validate MIME type
        clean_mime = mime_type.lower().split(";")[0].strip()
        if clean_mime not in ALLOWED_AUDIO_MIMES:
            raise ValueError(
                f"Unsupported audio format '{clean_mime}'. Allowed formats: {', '.join(sorted(ALLOWED_AUDIO_MIMES))}"
            )

        result = await self.stt_provider.transcribe(
            audio_bytes=audio_bytes,
            mime_type=clean_mime,
            language=language,
        )
        return result

    async def synthesize_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        language: str = "en-US",
        speech_rate: float = 1.0,
    ) -> SynthesisResult:
        """Synthesize text into speech audio bytes."""
        if not text or not text.strip():
            raise ValueError("Text to synthesize cannot be empty.")

        # Cap text length to prevent resource exhaustion (max 8,000 characters per synthesis request)
        clean_text = text.strip()[:8000]

        result = await self.tts_provider.synthesize(
            text=clean_text,
            voice=voice,
            language=language,
            speech_rate=speech_rate,
        )
        return result

    async def get_user_voice_preference(self, user_id: uuid.UUID) -> VoicePreference:
        """Fetch or create default voice preference for a tenant user."""
        stmt = select(VoicePreference).where(
            VoicePreference.tenant_id == self.tenant_id,
            VoicePreference.user_id == user_id,
        )
        pref = (await self.session.execute(stmt)).scalar_one_or_none()
        if not pref:
            pref = VoicePreference(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                user_id=user_id,
                voice_mode="TEXT",
                auto_read=False,
                speech_rate=1.0,
                preferred_voice=None,
                preferred_language="en-US",
            )
            self.session.add(pref)
            await self.session.commit()
            await self.session.refresh(pref)
        return pref

    async def update_user_voice_preference(
        self,
        user_id: uuid.UUID,
        voice_mode: Optional[str] = None,
        auto_read: Optional[bool] = None,
        speech_rate: Optional[float] = None,
        preferred_voice: Optional[str] = None,
        preferred_language: Optional[str] = None,
    ) -> VoicePreference:
        """Update user voice preference settings."""
        pref = await self.get_user_voice_preference(user_id)
        if voice_mode is not None:
            pref.voice_mode = voice_mode
        if auto_read is not None:
            pref.auto_read = auto_read
        if speech_rate is not None:
            pref.speech_rate = max(0.5, min(2.0, speech_rate))
        if preferred_voice is not None:
            pref.preferred_voice = preferred_voice
        if preferred_language is not None:
            pref.preferred_language = preferred_language

        await self.session.commit()
        await self.session.refresh(pref)
        return pref

    def get_supported_voices(self) -> list[dict]:
        """Return inventory of available speech voices across supported engines."""
        return [
            {"id": "browser-default", "name": "Browser Default Voice", "provider": "browser", "lang": "en-US"},
            {"id": "mock-natural-en", "name": "Mock Natural English", "provider": "system", "lang": "en-US"},
            {"id": "mock-natural-ur", "name": "Mock Urdu Speaker", "provider": "system", "lang": "ur-PK"},
        ]
