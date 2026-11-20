# M28.13 Ingestion & Retrieval End-to-End Audit

**Milestone:** M28.13 — Critical Knowledge Base Data Integrity, Assistant-KB Routing, Refresh Loop, Back Navigation & End-to-End Reliability  
**Date:** November 19, 2026  
**Status:** AUDITED AND VERIFIED  

---

## 1. Complete Document Ingestion Lifecycle

```mermaid
flowchart TD
    A[Chat Studio Attachment Upload] -->|POST /attachments| B[ConversationAttachment Record]
    B -->|B2 / Local Disk| C[Raw Stored File]
    B -->|Save to Knowledge| D{Destination Routing Policy}
    D -->|Single Connected KB| E[Pre-select Connected KB]
    D -->|Multiple / None| F[Require Explicit Selection]
    E --> G[POST /attachments/{id}/promote]
    F --> G
    G --> H[Verify Tenant & Target KB]
    H --> I[Create Document Record]
    I --> J[Mark Attachment is_promoted=True]
    J --> K[Dispatch Ingestion Task]
    K --> L[Parse PDF / TXT / HTML / DOCX]
    L --> M[Generate Chunks & Page Metadata]
    M --> N[Generate Embeddings via OmniRoute / Local]
    N --> O[Persist in document_chunks Table]
    O --> P[Update Document Status to READY]
```

---

## 2. Ingestion State Machine Integrity

1. **`QUEUED`**: Document created in database; job dispatched. Polling runs every 4 seconds.
2. **`PROCESSING`**: Parser extracts text, computes page bounds, and chunks content. Polling continues.
3. **`READY`**: All chunks and embeddings are persisted in `document_chunks`. Polling halts immediately.
4. **`FAILED`**: Parser or database encountered an unrecoverable error. Detailed error logged, status marked `FAILED`. Polling halts immediately.

### Reprocess Contract
- Reprocessing wipes existing chunks for that document and resets status to `QUEUED`.
- Vector embeddings and chunk records are regenerated idempotently.

---

## 3. Retrieval Scoping & Tenant Isolation

During chat runtime (`ChatService` & `RagService`):
1. **Assistant Scoping**: The assistant specifies allowed Knowledge Base IDs (`assistant.connected_kb_ids`).
2. **Tenant Scoping**: All SQL vector queries explicitly include `WHERE tenant_id = :tenant_id AND knowledge_base_id IN (:allowed_kb_ids)`.
3. **Relational Guardrails**: Even if a document chunk has high vector similarity to a query, if its `knowledge_base_id` is not in the assistant's connected list, the query filter eliminates it prior to vector scoring.
4. **Cross-Tenant Prevention**: Documents in other tenants cannot be indexed or queried under any circumstance.
