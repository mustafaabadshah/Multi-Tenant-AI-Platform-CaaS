# Milestone 05 External Execution — Remaining Blockers Register

**Project:** Multi-Tenant AI Platform / CaaS  
**Date:** 2026-11-08  
**Audit Phase:** Remaining Blockers Audit  
**Auditor:** Independent Release Assessor  

---

## 1. Blocker Inventory: BLK-01

| Field | Detail |
|---|---|
| **Blocker ID** | **`BLK-01`** |
| **Title** | Live Container Infrastructure Validation on PostgreSQL 16 & Qdrant v1.9.0 |
| **Severity** | **RELEASE_BLOCKER_FOR_UNCONDITIONAL_PASS** |
| **Current Status** | **`PORTABLE_RUNNER_PACKAGE_READY (EXECUTION PENDING EXTERNAL LINUX RUNNER)`** |
| **Root Cause** | Host physical available RAM is **1,271.36 MB** (< 2,048 MB memory safety threshold). Docker execution locally was withheld to prevent system thrashing and instability. No external runner is programmatically reachable from the current session. |
| **Required Deliverables** | 1. 12 live PostgreSQL/pgvector/FTS test logs (`postgres_test_output.txt`).<br>2. 5 live Qdrant test logs (`qdrant_test_output.txt`).<br>3. Live PostgreSQL backup and restore drill log (`postgres_backup_restore_drill.log`).<br>4. Live Qdrant rebuild drill log (`qdrant_rebuild_drill.log`).<br>5. Container service logs (`postgres_container_logs.txt`, `qdrant_container_logs.txt`). |
| **Resolution Action** | Transfer `portable_runner/m05_live_test_snapshot.zip` (SHA-256: `3c97b830261542a6a27dd1d0ee93cc76b63cebbb91f99fa9f54e50dcc8eeed6f`) to an Ubuntu 22.04/24.04 runner with $\ge 4$ GB RAM, run `./infrastructure/scripts/run-live-integration-tests.sh --mode all`, and return `m05_live_evidence_results.tar.gz`. |

---

## 2. Technical Debt & Milestone 06 Follow-Ups (Non-Blocking for Staging)

1. **PDF Word-Level Span Coordinates:** Ingestion currently preserves available parser bounding boxes with synthetic US Letter fallback; exact word span extraction via PyMuPDF `get_text("words")` is formally deferred to Milestone 06.
2. **Ingestion Queue Durability:** `asyncio.create_task` is acceptable for controlled staging; dedicated distributed workers (Celery/ARQ/BullMQ) recommended for enterprise production scaling.
