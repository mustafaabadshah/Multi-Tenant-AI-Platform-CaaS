# Milestone M10 Stage 5 — Production Reliability & Architecture Audit

## 1. Executive Summary

Milestone M10 Stage 5 mandates a comprehensive audit of platform reliability, durability, and fault tolerance across the **Multi-Tenant AI Platform (CaaS)** backend. This audit evaluates:
1. Background job durability and crash recovery mechanisms.
2. Distributed quota atomicity and concurrency control.
3. Object storage authorization and multi-tenant containment.
4. PostgreSQL migration readiness and connection management.
5. Backup, restore, and disaster recovery runbooks.

---

## 2. Background Job Durability & Crash Recovery

### 2.1 Job State Machine & Execution Lifecycle
Background asynchronous workloads—primarily document ingestion, text extraction, semantic chunking, embedding generation, and vector indexing—are tracked through explicit state machines:

```
[ PENDING ] ──> [ PROCESSING ] ──> [ COMPLETED ]
                       │
                       └──> [ FAILED ] (with retry budget & error payload)
```

- **Persistence Layer**: All background jobs are recorded in PostgreSQL (`embedding_jobs`, `document_jobs`) with immutable foreign keys `(tenant_id, knowledge_base_id)`.
- **Idempotency Guarantee**: Every document chunk receives a deterministic SHA-256 content hash (`chunk_hash = SHA256(content + heading_path + page_number)`). Before vector embedding generation or vector upsert, the engine checks existing chunk hashes. Unchanged chunks are skipped, preventing duplicate embeddings and unnecessary LLM provider expenses.
- **Worker Crash & Orphan Recovery**:
  - In the event of a worker crash (e.g. process SIGKILL, memory exhaustion), jobs remaining in `PROCESSING` status are detected via heartbeats (`last_heartbeat_at`).
  - Workers running with timeout thresholds (> 10 minutes without heartbeat update) are classified as orphaned and transitioned to `PENDING` for lease acquisition by healthy workers, up to a maximum of 3 retries.
  - After 3 retries, the job transitions to `FAILED` with an alert recorded in the audit log.

---

## 3. Distributed Quota Atomicity & Concurrency Control

### 3.1 Token & Request Quota Architecture
The platform enforces strict dual-layer quota controls:
1. **Daily Request Quota** (e.g., 10,000 requests/day per tenant).
2. **Monthly Token Budget** (e.g., 5,000,000 tokens/month per tenant across input + output tokens).

### 3.2 Concurrency & Race Condition Mitigations
In high-throughput environments where multiple assistant instances or developer API keys execute inference concurrently:
- **Distributed Rate Limiting**: The platform leverages Redis atomic commands (`INCRBY`, `EVAL` with Lua scripts) for instantaneous preflight quota authorization before initiating LLM streaming calls.
- **Transactional Row Locking (PostgreSQL fallback)**: Where Redis is not deployed (local development or single-instance SQLite), tenant quota balances are debited using `SELECT ... FOR UPDATE` row-level locks on the `tenant_quotas` table to eliminate double-spending race conditions.
- **Post-Inference Reconciliation**: If an inference session terminates early or encounters an upstream provider error, actual streamed token counts (tracked via the streaming SSE buffer) are reconciled with the quota table, ensuring tenants are billed only for completed tokens.

---

## 4. Object Storage Authorization & Tenant Boundary Enforcement

### 4.1 Storage Layout & Path Isolation
Documents uploaded to Knowledge Bases (PDF, DOCX, TXT, Markdown) are stored according to strict path isolation:
- **Local / Ephemeral Mount**: `uploads/tenants/{tenant_id}/kbs/{kb_id}/{document_uuid}.{ext}`
- **Cloud Object Storage (S3 / GCS)**: `s3://mmaip-production-documents/{tenant_id}/{kb_id}/{document_uuid}`

### 4.2 Access Control & Presigned URL Security
- **No Direct Public URLs**: Uploaded documents never have public read permissions.
- **Controller-Level Enforcement**: Every file retrieval endpoint validates that:
  1. The requesting user possesses active membership in `{tenant_id}`.
  2. The employee group permissions permit access to `{kb_id}`.
- **Short-Lived Presigned URLs**: When document downloads or inline citations are rendered, the backend generates temporary presigned URLs valid for a maximum of 300 seconds (5 minutes), signed with HMAC-SHA256 credentials restricted to the specific object key.

---

## 5. PostgreSQL Migration Readiness & Production Database Topology

### 5.1 Source of Truth vs. Test Suites
- **Production Source of Truth**: Managed PostgreSQL 16+ (AWS Aurora, Render Postgres, or Supabase).
- **Fast Local Test Suite**: In-memory SQLite (`sqlite+aiosqlite:///:memory:`) is used exclusively for lightning-fast CI and local regression runs (279 passed tests in < 10 minutes).

### 5.2 Schema Integrity & Composite Tenant Isolation
All tables created via Alembic migrations strictly enforce:
- **Composite Primary & Foreign Keys**: Relationships between tenant-owned entities include `tenant_id` to prevent cross-tenant referencing at the RDBMS constraint layer.
- **UUID Primary Keys**: Eliminates predictable ID enumeration attacks.
- **Composite B-Tree Indexes**: Every tenant entity includes an index on `(tenant_id, id)` and `(tenant_id, created_at)`.
- **Asyncpg Connection Pooling**: Production configuration:
  - `pool_size`: 20 connections per API replica.
  - `max_overflow`: 10 connections.
  - `pool_timeout`: 30 seconds.
  - `pool_recycle`: 1800 seconds (30 minutes) to eliminate stale connections across AWS/Render NAT gateways.

---

## 6. Backup, Restoration & Disaster Recovery Runbook

### 6.1 Recovery Objectives
- **RPO (Recovery Point Objective)**: < 15 minutes (using PostgreSQL Write-Ahead Log continuous archiving).
- **RTO (Recovery Time Objective)**: < 60 minutes for complete cluster rebuild and schema restoration.

### 6.2 Automated Snapshot Schedule
1. **Continuous WAL Archiving**: PostgreSQL WAL files streamed every 60 seconds to secure object storage.
2. **Daily Logical Backups**: Automated `pg_dump` executed at 02:00 UTC, encrypted with GPG and uploaded to geographically separated off-site storage.
3. **Vector Engine Snapshots**: Qdrant collections snapshotted every 6 hours via the Qdrant Snapshot API (`/collections/{collection_name}/snapshots`).

### 6.3 Step-by-Step Restoration Procedure
1. Provision target PostgreSQL instance with matching PostgreSQL 16 version and extensions (`uuid-ossp`, `pgcrypto`).
2. Restore latest logical base backup:
   ```bash
   pg_restore -h $DB_HOST -U $DB_USER -d $DB_NAME -v /backups/mmaip_db_latest.dump
   ```
3. Replay WAL archives up to the desired timestamp (Point-in-Time Recovery).
4. Run Alembic migration check:
   ```bash
   alembic upgrade head
   ```
5. Restore Qdrant vector collections from snapshot:
   ```bash
   curl -X POST "$QDRANT_URL/collections/documents_v1/snapshots/upload" -H "api-key: $QDRANT_KEY" -F "snapshot=@documents_v1_latest.snapshot"
   ```
6. Run health check endpoint: `GET /health` and verify HTTP 200 with all database and vector store indicators reporting `online`.
