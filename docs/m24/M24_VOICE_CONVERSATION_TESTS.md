# M24 — Voice Conversation & Multimodal Tests

## 1. Automated Integration Tests
Automated multimodal verification is implemented in `backend/tests/test_m24_multimodal_runtime.py`:

### Test Cases
1. `test_assistant_chat_with_conversation_attachment_citations`:
   - Seeds an active tenant, user, assistant, and conversation.
   - Attaches a synthetic policy document ("Refunds are issued within 14 business days").
   - Submits query: "How long do refunds take according to our policy?"
   - Confirms that the assistant response includes attachment retrieval chunks in context and streams valid `token` events.
2. `test_speech_transcript_to_stream_chat`:
   - Submits a simulated audio stream to `POST /api/v1/speech/transcribe`.
   - Obtains recognized transcript ("What is the refund timeline?").
   - Transmits transcript to the streaming conversation endpoint.
   - Verifies the end-to-end speech-to-chat flow produces valid SSE stream output.

## 2. Frontend State Machine & Cleanup
The turn state machine (`IDLE` -> `LISTENING` -> `TRANSCRIBING` -> `THINKING` -> `SPEAKING` -> `IDLE`) ensures:
- No concurrent overlapping microphone recordings.
- Immediate speech cancellation when changing active conversation or logging out.
- Controlled re-entry: voice auto-listening only re-triggers if no approval cards are pending.
