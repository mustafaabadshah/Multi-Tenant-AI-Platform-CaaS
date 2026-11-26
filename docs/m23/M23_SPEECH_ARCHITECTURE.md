# M23 — Speech-to-Text (STT) & Text-to-Speech (TTS) Architecture

## 1. Principles & Design Goals
- **Free-First, Zero-Infrastructure Baseline**: All end-user voice capabilities (dictation, listening aloud, voice conversation) are implemented using standard W3C Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition` and `SpeechSynthesis`).
- **No Mandatory Paid Speech Services**: Default operation requires zero paid credits, zero external speech API tokens, and zero always-on GPU workers.
- **Provider Abstraction**: Extensible Python backend provider interfaces (`SpeechToTextProvider`, `TextToSpeechProvider`) decouple application business logic from physical speech backends.
- **Deterministic Mock Provider**: `MockSpeechProvider` generates standards-compliant RIFF/WAVE PCM audio headers and deterministic transcripts for automated regression suites.

## 2. Speech Component Architecture

```
   ┌────────────────────────────────────────────────────────┐
   │                   Frontend Browser                     │
   │  ┌──────────────────────┐    ┌──────────────────────┐  │
   │  │ Web Speech STT       │    │ Web Speech TTS       │  │
   │  │ (SpeechRecognition)  │    │ (SpeechSynthesis)    │  │
   │  └──────────┬───────────┘    └──────────▲───────────┘  │
   │             │                           │              │
   │             ▼                           │              │
   │      [Editable Input]         [cleanTextForSpeech]     │
   └─────────────┼───────────────────────────┼──────────────┘
                 │                           │
                 │ POST /messages/stream     │
                 ▼                           │
   ┌─────────────────────────────────────────┴──────────────┐
   │                FastAPI Backend (CaaS)                  │
   │                                                        │
   │  ┌──────────────────────┐    ┌──────────────────────┐  │
   │  │ SpeechService        │    │ AssistantRuntime     │  │
   │  │ - Audio Validation   │    │ - RAG                │  │
   │  │ - MockSpeechProvider │    │ - MCP Tools          │  │
   │  │ - Quota & Prefs      │    │ - Citations & SSE    │  │
   │  └──────────────────────┘    └──────────────────────┘  │
   └────────────────────────────────────────────────────────┘
```

## 3. Safe Speech-Text Sanitization (`cleanTextForSpeech`)
Reading raw markdown aloud leads to a confusing listening experience. The client-side sanitizer systematically cleanses:
1. Markdown code blocks (` ```...``` `) -> replaced with " [code block omitted] "
2. Inline code (` `...` `) -> unwrapped to inner code text
3. Markdown links (` [text](url) `) -> stripped to just the title
4. Standalone URLs (` http://... `) -> stripped entirely
5. Numbered citations (` [1] `, ` [2, 3] `) -> stripped
6. Header markers (` ### `, ` ** `, ` _ `, ` ~~ `) -> stripped
7. Markdown tables and dividers -> normalized to natural sentence breaks

## 4. Backend Speech Endpoints
- `POST /api/v1/speech/transcribe`: Multi-part audio transcription endpoint with 15 MB audio payload cap and MIME validation.
- `POST /api/v1/speech/synthesize`: Text synthesis endpoint returning audio/wav streams.
- `GET /api/v1/speech/voices`: Discovers supported provider voices and capabilities.
- `GET /api/v1/speech/preferences`: Fetches current user voice settings.
- `PUT /api/v1/speech/preferences`: Persists mode, rate, auto-read, and language preferences.
