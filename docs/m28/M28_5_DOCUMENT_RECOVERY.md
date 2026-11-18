# M28.5 Safe Recovery Procedure for Failed Existing Documents

## 1. Principles of Safe Document Recovery

Recovery of existing failed documents must be non-destructive, tenant-isolated, and idempotent:
- **Zero Raw File Deletion:** The original object stored in B2 (`tenants/.../C___For_Loop.html`) is preserved untouched.
- **No Document Record Duplication:** Recovery operates on the existing `Document` entity (`c4959352-28b6-423e-a6b4-16a82ccdb334`) and its `DocumentVersion` (`f8a7e7e0-3a36-49fa-8430-c288ec4cbeac`).
- **Audit Preservation:** Historical failure events in `ingestion_job_events` and audit logs remain intact for compliance tracking.
- **In-Flight Conflict Guard:** Duplicate concurrent clicks on Reprocess are rejected with HTTP 409 Conflict.

## 2. Hardened Reprocess Endpoint

The endpoint `POST /api/v1/documents/{document_id}/reprocess` enforces an 8-step safety sequence:

```python
# 1. Authorize tenant access and document ACL
_check_document_acl(doc, ctx)

# 2. Block duplicate in-flight jobs
active_job = await get_active_job(document_id)
if active_job:
    raise HTTPException(409, "An ingestion job is already in progress for this document.")

# 3. Verify latest document version exists
latest_version = await repo.get_latest_version(document_id)
if not latest_version:
    raise HTTPException(400, "Document has no versions to reprocess.")

# 4. Confirm underlying file exists in storage provider
file_exists = await storage.exists(tenant_id, doc.file_path)
if not file_exists:
    raise HTTPException(404, f"Original document file '{doc.filename}' not found in storage.")

# 5. Clean stale partial chunks / embeddings from previous failed attempts
await purge_failed_version_artifacts(db, tenant_id, doc.id, latest_version.id)

# 6. Create ingestion job linked to document_version_id
job = await job_repo.create(
    knowledge_base_id=doc.knowledge_base_id,
    document_id=doc.id,
    document_version_id=latest_version.id,
    status="QUEUED",
    stage="QUEUED",
    progress_pct=10,
    job_metadata={"reprocessed_by": str(user.id), "reprocess_attempt": True},
)
doc.status = "QUEUED"
await db.commit()

# 7. Dispatch background ingestion worker
asyncio.create_task(run_ingestion_in_background(tenant_id, job.id))

# 8. Record audit trail event
await audit_repo.log_event(action="document.reprocess", ...)
```

## 3. Operator Execution Instructions (Post-Deployment)

Once Milestone M28.5 is deployed to Render staging:

1. **Sign in to Staging:** Open `https://mmaip-frontend.onrender.com` and log in with operator credentials for Tenant `a2a0b1e6-51bc-4f68-a03e-19ce03c79f94`.
2. **Navigate to Knowledge Bases:** Select Knowledge Base `faccb980-145c-4606-b6f1-b80f24fa8141`.
3. **Locate Document:** Find `C___For_Loop.html`. Verify that its status displays `FAILED` with 0 chunks.
4. **Inspect Overview:** Click **Inspect**. Note the `Uploaded MIME` is `application/octet-stream` and `Detected Format` indicates `HTML`.
5. **Click Reprocess Document:** Click the **Reprocess Document** button in the modal or the table action column.
6. **Observe Transition:** The document status transitions: `QUEUED` → `PROCESSING` → `READY`.
7. **Verify Outcome:**
   - Generated Chunks: $> 0$ (typically 5–15 chunks).
   - Extracted Characters: $> 0$.
   - Extracted Text tab displays syntax-highlighted C++ loop documentation.
8. **Test Grounded Chat:** Open Assistant Chat, ask *"Explain how the C++ for loop initialization statement works"*, and verify the citation points directly to `C___For_Loop.html`.
