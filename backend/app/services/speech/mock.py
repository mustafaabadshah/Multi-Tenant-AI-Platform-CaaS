"""Deterministic Mock Speech Provider for local execution and test suites."""

import struct
from typing import Optional

from app.services.speech.base import (
    SpeechToTextProvider,
    SynthesisResult,
    TextToSpeechProvider,
    TranscriptionResult,
)


def create_mock_wav(duration_seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Generate a valid, minimal PCM 16-bit mono WAV byte sequence."""
    num_samples = int(sample_rate * duration_seconds)
    data_size = num_samples * 2  # 16-bit = 2 bytes per sample
    file_size = 36 + data_size

    # RIFF header
    header = bytearray()
    header.extend(b"RIFF")
    header.extend(struct.pack("<I", file_size))
    header.extend(b"WAVE")

    # fmt subchunk (16 bytes PCM)
    header.extend(b"fmt ")
    header.extend(struct.pack("<I", 16))  # Subchunk1Size
    header.extend(struct.pack("<H", 1))   # AudioFormat (1 = PCM)
    header.extend(struct.pack("<H", 1))   # NumChannels (1 = Mono)
    header.extend(struct.pack("<I", sample_rate))  # SampleRate
    header.extend(struct.pack("<I", sample_rate * 2))  # ByteRate
    header.extend(struct.pack("<H", 2))   # BlockAlign
    header.extend(struct.pack("<H", 16))  # BitsPerSample

    # data subchunk
    header.extend(b"data")
    header.extend(struct.pack("<I", data_size))

    # Silence samples (zeroes)
    samples = bytearray(data_size)
    return bytes(header + samples)


class MockSpeechProvider(SpeechToTextProvider, TextToSpeechProvider):
    """Deterministic, CPU-only Speech provider requiring zero external cloud dependencies."""

    def __init__(self, default_transcript: str = "Hello, this is a simulated voice message."):
        self.default_transcript = default_transcript
        self.transcribe_call_count = 0
        self.synthesize_call_count = 0

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str,
        language: str = "en-US",
        options: Optional[dict] = None,
    ) -> TranscriptionResult:
        """Simulate Speech-to-Text transcription with deterministic accuracy."""
        self.transcribe_call_count += 1

        # If audio payload embeds a text signature, extract it for custom test scenarios
        transcript = self.default_transcript
        if b"TEST_TRANSCRIPT:" in audio_bytes:
            try:
                start = audio_bytes.find(b"TEST_TRANSCRIPT:") + len(b"TEST_TRANSCRIPT:")
                end = audio_bytes.find(b"\n", start)
                if end == -1:
                    end = len(audio_bytes)
                extracted = audio_bytes[start:end].decode("utf-8", errors="ignore").strip()
                if extracted:
                    transcript = extracted
            except Exception:
                pass

        return TranscriptionResult(
            transcript=transcript,
            confidence=0.98,
            language=language,
            duration_seconds=max(0.5, len(audio_bytes) / 32000.0),
            metadata={"mock": True, "call_index": self.transcribe_call_count},
        )

    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None,
        language: str = "en-US",
        speech_rate: float = 1.0,
        options: Optional[dict] = None,
    ) -> SynthesisResult:
        """Simulate Text-to-Speech audio generation, returning valid WAV bytes."""
        self.synthesize_call_count += 1
        duration = max(0.5, len(text) * 0.05 / max(0.1, speech_rate))
        wav_bytes = create_mock_wav(duration_seconds=duration)

        return SynthesisResult(
            audio_bytes=wav_bytes,
            mime_type="audio/wav",
            character_count=len(text),
            duration_seconds=duration,
            voice_used=voice or "mock-natural-en",
        )
