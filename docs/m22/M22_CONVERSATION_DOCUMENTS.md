# M22 — Conversation Attachments & Document Intelligence

## 1. Overview
Milestone 22 introduces first-class conversation attachments to the Multi-Tenant AI Platform (CaaS). Users can now upload documents (PDF, DOCX, TXT, CSV) directly within an active chat session. These documents are scoped strictly to the conversation, chunked recursively, and made available for grounded retrieval within that chat without leaking to other tenants, conversations, or global knowledge bases.

## 2. Architecture & Data Model

### Database Models
Added to `backend/app/models/conversation.py`:
- `ConversationAttachment`:
  - `id`: UUID (Primary Key)
  - `tenant_id`: UUID (Indexed Foreign Key -> `tenants.id`)
  - `conversation_id`: UUID (Foreign Key -> `conversations.id`)
  - `message_id`: UUID (Optional Foreign Key -> `messages.id`)
  - `uploader_user_id`: UUID (Foreign Key -> `users.id`)
  - `original_filename`: String(255)
  - `content_type`: String(100)
  - `file_size`: Integer
  - `storage_path`: String(500) (Private tenant-scoped B2 storage path)
  - `sha256_hash`: String(64)
  - `status`: String(50) (`UPLOADED`, `PROCESSING`, `READY`, `FAILED`)
  - `extraction_status`: String(50) (`PENDING`, `EXTRACTED`, `EMPTY`, `FAILED`)
  - `chunk_count`: Integer
  - `is_promoted`: Boolean (Default: False)
  - `promoted_knowledge_base_id`: UUID (Optional Foreign Key -> `knowledge_bases.id`)
  - `promoted_document_id`: UUID (Optional Foreign Key -> `documents.id`)
  - `promoted_at`: DateTime(timezone=True)
  - `error_message`: Text

- `ConversationAttachmentChunk`:
  - `id`: UUID (Primary Key)
  - `tenant_id`: UUID (Indexed Foreign Key -> `tenants.id`)
  - `conversation_id`: UUID (Indexed Foreign Key -> `conversations.id`)
  - `attachment_id`: UUID (Foreign Key -> `conversation_attachments.id`)
  - `chunk_index`: Integer
  - `content`: Text
  - `token_count`: Integer
  - `character_count`: Integer
  - `page_number`: Integer (Default: 1)
  - `metadata_json`: JSONB

### Alembic Migration
- Migration `0017_m22_conversation_attachments.py` linearly branches from `0016_m20_2_assistant_tools_config`.
- Creates `conversation_attachments`, `conversation_attachment_chunks`, and `user_voice_preferences` tables with foreign keys and tenant-isolation indices.

## 3. Upload & Extraction Pipeline
- **Validation**: Enforces 15 MB file size limit and MIME allowlist (`application/pdf`, `text/plain`, `text/csv`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`).
- **Storage**: Uploaded bytes are securely stored in the private B2 storage provider partitioned by `tenants/{tenant_id}/conversations/{conversation_id}/attachments/{uuid}_{filename}`.
- **Parsing**: Reuses platform parsers (`TextParser`, `PdfParser`, etc.) via `DocumentParserFactory`.
- **Chunking**: Executes bounded recursive splitting (`_split_text`) with default 500-token chunks and 50-token overlap.
- **Indexing**: Extracts textual chunks into `conversation_attachment_chunks` immediately, marking status as `READY`.

## 4. Chat Retrieval Scope & RAG Integration
- In `AssistantRuntime`, before assembling knowledge context, the runtime executes:
  `conversation_attachment_service.search_attachments(tenant_id, conversation_id, user_prompt, top_k=3)`
- Results are wrapped into `VectorSearchResult` instances and prepended to the knowledge base retrieval results.
- Prompts received by the LLM reference the exact attachment filenames and page numbers, enabling faithful citations.

## 5. Knowledge Base Promotion
- Default policy: attachments remain conversation-scoped.
- Promotion API: `POST /api/v1/conversations/{conversation_id}/attachments/{attachment_id}/promote`.
- Creates a permanent `Document` and `DocumentVersion` in the destination Knowledge Base within the same tenant.
- Marks `is_promoted = True` on the attachment record and logs `promoted_at`.
