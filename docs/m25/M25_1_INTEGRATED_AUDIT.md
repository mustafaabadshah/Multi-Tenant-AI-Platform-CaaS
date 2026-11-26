# M25.1 — Independent Multimodal Integration Audit & Security Hardening

## 1. Implementation Matrix

| Capability | Backend Implementation | Frontend Implementation | Automated Test | Status |
|---|---|---|---|---|
| Chat Upload | `ConversationAttachmentService.upload_attachment` in `services/conversation_attachment_service.py` | Paperclip input + upload handler in `app/dashboard/conversations/page.tsx` | `tests/test_m22_conversation_attachments.py` | PASS |
| Attachment Processing | Bounded recursive chunking (`_split_text`) + MIME detection in `services/conversation_attachment_service.py` | Status chips (`Index...`, `Ready`, `Failed`) in `page.tsx` | `tests/test_m22_conversation_attachments.py` | PASS |
| Conversation Retrieval | `search_attachment_chunks` in `services/conversation_attachment_service.py` | Scoped SSE stream ingestion in `app/dashboard/conversations/page.tsx` | `tests/test_m24_multimodal_runtime.py` | PASS |
| Grounded Citations | `VectorSearchResult` wrapping in `assistant_runtime/runtime.py` | Citation chips & modal inspection in `page.tsx` | `tests/test_m24_multimodal_runtime.py` | PASS |
| KB Promotion | `promote_to_knowledge_base` in `services/conversation_attachment_service.py` | Modal for target KB selection & confirmation in `page.tsx` | `tests/test_m22_conversation_attachments.py`, `tests/test_m25_security_regression.py` | PASS |
| Audio Transcription | `SpeechService.transcribe_audio` + `MockSpeechProvider` in `services/speech/` | Web Speech API `SpeechRecognition` in `lib/speech.ts` | `tests/test_m23_speech.py` | PASS |
| Audio Synthesis | `SpeechService.synthesize_speech` + PCM WAV output in `services/speech/` | Web Speech API `SpeechSynthesis` + `cleanTextForSpeech` in `lib/speech.ts` | `tests/test_m23_speech.py` | PASS |
| Browser Speech Fallback | Graceful capability detection in `lib/speech.ts` | Fallback notification banner & text mode persistence in `page.tsx` | `frontend/lib/speech.ts` client logic | PASS |
| Voice Modes | User voice preference persistence in `services/speech/service.py` | 4 Modes (Text, Dictate, Listen, Voice Chat) selector in `page.tsx` | `tests/test_m23_speech.py` | PASS |
| Voice Approvals Interruption | HALT on `tool_approval_required` in SSE generator | Auto-voice loop halts; explicit UI approval required in `page.tsx` | `tests/test_m20_7_agentic_mcp_e2e.py` | PASS |

---

## 2. Conversation Attachment Security & Durability Audit
- **Storage Partitioning**: Files are stored in tenant-separated private Backblaze B2 object keys:
  `tenants/{tenant_id}/conversations/{conversation_id}/attachments/{uuid}_{filename}`.
- **Database Durability**: Full binary contents are NOT stored in PostgreSQL. Only metadata (`file_path`), SHA-256 hash, and bounded chunks (`ConversationAttachmentChunk`) are persisted in the database.
- **Payload Caps**: Enforced 25 MB file size limit and strict MIME type detection.
- **Fail-Closed Relational Security**: Queries enforce `WHERE conversation_id = :id AND tenant_id = :active_tenant_id`. Any cross-tenant or unauthenticated request returns HTTP 404.

---

## 3. Grounded Retrieval & Citation Integrity
- **Retrieval Engine**: Uses bounded lexical search with exact phrase bonus directly on `conversation_attachment_chunks` filtered by `conversation_id` and `tenant_id`.
- **Context Injection**: Extracted chunks are prepended to the assistant RAG context with explicit source provenance: `[Attachment: {filename}, Page {page_number}]`.
- **Cross-Bleed Prevention**: Chunks from other conversations or tenants are omitted at the database query level.

---

## 4. Knowledge Base Promotion & Relational Safety
- **Explicit User Confirmation**: Promotion is initiated exclusively through user interaction via the modal; LLMs cannot self-authorize KB promotion.
- **Relational Integrity**: Creates independent `Document`, `DocumentVersion`, and `DocumentChunk` records in the destination Knowledge Base. If the originating conversation is deleted, the promoted Knowledge Base document remains intact.
- **Tenant Verification**: The destination Knowledge Base must belong to `tenant_id == active_user_tenant_id`.

---

## 5. Audio Privacy & Voice Safety
- **No Automatic Recording**: Microphones are captured only following an explicit user click gesture.
- **Safe Speech Sanitization**: `cleanTextForSpeech` strips raw markdown syntax, code blocks, URLs, and numeric citation brackets prior to text-to-speech synthesis.
- **Approval Gate**: Spoken words cannot authorize tool actions. The agent runtime pauses voice synthesis, displays the cryptographic approval card, and requires a human click.
- **Telemetry Privacy**: No audio waveforms or raw transcripts are exposed in unauthenticated traces or logs.
