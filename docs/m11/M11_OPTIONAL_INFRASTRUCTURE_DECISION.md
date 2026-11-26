# M11 Stage 5 — Optional Infrastructure Decision (Qdrant, Redis, Phoenix)

**Status:** Decision recorded — no source changes made
**Date:** 2026-11-12
**Scope:** Determine whether Qdrant (and the other optional services) are required for the initial private-staging configuration, prove the application does not depend on them when disabled, and record exactly what must be validated before Qdrant is enabled.
**Change boundary:** This document is the only artifact produced. No Git mutation, no source edit, no cloud call, no package install, and no Docker image pull was performed.

---

## 1. Executive decision

| Question | Answer |
|---|---|
| Is a local `qdrant/qdrant` image present? | **No.** |
| Were the 5 Qdrant-gated live integration tests executed? | **No.** They skipped because no Qdrant endpoint is reachable; the root cause is the missing image. |
| Does the application connect to Qdrant at startup or during retrieval while Qdrant is disabled? | **No.** Verified by an instrumented lifespan/startup probe and by code inspection. |
| Initial staging decision | **Keep Qdrant disabled.** Continue with PostgreSQL pgvector or FTS. Redis and Phoenix also remain disabled. |

```text
LIVE_QDRANT_VERIFICATION = NOT RUN — IMAGE NOT PRESENT
QDRANT_DECISION = DISABLED FOR INITIAL STAGING
```

---

## 2. Current retrieval configuration

### 2.1 Sources of truth observed

| Source | Retrieval mode | Vector store | Embedding defaults | Notes |
|---|---|---|---|---|
| Code defaults (`backend/app/core/config.py:120-124`) | `hybrid` | `pgvector` | `omniroute`, `text-embedding-3-small`, 1536 dims | Used when no environment override is present. |
| Active local `backend/.env` | `lexical` | `fts` | not overridden (code defaults) | This is the configuration used by the startup probe and the local test run. No `QDRANT_*`, `REDIS_*`, `PHOENIX_*`, or `INGESTION_*` overrides are present. |
| `.env.example` | `hybrid` | `pgvector` | `sentence-transformers`, `all-MiniLM-L6-v2`, 384 dims | Documents the intended pgvector path. |
| `render.yaml:61-74` | `hybrid` | `pgvector` | `sentence-transformers`, `all-MiniLM-L6-v2`, 384 dims | Staging blueprint uses pgvector, not Qdrant. |
| `docker-compose.yml:48-51` | `${DEFAULT_RETRIEVAL_MODE:-hybrid}` | `${DEFAULT_VECTOR_STORE:-pgvector}` | `omniroute` | Qdrant is behind the `vector` / `qdrant` / `full` profile only. |

### 2.2 Optional-service settings

| Setting | Default | Runtime use found |
|---|---|---|
| `REDIS_URL` (`config.py:96`) | `redis://localhost:6379/0` | **None.** Rate limiting is explicitly in-process and dependency-free (`backend/app/core/rate_limit.py`). The only other mention is a future-revocation comment in `backend/app/api/v1/auth.py:317`. |
| `QDRANT_URL` (`config.py:97`) | `http://localhost:6333` | Only when a Qdrant store is explicitly constructed (Qdrant KB config, ingestion with `vector_store="qdrant"`, or the explicit `/vector-stores/validate` endpoint). |
| `QDRANT_API_KEY` (`config.py:98`) | unset | Same as above. |
| `QDRANT_COLLECTION_NAME` (`config.py:99`) | `mmaip_knowledge_chunks` | Collection prefix; per-dimension suffix is appended. |
| `PHOENIX_ENABLED` (`config.py:100`) | `false` | **None.** No Phoenix/OpenTelemetry runtime code path exists. |

A local Redis container (`meta-graph-redis`) and a local Neo4j container happen to be running on this machine, but they belong to an unrelated setup and are not used by this application. No Qdrant container is running.

---

## 3. Startup and retrieval behavior with Qdrant disabled

### 3.1 Code path

| Check | Evidence |
|---|---|
| Lifespan does not initialize or health-check any vector store. It only initializes the schema, seeds roles, recovers jobs, and starts the inline ingestion dispatcher. | `backend/app/main.py:18-108` |
| Readiness checks only the relational database. | `backend/app/main.py:144-157` |
| The vector store registry only constructs an adapter for the requested type. With `fts` or `pgvector`, it never constructs `QdrantVectorStore`. | `backend/app/vectorstores/registry.py:29-53` |
| `QdrantVectorStore` constructs `AsyncQdrantClient` lazily inside `_get_client()`, not in `__init__`. Importing the module does not connect. | `backend/app/vectorstores/qdrant_store.py:43-48` |
| Retrieval resolves the configured target store. If the store is `fts`, the mode is forced to `lexical`. Semantic search (and therefore Qdrant search) runs only for `semantic` / `hybrid` modes. | `backend/app/retrieval/service.py:88-120`, `:123-167` |
| Ingestion constructs a Qdrant store only inside `if ret_cfg.vector_store == "qdrant"` branches. | `backend/app/services/ingestion/service.py:550-609`, `:722-759` |
| The only remaining Qdrant contact path is an explicit administrator call to `POST /vector-stores/validate` with `store_type="qdrant"`. It is not part of startup or normal retrieval. | `backend/app/api/v1/vector_stores.py:30-51` |

### 3.2 Executed startup probe

The probe ran from the backend virtual environment with the repository's active `backend/.env` (`DEFAULT_VECTOR_STORE=fts`, `DEFAULT_RETRIEVAL_MODE=lexical`). It replaced `AsyncQdrantClient` with a constructor that raises, and `QdrantVectorStore._get_client` with a function that raises, so any Qdrant client construction or connection attempt would fail the probe. It then started the real FastAPI lifespan through `TestClient`, called `/health` and `/ready`, and resolved both `fts` and `pgvector` stores through the registry.

Key output:

```text
SETTINGS_DEFAULT_VECTOR_STORE = fts
SETTINGS_DEFAULT_RETRIEVAL_MODE = lexical
SETTINGS_QDRANT_URL = http://localhost:6333
SETTINGS_QDRANT_API_KEY_SET = False
SETTINGS_PHOENIX_ENABLED = False
SETTINGS_REDIS_URL = redis://localhost:6379/0
[Lifespan] Inline ingestion dispatcher started (poll=2s, concurrency=1, lease=3600s)
GET_/health = 200 healthy
GET_/ready = 200 {'status': 'ready', 'database': 'connected', ...}
QDRANT_CLIENT_CONSTRUCTIONS_AT_STARTUP = 0
QDRANT_GET_CLIENT_CALLS_AT_STARTUP = 0
RESOLVE_fts = PostgresFTSStore | is_qdrant = False
RESOLVE_pgvector = PgVectorStore | is_qdrant = False
QDRANT_CLIENT_CONSTRUCTIONS_AFTER_RESOLUTION = 0
QDRANT_GET_CLIENT_CALLS_AFTER_RESOLUTION = 0
STARTUP_EVIDENCE_PASS
```

### 3.3 Conclusion

With Qdrant disabled, the application starts, becomes ready, resolves the configured `fts` store, resolves `pgvector` without error, and makes **zero** Qdrant client constructions or connection attempts. No defect was found in this behavior.

---

## 4. PostgreSQL / vectorless path evidence

The active local configuration is the vectorless FTS path. The following focused tests were executed against the SQLite test fallback used by the backend test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_vector_stores.py `
  "tests/test_m10_stage3_knowledge_and_retrieval.py::test_12_vectorless_retrieval_mode" `
  "tests/test_m10_stage3_knowledge_and_retrieval.py::test_13_lexical_retrieval_scoring_and_ranking" `
  "tests/test_m10_stage3_knowledge_and_retrieval.py::test_14_semantic_retrieval_with_vector_store" `
  "tests/test_m10_stage3_knowledge_and_retrieval.py::test_16_empty_document_allowlist_fails_closed" `
  "tests/test_m10_stage3_knowledge_and_retrieval.py::test_17_cross_tenant_retrieval_denial_adversarial" -q -rs
```

Exact result line:

```text
11 passed in 31.74s
```

Covered behavior:

| Test | What it proves |
|---|---|
| `test_vector_store_registry_listing` | Adapter discovery works without contacting a vector service. |
| `test_fts_store_lexical_search_and_ranking` | Vectorless lexical retrieval and ranking work. |
| `test_pgvector_store_upsert_and_similarity_ranking` | pgvector adapter logic works on the SQLite fallback. |
| `test_pgvector_store_rejects_dimension_mismatch_on_upsert` | Local dimension validation is fail-closed. |
| `test_pgvector_store_filters_by_dimension_on_search` | Dimension-scoped search behavior is preserved. |
| `test_qdrant_store_isolates_collections_by_dimension` | Collection naming isolates vector spaces by dimension (mocked, no live server). |
| `test_12_vectorless_retrieval_mode` | End-to-end `RetrievalService` lexical path returns results with `vector_store="fts"` and `embedding_provider="none"`. |
| `test_13_lexical_retrieval_scoring_and_ranking` | Lexical scoring and ordering. |
| `test_14_semantic_retrieval_with_vector_store` | Semantic path with the test vector store abstraction. |
| `test_16_empty_document_allowlist_fails_closed` | An explicit empty `document_ids` allowlist returns no results. |
| `test_17_cross_tenant_retrieval_denial_adversarial` | Cross-tenant retrieval is denied by the authorization layer. |

Limitations of this evidence:

- These tests use the SQLite fallback, not a live PostgreSQL 16 server. Live PostgreSQL verification remains a separate prerequisite and was already recorded as `LIVE_POSTGRESQL_VERIFICATION = NOT RUN` in M10; this stage does not change that status.
- These tests prove the vectorless/pgvector application paths; they do not prove live Qdrant payload isolation.

---

## 5. Qdrant live test outcome

### 5.1 Image presence check

Command:

```powershell
docker images --format "{{.Repository}}:{{.Tag}}"
```

Exact output:

```text
pgvector/pgvector:pg16
python:3.12-slim
python:<none>
redis:7-alpine
neo4j:5.20.0-community
```

There is no `qdrant/qdrant` repository or tag in the local image store. `docker image inspect qdrant/qdrant:v1.9.0` returns:

```text
Error response from daemon: No such image: qdrant/qdrant:v1.9.0
```

`docker ps` shows no Qdrant container, and TCP port `127.0.0.1:6333` is closed. Per the task rules, **no image was pulled**.

### 5.2 Test invocation and exact result

Command (from `backend/`):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_qdrant_live_integration.py -q -rs
```

Exact result line:

```text
5 skipped in 4.28s
```

Skip reason (identical for all five):

```text
Live Qdrant vector database is NOT reachable at http://127.0.0.1:6333. To execute: start the isolated M05 Qdrant container with `docker compose -f docker-compose.m05-qdrant.yml up -d`.
```

The five gated tests and their outcomes:

| Test | File:line | Outcome |
|---|---|---|
| `test_qdrant_service_connectivity_and_health` | `backend/tests/integration/test_qdrant_live_integration.py:62` | SKIPPED — no live endpoint |
| `test_qdrant_collection_creation_and_dimension_isolation` | `...:72` | SKIPPED — no live endpoint |
| `test_qdrant_upsert_and_filtered_search` | `...:105` | SKIPPED — no live endpoint |
| `test_qdrant_cross_tenant_payload_isolation` | `...:150` | SKIPPED — no live endpoint |
| `test_qdrant_scoped_deletion` | `...:179` | SKIPPED — no live endpoint |

### 5.3 How the tests are enabled

| Requirement | Detail |
|---|---|
| URL environment variable | `M05_QDRANT_TEST_URL` (default `http://127.0.0.1:6333`) at `backend/tests/integration/test_qdrant_live_integration.py:12`. The tests do **not** read the application's `QDRANT_URL`. |
| Python package | `qdrant-client`; it is installed in the backend venv (version `1.20.0`), so `HAVE_QDRANT = True`. |
| Server | A reachable Qdrant HTTP API at the test URL. The session fixture probes it and skips all five tests when unreachable (`...:30-40`). |
| Pytest marker | `qdrant_integration` (`backend/pyproject.toml:72`). No marker filter is required to run the file. |
| Compose file | `docker-compose.m05-qdrant.yml` expects `qdrant/qdrant:v1.9.0`, binds `127.0.0.1:6333` and `:6334`, and uses a named volume. Running `docker compose ... up` while the image is absent would attempt a pull, which is why it was not executed. |

```text
LIVE_QDRANT_VERIFICATION = NOT RUN — IMAGE NOT PRESENT
```

---

## 6. Security-critical Qdrant guard verification (offline only)

Because the live tests could not run, the pure guard logic was exercised with a fake Qdrant client that returns an empty collection list and records filters. This is **not** live payload-isolation verification.

| Check | Observed result |
|---|---|
| Empty `document_ids` allowlist | `EMPTY_DOCUMENT_IDS_RESULTS = 0`; the Qdrant `search` call count stayed `0` (guard returns before any client query). |
| Dimension mismatch | `DIMENSION_MISMATCH_RAISED = True`; message `Query vector dimension mismatch: expected 1536, got 384`; `search` call count stayed `0`. |
| Tenant filter construction | `FILTER_KEYS = ['document_id', 'embedding_version', 'knowledge_base_id', 'tenant_id']`; the tenant value equals the requesting tenant and excludes a different tenant. |
| Knowledge-base filter | The filter value equals the requested KB ID. |
| Document filter | `document_id` uses `MatchAny` with exactly the requested document IDs. |
| Cross-tenant query | The generated filter uses the requester's tenant ID; the fake server returned zero results. |

Code under test:

- Empty allowlist guard: `backend/app/vectorstores/qdrant_store.py:131-132`.
- Dimension guard: `backend/app/vectorstores/qdrant_store.py:126-129`.
- Tenant / KB / document / embedding-version payload filters: `backend/app/vectorstores/qdrant_store.py:144-178`.
- Per-dimension collection isolation: `backend/app/vectorstores/qdrant_store.py:50-79`.
- Tenant-scoped deletion: `backend/app/vectorstores/qdrant_store.py:216-262`.

Still unverified until a live server exists: actual Qdrant payload-index behavior, real cross-tenant non-retrieval under concurrency, real delete isolation, and collection lifecycle under restart.

---

## 7. Decision table

| Component | Decision | Basis | Activation trigger |
|---|---|---|---|
| **Redis** | **Disabled** | `REDIS_URL` is configuration-only. Rate limiting is per-process and dependency-free. No runtime Redis client exists. | Only if shared cross-process rate limiting, distributed locks, or a shared cache is added and tested. A Redis container happening to run on the host does not make it a dependency. |
| **Phoenix** | **Disabled** | `PHOENIX_ENABLED` is configuration-only. No Phoenix/OpenTelemetry runtime code path exists. | Only after tracing instrumentation is implemented and a collector endpoint is provisioned. |
| **Qdrant** | **Disabled — live validation NOT RUN (image absent)** | Local image absent; the 5 live tests skipped. Application startup and retrieval do not contact Qdrant when `DEFAULT_VECTOR_STORE=fts`/`pgvector`. Guard logic is statically/offline verified only. | Only after the Section 9 checklist passes against a disposable live instance, and a measured workload need exists (Section 8). |
| **Separate ingestion worker** | **Optional, not enabled for initial staging** | The inline dispatcher is the default. The M11 Stage 5 reliability review requires the worker profile to remain disabled until its claim/lease and environment constraints are closed. | Only after the Stage 5 worker-safety conditions are implemented and verified with two concurrent workers. |

Initial staging configuration remains: one API process, `DEFAULT_VECTOR_STORE` set to `pgvector` (PostgreSQL) or `fts` (vectorless), Redis disabled, Phoenix disabled, Qdrant disabled, worker profile disabled.

---

## 8. Workload that would justify Qdrant

Qdrant should be enabled only for a measured need, not by default. Evidence that would justify it:

1. **Scale beyond pgvector's comfortable operating range.** A corpus/vector count where pgvector HNSW/IVFFlat index build, memory, or filtered-ANN latency violates the retrieval SLO after tuning and `EXPLAIN (ANALYZE, BUFFERS)` review.
2. **High semantic/hybrid query throughput.** Sustained query rates where vector search on the primary PostgreSQL instance contends with transactional ingestion and chat workloads, and read replicas do not solve it cleanly.
3. **Filtered-ANN performance.** Large per-tenant or per-KB vector sets where tenant/KB/document filters cause unacceptable recall or latency in PostgreSQL, while Qdrant payload indexes provide a measured improvement.
4. **Independent vector-tier operations.** A requirement for collection snapshots, replication/sharding, dedicated memory sizing, or independent scaling/upgrade of the vector tier.
5. **Multi-worker or multi-replica ingestion/retrieval.** A deployment shape where the relational database CPU/connection budget cannot absorb vector search at the required concurrency.
6. **Retrieval evaluation gap.** M11 retrieval evaluations show a concrete recall/latency gap that pgvector/FTS cannot close within the staging SLO.

A desire to "use a vector database" is not sufficient. Because Qdrant adds a second data store with its own consistency, backup, and orphan-vector failure modes (documented in the M11 Stage 5 background-job review), it must be justified by measurements.

---

## 9. Pre-activation validation checklist

Do not enable Qdrant in any environment until every item below is satisfied and recorded.

### 9.1 Image and version

- [ ] Confirm the approved `qdrant/qdrant` image is already local, or obtain explicit approval to pull it. Do not run `docker compose -f docker-compose.m05-qdrant.yml up -d` while the image is absent, because Compose would pull.
- [ ] Verify client/server compatibility. The backend venv currently has `qdrant-client 1.20.0`, while the compose files reference `qdrant/qdrant:v1.9.0`; pin a mutually compatible client/server pair before activation.
- [ ] Record the exact image digest.

### 9.2 Isolated live run

- [ ] Start exactly one disposable Qdrant container bound to `127.0.0.1:6333`, with no other services, a disposable volume, no restart policy, and a conservative memory limit.
- [ ] Wait for readiness (`GET /collections` or the healthcheck) before running tests.
- [ ] Run the 5 tests sequentially with `M05_QDRANT_TEST_URL=http://127.0.0.1:6333`:

```powershell
$env:M05_QDRANT_TEST_URL = "http://127.0.0.1:6333"
.\.venv\Scripts\python.exe -m pytest tests/integration/test_qdrant_live_integration.py -q -rs -p no:randomly
```

- [ ] Require all 5 to pass, with an exact summary line such as `5 passed`, not skips.
- [ ] Stop and remove only the disposable container and its volume; leave images in place.

### 9.3 Security-critical live assertions

- [ ] Empty `document_ids` allowlist returns zero results and performs no Qdrant search.
- [ ] Tenant A cannot retrieve Tenant B vectors with an identical query vector.
- [ ] Knowledge-base and document ACL filters return only authorized points.
- [ ] A query vector whose length differs from the collection dimension raises the expected error (and does not silently query another collection).
- [ ] Tenant B cannot delete Tenant A chunks; Tenant A can delete its own.
- [ ] Collections remain isolated per dimension (`{collection}_{dims}`).
- [ ] Department-level filtering behaves as designed for non-admin users.

### 9.4 Application integration

- [ ] Set `QDRANT_URL` (and `QDRANT_API_KEY` if used) explicitly for the target environment; do not rely on the `localhost` default in a container.
- [ ] Set `DEFAULT_VECTOR_STORE=qdrant` only for a KB that has been deliberately migrated; keep pgvector/FTS for the rest until validated.
- [ ] Verify startup and `/ready` still do not depend on Qdrant being available (failure must be degraded, not a startup crash).
- [ ] Verify ingestion and reindex paths write to Qdrant only for `vector_store="qdrant"` KBs, and that a Qdrant outage produces a visible job failure rather than silent data loss.
- [ ] Verify the explicit `/vector-stores/validate` endpoint returns healthy/unhealthy accurately.

### 9.5 Operations and recovery

- [ ] Run the Qdrant rebuild/recovery drill (`backend/app/commands/drill_qdrant_rebuild.py` / `infrastructure/scripts/drill-live-qdrant-rebuild.sh`) and record `QDRANT_REBUILD_PASS` / `QDRANT_REBUILD_VERIFIED`.
- [ ] Define backup/restore for Qdrant collections and test a restore.
- [ ] Document orphan-vector cleanup for failed ingestion transactions (DB rollback after a successful upsert).
- [ ] Add monitoring for Qdrant latency, errors, collection size, and disk/memory.
- [ ] Define the rollback plan: switch the KB back to pgvector/FTS and confirm retrieval still works with existing relational data.

---

## 10. Defects and source changes

No defect was found in the disabled-path behavior: startup, readiness, `fts` resolution, and `pgvector` resolution made zero Qdrant client constructions or connection attempts.

No source files were edited. The only artifact is this document.

---

## 11. Declarations

```text
LOCAL_QDRANT_IMAGE_PRESENT = NO
LIVE_QDRANT_VERIFICATION = NOT RUN — IMAGE NOT PRESENT
QDRANT_LIVE_TESTS = 5 SKIPPED (5 skipped in 4.28s)
STARTUP_WITH_QDRANT_DISABLED = PASS (0 client constructions, 0 connection attempts)
VECTORLESS_PATH_TESTS = 11 PASSED (11 passed in 31.74s)
REDIS_DECISION = DISABLED
PHOENIX_DECISION = DISABLED
QDRANT_DECISION = DISABLED FOR INITIAL STAGING
SEPARATE_WORKER_DECISION = OPTIONAL / NOT ENABLED FOR INITIAL STAGING
```
