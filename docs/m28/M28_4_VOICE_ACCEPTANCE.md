# M28.4 Voice Chat Reliability & Acceptance

## 1. Overview & Architectural Principles

Voice interactions in the Multi-Tenant AI Platform must be resilient, accessible, and non-blocking. The voice stack uses zero paid third-party voice APIs, relying on native browser Web Speech APIs (`SpeechRecognition` / `webkitSpeechRecognition` and `SpeechSynthesis`) for client-side transcription and text-to-speech.

## 2. Voice Modes & Reliability Criteria

### 2.1 Dictation Mode (Speech-to-Text Input)
- **Activation:** Clicking the microphone icon initiates continuous speech recognition with `interimResults = true`.
- **Interim Feedback:** Real-time interim transcript display ensures the user receives visual feedback while speaking.
- **Commit & Fallback:** Finalized transcripts populate the message textarea with the user retaining full ability to edit before sending.
- **Microphone Permissions:** Clean error handling for `not-allowed`, `no-speech`, and `service-not-allowed` without unhandled exceptions or app freeze.

### 2.2 Auto-Read Mode (Text-to-Speech Output)
- **Automatic Narration:** When enabled, assistant response completion triggers `window.speechSynthesis.speak()`.
- **User Interruption:** Clicking anywhere, pressing any key, or clicking "Stop Speaking" calls `window.speechSynthesis.cancel()`, immediately silencing output.
- **Approval Interruption:** If an assistant requires tool approval or execution confirmation, TTS automatically halts to allow human review.

### 2.3 2-Turn Voice Cycle Test
The automated and interactive voice workflow verifies:
1. User dictates query: *"What are the key findings in the uploaded quarterly report?"*
2. System transcribes and submits query.
3. Assistant streams response.
4. Auto-read speaks response until completion or user pause.
5. User provides follow-up question via voice.
6. Assistant streams contextual second-turn answer.

## 3. Degradation & Graceful Handling

If the browser does not support Web Speech API or microphone hardware is denied:
- Microphone and Speaker controls display subtle disabled states with assistive tooltip explanations (`"Voice input not supported on this browser"`).
- Standard keyboard input and text display remain 100% functional.
