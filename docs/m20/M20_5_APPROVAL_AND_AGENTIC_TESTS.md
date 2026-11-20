# M20.5 — Approval & Agentic SSE Execution Report

| Scenario | Target Endpoint | Event / Protocol | Expected Result | Live Staging Evidence | Status |
|---|---|---|---|---|---|
| **SSE-01** | Conversation Creation | `POST /api/v1/conversations` | Assistant conversation initialized | 201 Created (`1117fd52-0cbd-44f9-8c5f-97553bf526f1`) | **PASS** |
| **SSE-02** | SSE Message Streaming | `POST .../messages/stream` | Server-Sent Events emitted in order | 33 events received: `message_start`, `retrieval_start`, `retrieval_complete`, `token` (x28), `usage`, `message_complete` | **PASS** |
| **SSE-03** | Mock Provider Guard | Assistant LLM runtime | Zero commercial LLM API costs | Verified: `provider=mock`, estimated cost $0.00 | **PASS** |
| **APPR-01** | Approval Model Schema | Alembic `0015` | `tool_approvals` table structure | Schema verified in PostgreSQL 16 | **PASS** |
| **APPR-02** | Single-Use Consumption | `POST /api/v1/approvals/{id}/respond` | Idempotent token, replay rejected | Verified via local test suite & API security review | **PASS** |
| **APPR-03** | Direct Tester Guard | `POST /api/v1/tools/{id}/execute` | Require admin permissions for mutating tools | Verified in Phase C hardening & regression suite | **PASS** |

---

## 1. Agentic Streaming Event Stream Verification

Streaming output from `https://mmaip-backend.onrender.com/api/v1/conversations/1117fd52-0cbd-44f9-8c5f-97553bf526f1/messages/stream`:
```text
event: message_start
event: retrieval_start
event: retrieval_complete
event: token
... (28 token chunks streamed)
event: usage
event: message_complete
```
Total events received: 33 events. No connection drops or timeouts.

## 2. In-Chat Human Approval Guarantee

The runtime guarantees:
- An LLM cannot self-authorize write-like or mutating actions.
- Any tool flagged with `requires_approval=True` or `risk_level in ('WRITE', 'HIGH_RISK')` emits `tool_approval_required` and pauses assistant execution until explicitly authorized by a tenant administrator.
- Replaying or submitting duplicate approvals returns `400 Bad Request (Approval already resolved)`.
