# Milestone 05 External Execution — Qdrant Test Selection Audit

**Project:** Multi-Tenant AI Platform / CaaS  
**Audit Phase:** Phase 5 — Qdrant Test Selection Audit  
**Auditor:** Qdrant Vector Architect & QA Lead  

---

## 1. Verified Test Node IDs (Exactly 5 Nodes)

The runner script (`run-live-integration-tests.sh`, lines 295–301) explicitly targets the exact 5 Qdrant integration test node IDs required by Milestone 05:

| # | Exact Node ID | Target File | Core Assertion |
|---|---|---|---|
| 1 | `tests/integration/test_qdrant_live_integration.py::test_qdrant_service_connectivity_and_health` | `test_qdrant_live_integration.py` | Qdrant responds `healthy` on `/readyz` |
| 2 | `tests/integration/test_qdrant_live_integration.py::test_qdrant_collection_creation_and_dimension_isolation` | `test_qdrant_live_integration.py` | Collections created with dimension isolation (768 vs 1536) |
| 3 | `tests/integration/test_qdrant_live_integration.py::test_qdrant_upsert_and_filtered_search` | `test_qdrant_live_integration.py` | Vector upsert with payloads & cosine search |
| 4 | `tests/integration/test_qdrant_live_integration.py::test_qdrant_cross_tenant_payload_isolation` | `test_qdrant_live_integration.py` | Cross-tenant vectors strictly isolated by payload filter |
| 5 | `tests/integration/test_qdrant_live_integration.py::test_qdrant_scoped_deletion` | `test_qdrant_live_integration.py` | Point deletion by document ID excludes vectors from search |

---

## 2. Test Execution & Assertion Integrity

### 2.1 Invocation Method
```bash
(
    cd "$BACKEND_DIR"
    "$PYTHON_CMD" -m pytest "${QDRANT_TEST_NODES[@]}" -v \
        --junitxml="${OUTPUT_DIR}/qdrant_test_junit.xml" \
        2>&1 | tee "${OUTPUT_DIR}/qdrant_test_output.txt"
)
QDRANT_EXIT=${PIPESTATUS[0]}
```

### 2.2 Execution Integrity
- The suite does not rely on mocked Qdrant clients or in-memory emulators; tests connect directly to `http://127.0.0.1:6333` running the official `qdrant/qdrant:v1.9.0` image.
- Test collections use disposable names (`test_m05_qdrant_live_*`) and clean up after execution.
- If any test assertion fails, Pytest exits with code 1. `PIPESTATUS[0]` sets `QDRANT_EXIT=1`, marking `QDRANT_PASSED=false` and triggering `FINAL_EXIT=1`.

### 2.3 Skip Path Guard
- None of the 5 Qdrant tests contain skip decorators.
- The JUnit XML output (`qdrant_test_junit.xml`) must be audited to verify:
  - `tests="5"`
  - `failures="0"`
  - `errors="0"`
  - `skipped="0"`
