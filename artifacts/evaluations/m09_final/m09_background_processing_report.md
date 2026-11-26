# Milestone M09 — Stage 5: Durable Background Processing & Recovery Report

**Project:** Multi-Tenant AI Assistant Platform / Chatbot-as-a-Service (CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Execution Date:** 2026-11-10  
**Status:** **PASS**

---

## 1. Executive Summary

In distributed and multi-tenant architectures, unhandled server reboots, container restarts, or unhandled exceptions can leave in-flight background jobs stuck in transient states (`PROCESSING`, `IN_PROGRESS`) indefinitely. In Stage 5, we engineered a durable, self-healing background processing and lifecycle recovery architecture.

On application startup, the platform automatically interrogates the database for orphaned background ingestion and embedding jobs, cleanly transitioning them to an actionable `FAILED` / `INTERRUPTED` status with the explicit error category `PROCESS_RESTART`. Associated document entities are rescued from perpetual `PROCESSING` locks, and full audit events are recorded. Rescued jobs can be safely inspected and retried or cancelled via the authenticated API with strict multi-tenant boundary enforcement.

---

## 2. Architecture & Implementation

### 2.1 Orphan Detection and Transition
- **Module:** `backend/app/services/ingestion/recovery.py` (`recover_orphaned_jobs`)
- **Target Entities:**
  - `IngestionJob`: Any job left in `status == "PROCESSING"` at boot time is transitioned:
    - `status = "FAILED"`
    - `stage = "INTERRUPTED"`
    - `error_category = "PROCESS_RESTART"`
    - `error_message = "Job was interrupted by an application process restart. Safe to retry."`
    - `completed_at = datetime.now(timezone.utc)`
  - `Document`: Associated document entity status reset from `PROCESSING` to `FAILED` to prevent permanent document lockup.
  - `IngestionEvent`: An audit record is created for the job with stage `PROCESS_RESTART` and recovery timestamp.
  - `EmbeddingJob`: Any knowledge base embedding job left in `status == "PROCESSING"` is transitioned to `FAILED` / `INTERRUPTED` with restart metadata.

### 2.2 FastAPI Lifespan Integration
- **File:** `backend/app/main.py`
- In the `lifespan` startup hook, immediately after system roles and permissions are verified, `recover_orphaned_jobs` is executed within an isolated async session.
- Diagnostic logging outputs recovered job counts without delaying readiness probes.

### 2.3 Resilient Retry & Cancellation Endpoints
- **File:** `backend/app/api/v1/ingestion.py`
- `POST /api/v1/ingestion/jobs/{job_id}/retry`:
  - Validates `status in ("FAILED", "CANCELLED")`.
  - Resets job to `status="QUEUED"`, `stage="QUEUED"`, `retry_count=0`, clearing error category and message.
  - Resets document status to `QUEUED`.
  - Records an audit log and an `IngestionEvent` with actor details.
  - Launches background worker task asynchronously.
- `POST /api/v1/ingestion/jobs/{job_id}/cancel`:
  - Validates active status and aborts in-flight work.
  - Transitions document and job to `CANCELLED`.
  - Emits tenant-scoped audit log and lifecycle event.

---

## 3. Test Evidence and Verification

Automated test suite: `backend/tests/test_background_recovery.py`  
Command: `pytest tests/test_background_recovery.py -v`

| Test Case | Scenario / Invariant | Status | Execution Time |
|---|---|---|---|
| `test_orphaned_ingestion_job_recovery` | Simulates server crash during chunking; verifies job transitions to FAILED, error_category=PROCESS_RESTART, doc status FAILED, and IngestionEvent created | **PASSED** | 1.84s |
| `test_orphaned_embedding_job_recovery` | Simulates server crash during embedding; verifies embedding job transitions to FAILED/INTERRUPTED with restart notice | **PASSED** | 1.52s |
| `test_retry_recovered_ingestion_job` | Verifies recovered job can be safely retried via `POST /retry`, clearing error state and setting doc status to QUEUED | **PASSED** | 2.11s |
| `test_cancel_running_ingestion_job` | Verifies active/queued job can be explicitly cancelled via `POST /cancel` | **PASSED** | 1.95s |
| `test_cross_tenant_isolation_on_recovery_and_ingestion` | Verifies Tenant B cannot read, retry, or cancel Tenant A's jobs (HTTP 404) | **PASSED** | 2.20s |

**Total:** 5 passed in 11.23s. Zero regressions. Zero cross-tenant leaks.
