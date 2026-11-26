# M28.1 — In-App Message Feedback Technical Report

**Milestone:** M28.1  
**Project:** Multi-Tenant AI Platform (CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Repository:** `https://github.com/mustafaabadshah/Multi-Tenant-AI-Platform-CaaS`  
**Date:** November 17, 2026  
**Status:** IMPLEMENTED & TESTED (PASS)  

---

## 1. Overview & Architectural Rationale

M28.1 implements in-app assistant message feedback for the private beta quality management layer. The requirement is to allow beta users to submit structured qualitative evaluations on assistant responses (Thumbs Up / Thumbs Down, category tags, optional bounded comments) with strict tenant isolation, idempotency, and non-destructive rating updates.

### Migration & Data Model Decision
An inspection of existing models confirmed that `Message.metadata_` is an untyped JSON dictionary that cannot reliably enforce:
- Foreign key integrity to the rating user and assistant.
- Database-level unique constraint (`one active rating per user per message`).
- Efficient indexing for workspace telemetry and aggregate queries.
- Auditable review status lifecycle (`NEW` → `REVIEWED` → `ACTIONED` → `CLOSED`).

Therefore, a dedicated relational entity `MessageFeedback` was introduced in `backend/app/models/conversation.py`, accompanied by a linear additive Alembic migration `backend/alembic/versions/0018_m28_message_feedback.py` (revising `0017_m22_conversation_attachments`).

---

## 2. Relational Schema: `message_feedback`

| Column | Type | Constraints / Description |
|---|---|---|
| `id` | `UUID` | Primary Key, default `gen_random_uuid()` |
| `tenant_id` | `UUID` | Foreign Key to `tenants.id` (ON DELETE CASCADE), Indexed |
| `conversation_id` | `UUID` | Foreign Key to `conversations.id` (ON DELETE CASCADE), Indexed |
| `message_id` | `UUID` | Foreign Key to `messages.id` (ON DELETE CASCADE), Indexed |
| `assistant_id` | `UUID` | Nullable Foreign Key to `assistants.id` (ON DELETE SET NULL), Indexed |
| `user_id` | `UUID` | Foreign Key to `users.id` (ON DELETE CASCADE), Indexed |
| `rating` | `VARCHAR(16)` | Enum: `THUMBS_UP`, `THUMBS_DOWN`, NOT NULL |
| `category` | `VARCHAR(32)` | Enum: `ACCURACY`, `HALLUCINATION`, `HELPFULNESS`, `INCOMPLETE`, `TONE`, `OTHER`, Nullable |
| `comment` | `TEXT` | Bounded comment (max 1000 characters), Nullable |
| `status` | `VARCHAR(16)` | Workflow state: `NEW`, `REVIEWED`, `ACTIONED`, `CLOSED`, default `NEW` |
| `created_at` | `TIMESTAMPTZ` | Timestamp with timezone, UTC |
| `updated_at` | `TIMESTAMPTZ` | Timestamp with timezone, UTC |

### Unique Constraint
```sql
CONSTRAINT uq_message_feedback_user UNIQUE (message_id, user_id)
```
Enforces that a user can have at most one rating per message. Any subsequent submission by the same user updates the existing feedback record rather than creating duplicates.

---

## 3. Feedback API Endpoints

All endpoints are registered under `/api/v1/conversations`:

### 1. `POST /api/v1/conversations/{conversation_id}/messages/{message_id}/feedback`
- **Permissions:** Active tenant membership + `CONVERSATION_READ`
- **Request Body:**
  ```json
  {
    "rating": "THUMBS_DOWN",
    "category": "HALLUCINATION",
    "comment": "Assistant cited facts not present in provided corporate document."
  }
  ```
- **Validation Rules:**
  - Authenticated user ID is derived strictly from server JWT context, not request body.
  - Verifies `conversation.tenant_id == active_tenant_id` (404/403 on mismatch).
  - Verifies `message.conversation_id == conversation_id` (404 on mismatch).
  - Only `MessageRole.ASSISTANT` messages can receive feedback (400 Bad Request on user messages).
  - Category must be one of `ACCURACY`, `HALLUCINATION`, `HELPFULNESS`, `INCOMPLETE`, `TONE`, `OTHER`.
  - Comment length bounded to 1000 characters.
  - Upsert semantics: If user already submitted feedback on this message, updates rating/category/comment and sets `updated_at`.
- **Response:** 201 Created (or 200 OK on update) returning serialized `MessageFeedbackResponse`.

### 2. `GET /api/v1/conversations/{conversation_id}/messages/{message_id}/feedback`
- Returns current user's submitted feedback on the message, or `null` if unrated.

### 3. `GET /api/v1/conversations/feedback/stream`
- **Permissions:** Admin / Owner (`CONVERSATION_MANAGE`)
- Supports filtering by `rating`, `category`, `status`, and `assistant_id`.
- Scoped strictly to active tenant.
- Returns list of feedback items with redacted context for operator review.

### 4. `GET /api/v1/conversations/feedback/telemetry`
- **Permissions:** Admin / Owner (`CONVERSATION_MANAGE`)
- Calculates accurate real-time aggregates:
  - `total_feedback_count`
  - `positive_feedback_count`
  - `negative_feedback_count`
  - `satisfaction_rate`: `(positive / total) * 100` (rounded to 1 decimal place; `null` if 0 ratings)
  - `category_breakdown`: Key-value counts of tags
  - `is_sparse_sample`: `true` if `total_feedback_count < 5` (flags low-sample warnings)
  - Unrated messages are NEVER counted as positive.

### 5. `PATCH /api/v1/conversations/feedback/{feedback_id}/status`
- **Permissions:** Admin / Owner (`CONVERSATION_MANAGE`)
- Allows transitions: `NEW` → `REVIEWED` → `ACTIONED` → `CLOSED`.
- Scoped strictly to active tenant.

---

## 4. Frontend Feedback Controls

Integrated directly into `frontend/app/dashboard/conversations/page.tsx` shared message bubbles:
1. **Compact inline actions:** Thumbs Up and Thumbs Down buttons placed beneath assistant messages.
2. **Interactive selection:** Clicking Thumbs Down expands an inline category picker (Accuracy, Hallucination, Incomplete, Tone, Helpfulness, Other) and an optional feedback text input.
3. **Optimistic & Safe Submission:** Submissions send non-blocking asynchronous requests, display visual loading state, and show a confirmation pill ("Feedback recorded") upon success.
4. **Persisted Ratings:** Reloading or reopening a conversation fetches the current user's feedback and restores the selected state.
5. **Accessibility:** Proper `aria-label` tags, SVG icons, and hover styling consistent with Linear × Apple Notes design principles.

---

## 5. Security & Verification Evidence

All 6 unit tests in `backend/tests/test_m28_message_feedback.py` passed:
- `test_submit_thumbs_up_feedback`: Verified 201 Created and database persistence.
- `test_update_feedback_idempotent`: Verified upsert semantics and constraint compliance.
- `test_feedback_on_user_message_rejected`: Verified 400 rejection when attempting to rate user inputs.
- `test_cross_tenant_feedback_denied`: Verified 404/403 tenant isolation boundary.
- `test_feedback_telemetry_accuracy`: Verified mathematical calculation of positive percentage and category breakdown without fabrication.
- `test_admin_feedback_stream_and_status_lifecycle`: Verified review status workflow.

**Verdict:** `M28_1_FEEDBACK = PASS`
