# M27.6 — Saving Web Sources to Knowledge Base

## 1. Storage Modes & Rights Protection

Users must be able to promote valuable web discoveries into shared Knowledge Bases. However, copying arbitrary third-party website text into a shared database raises copyright and storage issues.

M27 supports two explicit storage modes via `WebKBSaveService` in [kb_saver.py](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/services/web/kb_saver.py):

| Storage Mode | What is Persisted | Searchable Full-Text Chunks | Use Case & Rights Handling |
|---|---|---|---|
| **`REFERENCE` (Default)** | Document metadata: Title, Canonical URL, Domain, User Notes, Retrieval Timestamp, Content Hash | **No** (0 chunks created) | **Safe by default.** Bookmarks public resources without copying third-party copyright content. |
| **`FULL_CONTENT`** | Document metadata + full extracted text chunked and indexed into `DocumentVersion` and `DocumentChunk` | **Yes** (Chunked into ~1000 character blocks for Hybrid RAG) | For company documentation, public domain specifications, or content where full indexing is authorized. |

---

## 2. Model Reuse: Zero Database Migrations

The platform reuses existing SQLAlchemy models:
- **`Document`**:
  - `filename`: Page title (or custom title provided by user)
  - `safe_filename`: Sanitized filename (`web_<hash>.html`)
  - `file_path`: Canonical URL (`https://...`)
  - `mime_type`: `text/html`
  - `status`: `PROCESSED`
  - `metadata_json`:
    ```json
    {
      "source_type": "web",
      "source_url": "https://www.w3schools.com/cpp/cpp_for_loop.asp",
      "domain": "www.w3schools.com",
      "storage_mode": "REFERENCE",
      "notes": "User notes",
      "user_id": "...",
      "created_at": "2026-11-17T07:45:00.000Z"
    }
    ```
- **`DocumentVersion`**: Stores version 1, content hash, and extracted text/notes.
- **`DocumentChunk`**: Created only in `FULL_CONTENT` mode with `chunking_strategy="web_source"`.

---

## 3. Human Approval & Safety Boundary

Because saving to a shared Knowledge Base is a mutating action:
1. `web_save_to_kb` is defined in [builtin.py](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/services/tools/builtin.py) with:
   - `risk_level = "WRITE"`
   - `requires_approval = True`
2. When the LLM calls `web_save_to_kb`, the platform triggers the existing `ToolApprovalService` workflow. The user is presented with a Human-in-the-Loop approval card in chat.
3. The LLM **cannot self-authorize** permanent shared Knowledge Base writes without explicit user confirmation.
4. Cross-tenant writes are strictly rejected with authorization errors.
