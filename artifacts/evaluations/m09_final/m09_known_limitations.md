# Milestone M09 — Known Limitations & Operational Considerations

**Project:** Multi-Tenant AI Assistant Platform / Chatbot-as-a-Service (CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Execution Date:** 2026-11-10  
**Target Milestone:** M09 Release Readiness

---

## 1. Preserved M05 Status & Deferred Disaster Drills

Under the CPU-only host constraint (Windows 10 Pro, 8 GB RAM, dual-core i3-7100U), Milestone M05 maintains a **CONDITIONAL_PASS** status. The following four destructive production recovery drills remain deferred:
1. **Physical Postgres Kill/Hard Restart:** Validating database pool reconnection under active multi-container SIGKILL.
2. **MinIO Hard Kill/Restart:** Simulating ungraceful object storage loss and mid-write stream recovery.
3. **Live Multi-Container Network Partition:** Injecting `iptables` packet drop between the application container and Qdrant cluster.
4. **Multi-Version Alembic Live Downgrade on Postgres:** Executing continuous forward and rollback schema migrations against live PostgreSQL with loaded data.

*Mitigation in M09:* Soft failure and reconnect recovery were fully validated in-process via unit/integration suites (`test_m05_recovery_drills_unit.py`, `test_m05_database_recovery.py`, and `test_background_recovery.py`), and the S3 storage abstraction interface was verified with mock drivers.

---

## 2. Hardware & Resource Envelope

1. **Local Host Constraints:**
   - Total System RAM: 8 GB (with approximately 1–2 GB available under normal desktop load).
   - CPU: Intel Core i3-7100U (2 cores, 4 threads, no AVX-512, no discrete GPU).
2. **Embedding & Ingestion Throughput:**
   - When using local CPU embeddings (`sentence-transformers/all-MiniLM-L6-v2`), batch chunking is limited to concurrency `1` to avoid CPU thermal throttling and OS page swapping.
   - For high-volume production deployments (>1,000 documents/day), external embedding APIs (e.g., OpenAI `text-embedding-3-small` via BYOK) or a dedicated GPU worker pool are recommended.
3. **In-Process Ring-Buffer Tracer:**
   - The Stage 3 live tracer maintains an in-memory ring buffer (up to 1,000 traces per process).
   - Traces are cleared on process restart. For multi-node horizontal scaling or permanent trace storage, OpenTelemetry Phoenix collector export (`PHOENIX_ENABLED=true`) or Datadog/Jaeger exporter should be enabled.

---

## 3. Commercial Provider BYOK Key Requirement

1. **Zero Silent Fallback Policy:**
   - Commercial LLM providers (`openai`, `anthropic`, `gemini`, `groq`) require each workspace to provide an active API key in the BYOK vault (`/api/v1/providers/credentials`).
   - If an assistant is configured to use a commercial provider without a key in the workspace vault, the runtime halts immediately with an actionable error.
   - Local testing and sandbox environments should utilize the `mock` provider or local `omniroute` gateway.

---

## 4. Production Storage on Ephemeral Cloud Hosts

1. **Local Storage Ephemerality:**
   - `LocalStorageProvider` (`STORAGE_BACKEND=local`) stores files on the local filesystem (`./data/storage`).
   - On ephemeral cloud hosts (e.g., free/hobby tiers on Render, Fly.io, or Heroku), container restarts will discard locally stored uploaded PDFs and raw documents (though database text chunks and vectors in PostgreSQL/Qdrant persist).
2. **Cloud S3 Recommendation:**
   - For persistent document storage on ephemeral hosts, set `STORAGE_BACKEND=s3` and configure `S3_BUCKET_NAME`, `S3_ENDPOINT_URL`, and S3 credentials (AWS S3, Cloudflare R2, MinIO, or Supabase Storage).
