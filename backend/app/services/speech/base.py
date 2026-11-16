"""Speech-to-Text (STT) and Text-to-Speech (TTS) Provider Interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TranscriptionResult:
    transcript: str
    confidence: float = 1.0
    language: str = "en-US"
    duration_seconds: Optional[float] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SynthesisResult:
    audio_bytes: bytes
    mime_type: str = "audio/wav"
    character_count: int = 0
    duration_seconds: Optional[float] = None
    voice_used: Optional[str] = None


class SpeechToTextProvider(ABC):
    """Abstract interface for Speech-to-Text audio transcription."""

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str,
        language: str = "en-US",
        options: Optional[dict] = None,
    ) -> TranscriptionResult:
        """Transcribe speech audio into normalized text."""
        pass


class TextToSpeechProvider(ABC):
    """Abstract interface for Text-to-Speech audio synthesis."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        language: str = "en-US",
        speech_rate: float = 1.0,
        options: Optional[dict] = None,
    ) -> SynthesisResult:
        """Synthesize text into speech audio bytes."""
        pass
