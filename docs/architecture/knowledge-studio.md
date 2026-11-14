# Knowledge Studio Architecture (M07)

## Ingestion Pipeline & Chunk Architecture

```
[User Document / Web URL]
           │
           ▼
[Format Detection & SSRF Guard] ──> [Tenant Storage Volume]
           │
           ▼
[Parser Registry (PDF/DOCX/HTML/...)]
           │
           ▼
[Extracted Text & Structural Headings]
           │
           ▼
[Chunking Registry (Recursive/Markdown/Token)]
           │
           ▼
[Document Chunk Records] ──> [FTS ts_vector + Embedding Engine]
```

### Components
1. **DocumentRepository & IngestionJobRepository**:
   - Manages documents, versions, jobs, events, and chunks strictly scoped by `tenant_id`.
   - Maintains cryptographic hash (`file_hash`) for duplicate suppression.

2. **Chunk Inspector**:
   - Exposed via `GET /api/v1/documents/{document_id}/chunks`.
   - Returns chunk index, character length, token estimate, page number, heading hierarchy, and chunking strategy.

3. **Storage Abstraction**:
   - Persists raw files in tenant-scoped directories (`data/storage/{tenant_id}/{kb_id}/{doc_id}/`).
