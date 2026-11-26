# M22 — Document Security & Multi-Tenant Isolation

## 1. Security Prime Directive
All conversation attachments and their extracted chunks are private, tenant-isolated assets. No user from Tenant B may ever inspect, search, download, or promote a document belonging to Tenant A, even if they guess or spoof the attachment UUID or conversation UUID.

## 2. Threat Vector Analysis & Safeguards

### Vector 1: Cross-Tenant Attachment Snooping / Downloading
- **Threat**: Attacker in Tenant B attempts `GET /api/v1/conversations/{conv_A}/attachments/{att_A}/download`.
- **Mitigation**:
  1. The API route verifies that `conv_A` exists and has `tenant_id == active_user_tenant_id`.
  2. The service enforces `WHERE id = att_A AND conversation_id = conv_A AND tenant_id = active_user_tenant_id`.
  3. Failure returns strict `404 Not Found`.

### Vector 2: Cross-Tenant Knowledge Base Promotion (Tampering)
- **Threat**: Attacker in Tenant B tries to promote an attachment from Tenant A into Tenant B's Knowledge Base, or promote their own attachment into Tenant A's Knowledge Base.
- **Mitigation**:
  - `ConversationAttachmentService.promote_to_knowledge_base` verifies:
    1. Active tenant matches `attachment.tenant_id`.
    2. Active tenant matches `knowledge_base.tenant_id`.
    3. User has active membership in the tenant.
  - Cross-tenant requests are denied immediately with `404 Not Found` (fail-closed, no existence leakage).

### Vector 3: Cross-Conversation Document Bleed
- **Threat**: A document attached in Conversation 1 appears in the RAG retrieval context of Conversation 2.
- **Mitigation**:
  - `ConversationAttachmentService.search_attachments` filters explicitly by `conversation_id == active_conversation_id`.
  - Chunks from Conversation 1 are excluded from SQL query results during assistant chat in Conversation 2.

### Vector 4: Malicious File Payloads & Traversal
- **Threat**: Uploading executable binaries, scripts disguised as PDFs, or path-traversal filenames (`../../etc/passwd`).
- **Mitigation**:
  - Filenames are sanitized with `re.sub(r"[^a-zA-Z0-9_.-]", "_", file.filename)`.
  - File extension and MIME type allowlists strictly enforced.
  - File size capped at 15 MB.
  - Files are stored in partitioned, non-executable private B2 object storage keys.

## 3. Automated Security Verification
- `tests/test_m22_conversation_attachments.py` verifies:
  - Positive attachment lifecycle (upload, chunking, search).
  - Cross-tenant upload isolation.
  - Cross-tenant retrieval isolation.
  - Cross-tenant KB promotion denial.
- `tests/test_m25_security_regression.py` confirms:
  - Unauthorized deletion blocked.
  - Cross-tenant cross-referencing rejected.
