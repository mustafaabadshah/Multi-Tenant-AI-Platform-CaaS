# Milestone 05 — Remaining Release Blockers Status

**Current Milestone Decision:** `CONDITIONAL_PASS`  
**Date:** 2026-11-08  

---

## 1. Blocker Inventory

Although the three handover defects (A, B, C) have been fully remediated and validated in unit tests and package configuration, **the four core M05 live infrastructure blockers remain formally open (NOT_RUN)** until an external Linux runner executes the live containers and returns raw execution evidence:

| Blocker ID | Description | Remediation State | Live Status |
|---|---|---|---|
| **BLK-01A** | 12 PostgreSQL/pgvector live integration tests | Runner scripts verified; node IDs selected | **NOT_RUN** |
| **BLK-01B** | 5 Qdrant live integration tests | Runner scripts verified; node IDs selected | **NOT_RUN** |
| **BLK-01C** | Live PostgreSQL backup & restore drill | Script updated with in-memory BYOK decryption proof | **NOT_RUN** |
| **BLK-01D** | Live Qdrant application-driven rebuild drill | Script updated with `IngestionService.reindex_knowledge_base` | **NOT_RUN** |

---

## 2. Requirements for Unconditional Release Closure

To close Milestone 05 and transition from `CONDITIONAL_PASS` to `PASS`:
1. Execute Snapshot V2 on an external Linux machine ($\ge 4$ GB RAM, Docker 24+, Python 3.12).
2. Produce raw output logs, JUnit XML reports, and container dumps in `test_results/`.
3. Package results into `m05_live_evidence_results.tar.gz` with SHA-256 hash.
4. Return evidence to `artifacts/evaluations/m05_final_closure_20261108/external_execution/`.
5. Verify 17 tests passed (`failures="0"`, `errors="0"`, `skipped="0"`) and all 13 drill evidence markers are present.
