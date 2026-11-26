# M26.3 — Multimodal Agentic Runtime, Approvals & Security Report

## 1. Executive Summary
Phase M26.3 verified that all multimodal interaction modes (Text, Dictation, Listen, Voice Conversation, Document Attachments) route strictly through the unified `AssistantRuntime` pipeline without authorization shortcuts, approval bypasses, or cross-tenant leakage.

---

## 2. Unified Runtime Authorization
Every interaction (textual or spoken) hits the standard authenticated endpoint:
`POST /api/v1/conversations/{conversation_id}/messages/stream`
- **Tenant Isolation:** Enforced via `X-Tenant-ID` dependency and active membership verification.
- **User Ownership:** Non-admin users are restricted to conversations where `conv.user_id == current_user.id`.
- **Soft-Delete Guard:** Soft-deleted conversations return HTTP 404 and reject all incoming messages and attachment operations.
- **Context Construction:** `build_rag_context` budget-allocates tokens between conversation attachments and Knowledge Base chunks.

---

## 3. Human-in-the-Loop Tool Approvals
- **Durable Approval Tokens:** Any tool marked `requires_approval=True` halts assistant execution and generates a cryptographically signed approval record.
- **SSE Pause:** Emits `tool_approval_required` event over SSE with tool name, execution arguments, and expiry.
- **Voice Interruption:** In `VOICE_CONVERSATION` mode, speech synthesis reads the explanation and pauses. Spoken confirmation cannot execute mutating tools; execution strictly requires explicit user confirmation via the UI approval dialog.
- **Single-Use Consumption:** Approvals are consumed once in PostgreSQL with atomic state transition (`PENDING` -> `APPROVED` / `REJECTED`).

---

## 4. Prompt Injection & Boundary Security
- **Untrusted Input Wrapping:** Document and attachment chunks are passed through `sanitize_untrusted_content`, stripping delimiter markers and neutralizing fake instruction headers (`[UNTRUSTED_HEADER: SYSTEM]: `).
- **System Prompt Integrity:** Assistant system instructions reside in a separate high-priority context block that cannot be superseded by retrieved context or user transcripts.

---

## 5. Security Test Evidence
- `backend/tests/test_m26_multimodal_hardening.py::test_sanitize_untrusted_content_prompt_injection` -> PASSED
- `backend/tests/test_m26_multimodal_hardening.py::test_cross_tenant_attachment_access_denied` -> PASSED
- `backend/tests/test_m25_security_regression.py` (3 security tests) -> PASSED
- `backend/tests/test_tenant_isolation_security.py` -> PASSED
- `backend/tests/test_retrieval_security.py` -> PASSED
