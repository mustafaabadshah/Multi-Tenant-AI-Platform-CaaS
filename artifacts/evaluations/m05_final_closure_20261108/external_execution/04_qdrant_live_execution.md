# Milestone 05 External Execution — Qdrant v1.9.0 Live Integration Plan

**Project:** Multi-Tenant AI Platform / CaaS  
**Date:** 2026-11-08  
**Audit Phase:** Phase G — Qdrant Live Integration Assessment  
**Auditor:** Senior Vector Store Architect & Distributed Systems Engineer  

---

## 1. Execution Status & Environment Boundary

- **Execution Status:** **`NOT_RUN — PENDING EXTERNAL LINUX RUNNER`**
- **Reason:** Host physical available RAM is **1,271.36 MB** (< 2,048 MB memory safety threshold).
- **Packaged Deliverable:** Ready for execution inside `artifacts/evaluations/m05_final_closure_20261108/portable_runner/m05_live_test_snapshot.zip`.

---

## 2. Target Container Specification & Isolation

- **Docker Image:** `qdrant/qdrant:v1.9.0`
- **Host Port Bindings:** `127.0.0.1:6333:6333` (HTTP REST API), `127.0.0.1:6334:6334` (gRPC)
- **Compose Specification:** `docker-compose.m05-qdrant.yml`
- **Memory Limit:** 256 MB (CPU-only execution, zero GPU dependencies)
- **Healthcheck Probe:** TCP probe on port 6333 via `/dev/tcp/localhost/6333` (Interval: 5s, Timeout: 3s, Retries: 10)

---

## 3. Test Suite Inventory (5 Live Node IDs)

The external runner executes the following 5 exact test node IDs:

```text
tests/integration/test_qdrant_live_integration.py::test_qdrant_service_connectivity_and_health
tests/integration/test_qdrant_live_integration.py::test_qdrant_collection_creation_and_dimension_isolation
tests/integration/test_qdrant_live_integration.py::test_qdrant_upsert_and_filtered_search
tests/integration/test_qdrant_live_integration.py::test_qdrant_cross_tenant_payload_isolation
tests/integration/test_qdrant_live_integration.py::test_qdrant_scoped_deletion
```

---

## 4. Specific Properties Validated by the Suite

1. **Service Connectivity & Readiness:** Queries `/readyz` endpoint and confirms Qdrant daemon is accepting connections.
2. **Dimension-Isolated Collection Management:** Creates separate collections for different embedding dimensions (e.g. 768 vs 1536) using Cosine distance metric.
3. **Vector Upsert & Cosine Search:** Upserts real vector points with associated metadata payloads (`document_id`, `chunk_id`, `tenant_id`, `knowledge_base_id`) and executes vector searches.
4. **Cross-Tenant Payload Isolation:** Verifies that searches with a `tenant_id` payload filter strictly prevent any cross-tenant vector candidates from being returned, even when embedding vectors are identical.
5. **Scoped Point Deletion:** Deletes points associated with specific document IDs and verifies that deleted points are immediately excluded from future search results.
6. **Relational Authorization Layering:** Confirms that returned candidates pass through the application's `RetrievalAuthorizer` to recheck relational boundaries against PostgreSQL before reaching the user.
