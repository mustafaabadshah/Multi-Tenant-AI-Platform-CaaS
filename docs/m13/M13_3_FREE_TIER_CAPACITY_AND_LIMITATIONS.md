# M13.3 Stage 5/6 — Free-Tier Capacity and Limitations

| Field | Value |
|---|---|
| Milestone | M13.3 Stage 5/6 |
| Document | Free-tier capacity, allowances, duty-cycle limits, and operating constraints |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Baseline | `main` @ `9c27e1b8d3e6aeec00dcf6ddb84cd849b9a607e8`; worktree includes M13.3 edits |
| Date | 2026-11-13 |
| Topology | Render Free backend (Docker) + Render Free frontend (Node) + Neon Free PostgreSQL 16 + Backblaze B2 Free |
| Evidence | Inherited from the M13 Phase 1 cost/limits and architecture decisions, the M13.2 runtime limits, and the M13.3 blueprint review; repository configuration inspected read-only |
| Live validation | None. No Render, Neon, B2, or other provider call was made for this document |
| Execution status | **READ-ONLY.** No provisioning, billing action, deployment, or external call was performed, and no secret value was printed or written |

> **Expected cost may remain $0 while all services stay within current free allowances and terms. This is not a zero-cost guarantee.**

This document describes an operating envelope, not a measured production capacity. Provider allowances are living values and can change. Re-verify the official provider terms before provisioning. The figures below are inherited from the M13 Phase 1 research and the M13.2 runtime limits, not re-fetched for this stage.

---

## 1. Topology and binding constraints

| Layer | Service | Inherited free allowance | Binding constraint |
|---|---|---|---|
| Frontend | Render Free web service, Node runtime, `plan: free` | 0.1 CPU / 512 MB, one instance, ephemeral filesystem, shared 750 instance-hours/month, 15-minute idle spin-down, about 1-minute cold start, 5 GB/month outbound bandwidth, 500 pipeline minutes/month | Shared Render instance-hour pool; 512 MB Next server memory is unverified |
| Backend | Render Free web service, Docker runtime, `plan: free` | Same per-service envelope and same shared workspace pool as the frontend | 512 MB / 0.1 CPU; shared 750-hour pool; Neon wakeups |
| Database | Neon Free PostgreSQL 16 + pgvector | 1 GB storage/project, 100 CU-hours/project/month, 5 GB egress/project, scale-to-zero after 5 minutes, 6-hour instant restore (1 GB changes), 1 manual snapshot | 100 CU-hours; 1 GB storage; direct-connection and pooling behavior |
| Object storage | Backblaze B2 Free, private S3-compatible bucket | First 10 GB storage account-wide, egress up to 3x average monthly storage, Class A/B/C free, Class D first 2,500/day | 10 GB including versions; lifecycle management is required |
| LLM / embeddings | Operator-controlled OmniRoute or tenant BYOK; `local` embeddings for staging | Not part of the hosting allowance | No platform-paid fallback; any external model usage is outside this cost envelope |
| Domain | Generated `*.onrender.com` hostnames | $0 | No custom domain, no edge access control |

**The Render 5 GB figure is outbound bandwidth per workspace per month, not disk storage.** Render Free has no persistent disk; the filesystem is ephemeral. The database and object store are external.

---

## 2. Render Free capacity

### 2.1 Per-service envelope

Each Render Free web service has:

- **0.1 CPU and 512 MB RAM**, one instance only.
- **750 Free instance-hours per workspace per calendar month**, shared by all Free web services in the workspace.
- **Spin-down after 15 minutes without inbound HTTP or WebSocket messages**, with a cold start of about one minute.
- **Ephemeral filesystem**; no persistent disk, no shell access, no one-off jobs, and no `preDeployCommand` (paid-only).
- **No private-network inbound traffic**; the service can make outbound private-network connections.
- **5 GB/month outbound bandwidth** and **500 pipeline minutes/month** at the workspace level.
- Free services may be restarted at any time.

### 2.2 Shared 750-hour pool

| Usage pattern | Monthly instance-hours | Share of 750 | Result |
|---|---:|---:|---|
| One service, 24/7 | 720 | 96% | Fits with about 30 hours of headroom |
| **Two services, 24/7** | **1,440** | **192%** | **Exhausts in about 16 days; both services suspend until the next calendar month** |
| Two services, 12 hours/day each | 720 | 96% | Fits at the edge, no headroom |
| Two services, 8 hours/day each | 480 | 64% | Comfortable staging budget |
| Two services, 2 hours/day each | 120 | 16% | About six acceptance sessions/day would still fit |
| Backend only, 12 hours/day | 360 | 48% | Leaves room for occasional frontend use |

**Two services cannot run 24/7 within the 750-hour pool.** A low-duty-cycle staging/demo pattern is required. When the pool is exhausted, all Free web services in the workspace suspend until the next calendar month; instance hours do not overage.

### 2.3 Cold start, idle behavior, and ephemeral state

- Idle spin-down is expected. A cold start includes container boot, `alembic upgrade head`, Uvicorn startup, role seeding, and ingestion/lease recovery.
- The platform health check is `/health` (process liveness only). `/health` does not touch the database.
- `/ready` performs a real database round trip and is not the platform probe. Do not poll `/ready`; it wakes Neon.
- The filesystem is ephemeral. Local uploads and local temp state can disappear on restart or redeploy. Staging must use `STORAGE_BACKEND=s3` and must not rely on `STORAGE_PATH`.
- There is no application-level backup or point-in-time recovery for B2. Treat staging data as disposable.

### 2.4 Build minutes and bandwidth

- **500 pipeline minutes/month** are shared at the workspace level. Without a payment method, builds stop when the minutes are exhausted; optional supplementary minutes are a paid action.
- **5 GB/month outbound bandwidth** is shared at the workspace level. Above that, with a card, bandwidth is billed at the inherited overage rate; without a card, services can spin down.
- Document downloads are proxied through the backend (`B2 -> Render backend -> browser`), so they count against Render outbound bandwidth, not only B2 egress.
- `autoDeploy: false` is set in the blueprint. Deployments are manual; this avoids accidental rebuilds and build-minute consumption.

### 2.5 Hard operating constraints

- **No keep-alives.** Do not add uptime pings, synthetic traffic, or scheduled requests to defeat spin-down. They consume instance-hours and wake Neon.
- **No extra workers.** Keep `--workers 1`, one API process, and `INGESTION_MAX_CONCURRENCY=1`. Do not add a separate ingestion worker on the Free instance.
- **No local persistent uploads.** `STORAGE_BACKEND=s3`; the Render disk is ephemeral.
- **Single API process.** The in-process dispatcher, per-process rate limiter, and process-wide ingestion semaphore assume one process.
- **No paid add-ons or payment method** for the $0/no-card posture. Adding a card changes overage behavior from suspension to billing.

---

## 3. Neon Free capacity

### 3.1 Inherited allowances

| Resource | Free allowance | Staging implication |
|---|---|---|
| Storage | 1 GB PostgreSQL per project | Metadata, chunks, vectors, conversations; documents stay in B2 |
| Compute | 100 CU-hours per project per month | Fixed 0.25 CU gives about 400 active hours/month |
| Egress | 5 GB per project per month | API/database traffic only; documents do not traverse Neon |
| Scale-to-zero | After 5 minutes of inactivity; resumes in a few hundred milliseconds | Cold database wake can exceed the application's 3-second `/ready` timeout |
| Recovery | 6-hour instant restore, limited to 1 GB of changes; 1 manual snapshot | Adequate for staging; no scheduled backups on Free |
| Inactivity pause | Free projects are not paused for inactivity; only compute suspends | No Supabase-style one-week project pause |
| Connection pooling | PgBouncer transaction pooling; direct connections also available | Direct endpoint is recommended for one backend process and migrations |
| TLS | Required; Neon rejects unencrypted connections | Use `?ssl=require` in the async URL, not `?sslmode=require` |

If CU-hours or egress are exhausted, compute suspends until the next billing period or an upgrade. If storage exceeds 1 GB, writes fail. Neon does not delete data for exceeding the Free plan.

### 3.2 Compute arithmetic

| Compute size | Hours at 100 CU-hours | Hours/day in a 30-day month | Notes |
|---:|---:|---:|---|
| 0.25 CU (Free default/minimum) | 400 | 13.2 | Recommended fixed size for staging |
| 0.5 CU | 200 | 6.7 | Faster, but exhausts twice as fast |
| 1 CU | 100 | 3.3 | Not suitable for a full day |
| 2 CU (Free maximum) | 50 | 1.7 | Short bursts only |

Autoscaling above 0.25 CU burns the allowance faster. Fix the staging compute at 0.25 CU.

### 3.3 What wakes Neon

The 3,600-second empty-queue dispatcher poll reduces idle polling wakeups, but it does not make the database free of activity. The following still wake or keep Neon awake:

- `/ready` calls (one real database round trip each).
- Chat requests and conversation writes.
- Document uploads, reprocessing, retries, and ingestion dispatch.
- Login, registration checks, workspace switching, dashboard API calls, and audit writes.
- `alembic upgrade head` before Uvicorn starts.
- Startup role seeding and ingestion/lease recovery.

Since M13.3, `Base.metadata.create_all` is gated to `ENVIRONMENT=development` by `should_initialize_schema`. In staging, Alembic is the only DDL owner. A staging cold start therefore runs the idempotent migration command before Uvicorn, then role seeding and recovery; it does not run ORM `create_all`.

### 3.4 Duty-cycle budget

The following uses active hours as a proxy for CU-hours at a fixed 0.25 CU. Scale-to-zero has a 5-minute tail, so actual CU-hours can be higher than the request window suggests.

| Backend active pattern | Active hours/month | Approximate CU-hours at 0.25 CU | Verdict |
|---|---:|---:|---|
| 2 hours/day | 60 | 15 | Comfortable |
| 4 hours/day | 120 | 30 | Comfortable |
| 8 hours/day | 240 | 60 | Comfortable |
| 12 hours/day | 360 | 90 | Fits at the edge, no headroom |
| 24/7 | 720 | 180 | Exhausts the 100 CU-hour allowance in about 16.7 days |

A 24/7 backend at 0.25 CU consumes about 180 CU-hours in a 30-day month. A 12-hour/day duty cycle consumes about 90 CU-hours, which fits. Measure actual active hours; do not assume scale-to-zero will save the budget while the backend is continuously serving or polling.

### 3.5 Connection limits and URL format

- The application pool is `5 + 10 = 15` connections per process (`DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10`). One API process fits comfortably within the inherited direct-connection limit at 0.25 CU (about 112 direct connections).
- Use the **direct** Neon endpoint for the single backend and for migrations. If the pooled endpoint is used instead, add `prepared_statement_cache_size=0` or verify protocol-level prepared-statement support before relying on SQLAlchemy's default cache.
- `DATABASE_URL` must use `postgresql+asyncpg://` and `?ssl=require`. Do not add `sslmode=` or `channel_binding=`; asyncpg rejects them as connect keywords.
- `DATABASE_SYNC_URL` is for offline Alembic and tooling. Online `alembic upgrade head` uses `DATABASE_URL`; verify the target before migrating.
- `/ready` has a 3-second database timeout. A Neon cold start can transiently return 503; retry rather than polling.

---

## 4. Backblaze B2 Free capacity

### 4.1 Inherited allowances

| Resource | Free allowance | Staging implication |
|---|---|---|
| Storage | First 10 GB account-wide | Includes all object versions, not only the visible latest version |
| Egress | Free up to 3x average monthly storage | At 10 GB stored, about 30 GB/month; Render's 5 GB outbound is tighter for proxied downloads |
| Class A/B/C | Free | Ordinary upload/list/read traffic is not the binding constraint |
| Class D | First 2,500/day free | Beyond that, paid; monitor reconciliation and download-heavy operations |
| Versioning | Buckets are versioned by default | `DeleteObject` hides the current version; older versions remain and count toward storage |
| Lifecycle | Available through the B2 console and Native API | A lifecycle rule for old/hidden versions is operationally required |
| S3 API | S3-compatible; presigned URLs and multipart supported | Compatible with the existing `aioboto3` adapter |
| Checksums | Botocore flexible checksums may be rejected by B2 | Keep `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` and `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required`; verify with a real PUT/GET |
| Card | No card required at signup; overage may require a payment method | $0 only while inside the allowance and without a payment method |

### 4.2 Capacity examples

At the current application limits:

- 10 GB / 10 MiB is roughly **950-1,000 objects** before version history.
- 10 GB / 1 MiB average is roughly **10,000 objects** before version history.
- Version history multiplies storage. Repeated ingest/delete cycles can exhaust 10 GB while the visible file list looks small.
- The 5 MiB extracted-text cap bounds the text/vector payload, not the original object size.
- There is no application-level B2 backup or point-in-time recovery. Staging data is disposable.

### 4.3 Lifecycle and deletion discipline

- Configure a lifecycle rule for old/hidden versions and unfinished multipart uploads.
- Verify billed storage after a delete test; a successful `DeleteObject` is not proof that all bytes were reclaimed.
- Do not run reconciliation `--fix` or orphan deletion until the typed storage-error path and the live bucket behavior have been validated.
- Keep the bucket private. Do not expose public bucket URLs, website configuration, or a public custom domain.

---

## 5. Combined duty-cycle envelope

The binding constraints are the shared Render 750-hour pool and the Neon 100 CU-hour allowance. They are not independent budgets.

| Duty cycle (each Render service) | Render instance-hours/month | Share of 750 | Neon backend active hours/month | Neon CU-hours at 0.25 CU | Verdict |
|---|---:|---:|---:|---:|---|
| 2 hours/day | 120 | 16% | 60 | 15 | Comfortable |
| 4 hours/day | 240 | 32% | 120 | 30 | Comfortable |
| 8 hours/day | 480 | 64% | 240 | 60 | Comfortable |
| 12 hours/day | 720 | 96% | 360 | 90 | Fits at the edge; no headroom |
| 24/7 | 1,440 | 192% | 720 | 180 | Not permitted; both allowances exhaust |

Assumptions: both services share the same duty cycle; Neon is active whenever the backend is active; compute is fixed at 0.25 CU; the 5-minute scale-to-zero tail is ignored. A frontend-only idle period or a backend-only session changes the arithmetic. Measure actual usage rather than treating this table as a guarantee.

**Recommended staging pattern:** a few hours per day, or at most about 8 hours/day for both services. Twelve hours/day is the edge. Do not run 24/7.

---

## 6. 512 MB / 0.1 CPU capacity risks

### 6.1 Measured baseline

| Measurement | Value | Caveat |
|---|---:|---|
| Backend import baseline | about 210 MB RSS | Prior M13 measurement |
| Tiny 5-page PDF + local embeddings | about 213.6 MB peak | Prior M13 measurement |
| Approximate headroom in 512 MB | 250-300 MB | Before multipart, parser copies, OCR, and other requests |
| Frontend Next server runtime | Unverified | Build success does not prove 512 MB runtime headroom |

The backend is not a thin process. The import baseline consumes roughly 40% of the container before a document is parsed.

### 6.2 Effective staging limits

| Setting | Effective value | Enforcement / consequence |
|---|---:|---|
| `MAX_FILE_SIZE_BYTES` | 10,485,760 (10 MiB) | Bounded read; 413 before parser/service work |
| `MAX_FILES_PER_REQUEST` | 2 | Rejected before the upload loop; send one file per request for acceptance |
| `MAX_EXTRACTED_TEXT_SIZE_BYTES` | 5,242,880 (5 MiB) | UTF-8 byte truncation before chunking and embedding |
| `MAX_ARCHIVE_EXPANSION_BYTES` | 104,857,600 (100 MiB) | Declared uncompressed-size preflight for ZIP/OOXML; actual parser memory can be higher |
| `MAX_PROCESSING_DURATION_SECONDS` | 600 | Per-stage remaining-time budget; timeout is a permanent failure |
| `MAX_DOCUMENT_PAGES` | 1,000 | PDF/PPTX/XLSX preflight; extracted page count rechecked |
| `OCR_ENABLED_DEFAULT` | `false` | OCR is off by default; Tesseract is the highest-probability OOM/CPU path |
| `INGESTION_MAX_CONCURRENCY` | 1 | One ingestion job at a time per process |
| `DEFAULT_EMBEDDING_PROVIDER` | `local` | Zero-download CPU projection; no model download |
| `DEFAULT_EMBEDDING_DIMENSIONS` | 384 | Matches the local provider |
| Database pool | 5 + 10 | Up to 15 connections per process |

### 6.3 Per-request memory path

| Stage | Approximate additional memory | Notes |
|---|---|---|
| Upload handler | Up to 10 MiB per file plus one 64 KiB chunk | Sequential files; the application buffer is bounded |
| Multipart parser | Platform-dependent; may spool to temp storage | Starlette parses before the handler; temp-disk use is not bounded by the application setting |
| Storage read | Up to 10 MiB per document | The adapter reads the full object |
| Parser | Library-dependent; can exceed the compressed size | PyMuPDF, python-docx, openpyxl, python-pptx |
| Archive expansion | Up to 100 MiB declared; actual parser memory may be higher | Preflight checks declared sizes, not runtime decompression |
| OCR | Tesseract plus page images | Off by default; can spike CPU and memory |
| Chunking/embeddings | Proportional to the 5 MiB text cap | Local projection is CPU-bound and comparatively small |

### 6.4 Parser thread limitation

- Preflight, parser extraction, OCR, and chunking run in `asyncio.to_thread` under `asyncio.wait_for`.
- A timeout raises a permanent ingestion failure, marks the job/document failed, purges partial chunks/embeddings, and releases the semaphore slot.
- Python cannot force-kill the worker thread. The underlying parser or Tesseract call may continue after the job has failed.
- Concurrency 1 prevents multiple parsers from competing, but it does not make one large parser fast. At 0.1 CPU, a large PDF or Office file can consume the full budget for a long time.
- The 600-second processing deadline bounds the wait, not necessarily the CPU work.

### 6.5 Safe staging practice

- Ingest **one document at a time**, one file per request, even though the request limit is two.
- Use synthetic text/Markdown/CSV files under 1 MiB; PDFs of 1-5 pages; small PPTX decks; small XLSX workbooks.
- Do not enable OCR for the cohort. If a single OCR case is required, use a 1-2 page, 150 DPI scan and expect a long run.
- Do not test archives near the 100 MiB declared expansion limit.
- Keep `DEFAULT_EMBEDDING_PROVIDER=local`; do not switch to a model-downloading provider on the ephemeral Free instance.
- Do not add a second API process, a separate ingestion worker, or concurrent uploads.
- Treat the 512 MB envelope as suitable for a **closed synthetic cohort only**, not real customer documents, OCR-heavy workloads, concurrent users, or 24/7 availability.

---

## 7. Monitoring and guardrails

| Resource | What to watch | Action before exhaustion |
|---|---|---|
| Render instance-hours | Workspace usage against 750 hours/month | Reduce duty cycle; stop the frontend when not in use; do not add services |
| Render bandwidth | Workspace usage against 5 GB/month | Use smaller files; avoid repeated downloads; remember downloads proxy through Render |
| Render pipeline minutes | Workspace usage against 500 minutes/month | Keep `autoDeploy: false`; deploy manually and sparingly |
| Neon CU-hours | Project usage against 100 CU-hours/month | Fix compute at 0.25 CU; measure active hours; avoid `/ready` polling; reduce backend duty cycle |
| Neon storage | Project usage against 1 GB | Keep synthetic documents small; monitor chunks/vectors; delete test data deliberately |
| Neon egress | Project usage against 5 GB/month | Keep response sizes small; avoid bulk exports |
| B2 storage | Billed size including versions against 10 GB | Configure lifecycle for old versions; verify delete reclaim; keep files small |
| B2 Class D | Daily count against 2,500/day | Avoid list-heavy reconciliation and repeated download tests |
| B2 egress | Average monthly storage x 3 | Render's 5 GB outbound is usually the tighter limit for downloads |

Operational rules:

- Do not add keep-alives, uptime pings, or scheduled probes.
- Do not poll `/ready`; use `/health` for liveness and deliberate `/ready` checks only.
- Keep one Uvicorn worker and one API process.
- Keep `INGESTION_MAX_CONCURRENCY=1`.
- Do not add a paid Render disk, paid instance type, Render Postgres, Redis, Qdrant, or other paid add-on.
- Keep the B2 bucket private and lifecycle-managed.
- Record usage weekly during acceptance and stop if a resource approaches 80% of its allowance.

---

## 8. What would invalidate this envelope

The following are outside the $0/no-card staging envelope:

- Running both Render services 24/7, or adding a third Free service to the workspace.
- Keep-alives or scheduled traffic that defeats spin-down.
- Multiple Uvicorn workers, a separate ingestion worker, or concurrent ingestion.
- Uploading near-limit files, two 10 MiB files per request, large archives, OCR-heavy scans, or real customer documents.
- Switching to a model-downloading embedding provider or adding a local persistent upload path.
- Enabling public publishing, the Developer API, custom provider endpoints, or platform-paid LLM keys.
- Neon compute autoscaling above 0.25 CU, or frequent `/ready`/chat/upload traffic that keeps compute awake.
- B2 version accumulation without lifecycle management, or B2 storage/egress above the allowance.
- Adding a payment method or a paid upgrade. That changes the cost posture and requires explicit approval.

If any of these become necessary, the correct response is to stop and re-plan against a paid or larger free-tier topology, not to stretch this envelope.

---

## 9. Inherited sources and confidence

| Source | Used for | Confidence |
|---|---|---|
| `docs/m13/M13_FREE_TIER_COST_AND_LIMITS.md` | Render, Neon, and B2 allowances; overage and suspension behavior; 750-hour and CU-hour arithmetic | Inherited; provider pages were fetched during the M13 Phase 1 research window (2026-11-12) |
| `docs/m13/M13_FREE_TIER_ARCHITECTURE_DECISION.md` | Topology, host selection, 512 MB baseline, operational posture | Inherited |
| `docs/m13/M13_2_RUNTIME_LIMITS.md` | Effective staging limits, 512 MB/0.1 CPU risks, parser thread limitation, operational guidance | Inherited |
| `docs/m13/M13_3_RENDER_BLUEPRINT_REVIEW.md` | `exec`, `CORS_ORIGIN_REGEX=^$`, development-only `create_all`, startup behavior | Verified in the M13.3 review |
| `render.yaml` | Two Free services, shared pool, `--workers 1`, dispatcher 3600, upload/embedding/storage settings | Repository source |
| `backend/app/core/config.py`, `backend/app/main.py` | Code defaults, gating, startup recovery, health/readiness | Repository source |
| `frontend/lib/api.ts` | Frontend API base behavior | Repository source |

**Not verified here:** live Render instance-hours, live Neon CU-hours, live B2 billed storage including versions, frontend Next server RSS, and current provider terms. No external calls were made. This document is a staging envelope and a set of operating constraints, not a capacity guarantee.
