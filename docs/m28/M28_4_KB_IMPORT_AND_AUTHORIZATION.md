# M28.4 Knowledge Base Import & Authorization

## 1. Separation of Concerns: Read Now vs. Save to Knowledge Base

A foundational architectural requirement in M28.4 is the strict separation between temporary reading and permanent knowledge base ingestion:
- **"Read Now" (Ephemeral Context):** Web links or attached files fetched during active conversation are held strictly in memory / conversation cache. They are never committed to permanent knowledge bases without explicit user instruction.
- **"Save to Knowledge" (Explicit User Intent):** Requires the user to explicitly open the Save dialog, select a target Knowledge Base owned by their active tenant, and choose a storage mode.

## 2. Storage Modes

The `WebKBSaveService` supports three distinct storage modes:

1. **`REFERENCE` (Metadata Link Only):**
   - Saves document metadata: URL, page title, domain, timestamp.
   - Stores **0 chunks**.
   - Ideal for bookmarking source links without bloating vector storage or chunk indices.

2. **`NOTES` (User Synthesis & Summary):**
   - Chunks and stores only the user's custom notes or synthesis.
   - Creates document chunks from the user's annotations (`chunking_strategy="web_source"`).
   - Allows users to curate key findings without indexing irrelevant webpage boilerplate.

3. **`SEARCHABLE_CONTENT` (Full Extracted Body):**
   - Chunks the full extracted body text using paragraph-aware chunking (up to 1,000 characters per chunk).
   - Stores `page_number=None` to prevent spurious page 1 numbering.
   - Enables semantic retrieval across the entire webpage text during subsequent assistant chats.

## 3. Multi-Tenant Authorization Boundaries

Every save request enforces four strict authorization gates:
1. **Active Tenant Membership:** Authenticated user session must be an active member of `tenant_id`.
2. **Knowledge Base Ownership:** `SELECT * FROM knowledge_bases WHERE id = :kb_id AND tenant_id = :tenant_id`.
3. **Cross-Tenant Rejection:** Any attempt to save a source into a KB owned by Tenant B while authenticated in Tenant A is rejected with HTTP 404/403.
4. **Tenant-Scoped Chunks:** All created `Document` and `DocumentChunk` records carry the composite foreign keys enforcing tenant isolation at the database layer.
