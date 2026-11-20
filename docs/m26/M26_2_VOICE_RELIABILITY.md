# M26.2 — Speech-to-Text, Text-to-Speech & Voice Reliability Report

## 1. Executive Summary
Phase M26.2 audited and hardened the browser-native speech subsystem (Web Speech API) across the four chat interaction modes: Text, Dictation, Listen, and Voice Conversation.

---

## 2. Voice State Machine & Turn-Taking Architecture

### States & Transitions
- `IDLE`: Microphone inactive, synthesis quiet.
- `LISTENING`: Microphone listening for speech input.
- `TRANSCRIBING`: Processing interim and final speech recognition results.
- `THINKING`: User turn submitted; assistant SSE stream in flight.
- `WAITING_FOR_APPROVAL`: SSE emitted `tool_approval_required`; voice loop paused.
- `SPEAKING`: Text-to-Speech reading assistant response aloud.
- `PAUSED`: User explicitly paused playback.
- `ERROR`: Speech recognition or synthesis error encountered.

### Hardened Safeguards Implemented
1. **Duplicate Submission Prevention:** Introduced `isSubmittingVoiceRef` guard in `frontend/app/dashboard/conversations/page.tsx`. Only one submission occurs per final utterance, preventing rapid duplicate message emissions.
2. **Acoustic Feedback Loop Prevention:** When assistant text is read aloud in `LISTEN` or `VOICE_CONVERSATION` mode, `speechRecognizerRef.current?.stop()` is explicitly called prior to synthesis playback. The assistant's own voice cannot be picked up as user speech.
3. **Conversation Switch Cleanup:** Switching active conversations immediately invokes `synthesizer.cancel()` and `recognizer.stop()`, preventing audio playback or capture from leaking across conversations.
4. **Unmount & Navigation Cleanup:** Navigating away from the conversation workspace aborts microphone capture and cancels speech synthesis.

---

## 3. Speech Text Sanitization (`cleanTextForSpeech`)
Before sending text to `window.speechSynthesis`, markdown artifacts are cleaned:
- Fenced code blocks (` ```...``` `) are omitted with a brief auditory cue: `[code block omitted]`.
- Inline code (` `code` `) stripped of backticks.
- Markdown links (`[text](url)`) read the anchor text only.
- Standalone URLs are removed.
- Numbered citations (`[1]`, `[2, 3]`) are removed.
- Asterisks (`**`, `*`), markdown headers (`#`), and table dividers (`|`, `---`) are removed.
- Tested and verified in `backend/tests/test_m26_multimodal_hardening.py::test_clean_text_for_speech_sanitization`.

---

## 4. Multilingual & Browser Compatibility Matrix
| Platform / Browser | Speech Recognition (STT) | Speech Synthesis (TTS) | Supported Languages | Fallback Behavior |
|---|---|---|---|---|
| **Google Chrome (Desktop)** | Native (`webkitSpeechRecognition`) | Native (`speechSynthesis`) | en-US, ur-PK (if installed) | Standard text input |
| **Microsoft Edge (Desktop)** | Native (`webkitSpeechRecognition`) | Native (`speechSynthesis`) | en-US, ur-PK | Standard text input |
| **Mozilla Firefox (Desktop)** | Not Supported by default | Native (`speechSynthesis`) | System voices | Dictation disabled; Text mode fallback |
| **Apple Safari (macOS/iOS)** | Native (`webkitSpeechRecognition`) | Native (`speechSynthesis`) | en-US, es, fr, etc. | Standard text input |

*Note:* Browser speech recognition in Chromium browsers relies on browser network speech services. Offline recognition is not guaranteed. When recognition is unavailable or denied, the UI displays clear guidance and falls back to standard text input.
