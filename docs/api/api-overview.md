# MM AI Platform — API Overview & Endpoint Reference

**Status:** IMPLEMENTED AND VERIFIED  
**Base URL:** `/api/v1`  
**Authentication:** Bearer JWT Token (`Authorization: Bearer <token>`)  
**Workspace Scoping:** `X-Tenant-ID: <uuid>`

---

## 1. Authentication & Tenant Workspaces

| Method | Endpoint | Description | Permission Required |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Register new user and provision personal/org workspace | None (Public) |
| `POST` | `/api/v1/auth/login` | Authenticate user credentials and issue JWT tokens | None (Public) |
| `POST` | `/api/v1/auth/refresh` | Refresh expired access token using refresh token | None (Public) |
| `GET` | `/api/v1/tenants` | List all workspaces where user has membership | Authenticated |
| `POST` | `/api/v1/tenants/switch` | Switch active workspace context | Authenticated |
| `GET` | `/api/v1/tenants/{tenant_id}` | Retrieve tenant metadata | Member of tenant |

---

## 2. Knowledge Bases & Documents

| Method | Endpoint | Description | Permission Required |
|---|---|---|---|
| `GET` | `/api/v1/knowledge` | List all knowledge bases in active workspace | `KNOWLEDGE_READ` |
| `POST` | `/api/v1/knowledge` | Create a new knowledge base | `KNOWLEDGE_CREATE` |
| `GET` | `/api/v1/knowledge/{kb_id}` | Get knowledge base details | `KNOWLEDGE_READ` |
| `POST` | `/api/v1/documents/upload` | Upload and trigger ingestion for a document | `DOCUMENT_CREATE` |
| `GET` | `/api/v1/documents/{doc_id}` | Get document metadata and status | `DOCUMENT_READ` |
| `DELETE` | `/api/v1/documents/{doc_id}` | Soft-delete document and cascade chunks | `DOCUMENT_DELETE` |
| `GET` | `/api/v1/documents/{doc_id}/versions` | List version history for a document | `DOCUMENT_READ` |
| `POST` | `/api/v1/documents/{doc_id}/reprocess` | Re-run ingestion and chunking | `DOCUMENT_REPROCESS` |

---

## 3. AI Assistants & Conversational Streaming

| Method | Endpoint | Description | Permission Required |
|---|---|---|---|
| `GET` | `/api/v1/assistants` | List configured AI assistants in workspace | `ASSISTANT_READ` |
| `POST` | `/api/v1/assistants` | Create assistant with BYOK model and system prompt | `ASSISTANT_CREATE` |
| `PUT` | `/api/v1/assistants/{asst_id}` | Update assistant configuration | `ASSISTANT_UPDATE` |
| `DELETE` | `/api/v1/assistants/{asst_id}` | Delete an assistant | `ASSISTANT_DELETE` |
| `GET` | `/api/v1/conversations` | List conversation threads | `ASSISTANT_READ` |
| `POST` | `/api/v1/conversations` | Create a new conversation session | `ASSISTANT_READ` |
| `GET` | `/api/v1/conversations/{conv_id}/messages` | Get message history with citations | `ASSISTANT_READ` |
| `POST` | `/api/v1/conversations/{conv_id}/messages/stream` | Stream chat message response via SSE | `ASSISTANT_READ` |

---

## 4. Server-Sent Events (SSE) Protocol

Streaming conversational responses from `/api/v1/conversations/{conv_id}/messages/stream` emit the following sequential frames:

1. `message_start`: Emitted when runtime begins processing.
2. `retrieval_start`: Emitted when hybrid search begins.
3. `retrieval_complete`: Emitted with citation array, page numbers, and bounding boxes.
   ```json
   event: retrieval_complete
   data: {"citation_count": 1, "citations": [{"citation_num": 1, "document_name": "policy.pdf", "page_number": 1, "bounding_box": {"page": 1, "x": 72.0, "y": 90.0, "width": 468.0, "height": 65.0}}]}
   ```
4. `token`: Emitted per generated LLM delta chunk: `data: {"delta": "Hello"}`.
5. `usage`: Emitted with token counts and latency metrics.
6. `message_complete`: Emitted when messages are persisted in PostgreSQL.
