# Milestone M10 Stage 1: Security and Reliability Verification Audit

**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Host Environment:** Windows 10 Pro, 8 GB RAM, Intel Core i3-7100U @ 2.40 GHz, Intel HD 620, CPU-Only  
**Audit Date:** 2026-11-10  
**Milestone:** M10 Stage 1  
**Status:** **STAGE_1_VERIFIED (PASS)**  

---

## 1. Executive Summary

Milestone M10 Stage 1 performed a targeted, evidence-based security and reliability audit of the platform across all 9 critical security domains. 

A dedicated security verification test suite ([`tests/test_m10_stage1_security_verification.py`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/tests/test_m10_stage1_security_verification.py)) with 15 negative security tests was implemented and executed alongside existing regression suites.

One defect was identified during test execution:
- **Defect:** In [`PublishingService.get_or_create_public_session`](file:///E:/MM%20Office/Multi-Tanant-CaaS/backend/app/services/publishing_service.py), expired public chat sessions (`expires_at <= now`) were filtered out of the select query, causing the code to attempt inserting a new session record using the exact same `session_token`. Because `public_chat_sessions.session_token` has a `UNIQUE` constraint, this triggered an unhandled `sqlite3.IntegrityError` instead of rejecting the expired session.
- **Fix:** Refactored `get_or_create_public_session` to look up by `session_token` and explicitly check expiration. If expired, it logs a warning and raises `HTTPException(status_code=401, detail="Public chat session has expired. Please start a new session.")`. If no token is passed, it generates a fresh cryptographically random unguessable token.

All 15 targeted security tests and all 238 full backend regression tests pass with **0 failures**.

---

## 2. Domain-by-Domain Security Assessment

### 1A. Tenant Isolation
- **Files Inspected:**
  - `backend/app/api/deps.py`
  - `backend/app/api/v1/assistants.py`
  - `backend/app/api/v1/conversations.py`
  - `backend/app/api/v1/documents.py`
  - `backend/app/api/v1/evaluation.py`
  - `backend/app/api/v1/providers.py`
  - `backend/app/repositories/`
- **Security Boundary:** 
  1. Header `X-Tenant-ID` is verified against user membership via `get_current_tenant_context` in `deps.py`. If user is not an active member, returns `403 Forbidden`.
  2. Every database query enforces `tenant_id == ctx.tenant.id`. Foreign key and composite integrity prevent cross-tenant referencing.
- **Negative Scenarios Verified:**
  - Tenant B attempts to read/update Tenant A's assistant $\rightarrow$ `404 Not Found`.
  - Tenant B attempts to read/stream to Tenant A's conversation $\rightarrow$ `404 Not Found`.
  - Tenant B attempts to read Tenant A's documents, extracted text, chunks, or ingestion jobs $\rightarrow$ `404 Not Found`.
  - Tenant B attempts to fetch Tenant A's evaluation datasets or runs $\rightarrow$ `404 Not Found`.
  - Tenant B attempts to trigger an evaluation run on Tenant A's assistant $\rightarrow$ `400 Bad Request`.
  - Tenant B queries usage records $\rightarrow$ only receives Tenant B's usage (0 tokens); zero leakage of Tenant A's 7,000 tokens.
  - Revoked/inactive member access $\rightarrow$ `403 Forbidden` (`Access denied: You do not have active membership`).
- **Residual Risk:** None identified within monolithic database boundary.

---

### 1B. Public Publishing Security
- **Files Inspected & Modified:**
  - `backend/app/api/v1/public_chat.py`
  - `backend/app/services/publishing_service.py` (Modified to fix expired session handling)
- **Security Boundary:**
  1. Public ID uses 128-bit cryptographic entropy (`pub_` + 32 hexadecimal characters).
  2. Embed requests enforce domain whitelist (`allowed_domains`). Origin and Referer headers are parsed and checked.
  3. Anonymous visitors receive a cryptographically random session token bound to a dedicated conversation thread in `public_chat_sessions`.
  4. Public access boundary strictly restricts retrieval to documents with `access_level == "PUBLIC"`.
- **Negative Scenarios Verified:**
  - Active public assistant accessible $\rightarrow$ `200 OK`.
  - Unpermitted origin on embedded assistant (`Origin: https://evil-phishing.com`) $\rightarrow$ `403 Forbidden`.
  - Direct link navigation (missing origin/referer) $\rightarrow$ `200 OK` (permitted per policy).
  - Unpublish assistant $\rightarrow$ public metadata returns `404 Not Found`, chat stream returns `403 Forbidden`.
  - Expired session token reuse $\rightarrow$ rejected with `401 Unauthorized` (`Public chat session has expired`).
- **Residual Risk:** Origin and Referer headers can be spoofed in non-browser environments; this is documented as an embed restriction, not authentication.

---

### 1C. Developer API Key Security
- **Files Inspected:**
  - `backend/app/services/api_key_service.py`
  - `backend/app/api/v1/developer.py`
- **Security Boundary:**
  1. Keys are generated with 256-bit cryptographically secure randomness (`mmaip_live_[32 bytes]`).
  2. Raw token is returned **exactly once** upon creation.
  3. Only the SHA-256 hash is persisted in `api_keys.key_hash` (unique index).
  4. Scope enforcement (`assistant:read`, `assistant:chat`) verified on every API request.
  5. Assistant-level scoping (`api_keys.assistant_id`) restricts developer keys to designated assistants.
- **Negative Scenarios Verified:**
  - Invalid/forged API key $\rightarrow$ `401 Unauthorized`.
  - Revoked key (`DELETE /api/v1/developer/api-keys/{id}`) $\rightarrow$ `401 Unauthorized`.
  - Key lacking required scope (e.g., `assistant:read` attempting chat) $\rightarrow$ `403 Forbidden`.
  - Key restricted to Assistant A attempting to chat with Assistant B $\rightarrow$ `403 Forbidden`.
  - Key attempting cross-tenant assistant access $\rightarrow$ `404 Not Found`.
- **Residual Risk:** Low. Keys are hashed with SHA-256 and never logged.

---

### 1D. Qdrant and Retrieval ACL Security
- **Files Inspected:**
  - `backend/app/vectorstores/qdrant_store.py`
  - `backend/app/vectorstores/pgvector_store.py`
  - `backend/app/retrieval/service.py`
  - `backend/app/assistant_runtime/runtime.py`
- **Security Boundary:**
  1. Qdrant empty filter safeguard: `if filter_criteria.document_ids is not None and len(filter_criteria.document_ids) == 0: return []`.
  2. Mandatory tenant condition `tenant_id == filter.tenant_id` and `knowledge_base_id in filter.knowledge_base_ids` on all vector queries.
  3. Assistant runtime filters target documents to `access_level == 'PUBLIC'` for public chat sessions.
  4. Deleted documents (`status == 'DELETED'`) are excluded before vector and FTS retrieval.
- **Negative Scenarios Verified:**
  - Empty document ID allowlist (`document_ids=[]`) $\rightarrow$ returns `[]` immediately without executing open search.
  - Cross-tenant vector search $\rightarrow$ returns 0 results.
  - Deleted document chunks $\rightarrow$ excluded from lexical, semantic, and hybrid search.
  - Hybrid RRF fusion with department restrictions $\rightarrow$ unauthorized department chunks never re-enter fused candidate pool.
  - Public runtime retrieval $\rightarrow$ confidential documents are excluded from `target_doc_ids`.
- **Residual Risk:** Qdrant service errors fail closed by returning `[]`.

---

### 1E. BYOK and Secret Protection
- **Files Inspected:**
  - `backend/app/services/byok_vault.py`
  - `backend/app/assistant_runtime/runtime.py`
  - `backend/app/api/v1/providers.py`
- **Security Boundary:**
  1. Provider credentials are encrypted at rest using Fernet with application encryption key.
  2. Masked API keys (`sk-***...`) are stored for display; plaintext is never exposed in API responses.
  3. Commercial providers (`openai`, `anthropic`, `gemini`, `groq`) require active BYOK credentials in tenant vault.
  4. Zero silent fallback to platform-owned credentials.
- **Negative Scenarios Verified:**
  - Assistant configured with `openai` without BYOK credential in tenant vault $\rightarrow$ streaming response immediately yields `message_error` with `Provider 'openai' is not configured with an active BYOK credential...` and halts execution.
  - Revoked BYOK credential $\rightarrow$ rejected during runtime key resolution.
  - GET `/api/v1/providers/credentials` $\rightarrow$ returns `api_key_masked`, never plaintext.
- **Residual Risk:** Low. Key resolution happens strictly in-memory during request dispatch.

---

### 1F. Quota Concurrency
- **Files Inspected:**
  - `backend/app/services/quota_service.py`
- **Security Boundary:**
  1. `reserve_quota()` verifies monthly token limits and daily request limits against persisted usage PLUS active in-flight reservations.
  2. In-flight reservations are managed in a thread-safe in-process dictionary guarded by `threading.Lock()`.
  3. Expired reservations (> 300 seconds TTL) are purged automatically.
  4. Failed requests or provider errors explicitly release reservations.
- **Negative Scenarios Verified:**
  - In-flight reservation of 4,000 tokens against a 5,000-token quota blocks a concurrent 2,000-token request with HTTP 429 (`Monthly token limit exceeded`).
  - Releasing reservation allows subsequent request to succeed.
- **Architectural Qualification:**
  - *Known Limitation:* The reservation lock is thread-safe within a single process. In horizontally scaled multi-instance deployments, concurrent requests across separate processes would require a shared distributed lock or database table (e.g., PostgreSQL `SELECT ... FOR UPDATE` on `tenant_quotas`).

---

### 1G. Storage Isolation
- **Files Inspected:**
  - `backend/app/storage/base.py`
  - `backend/app/storage/local.py`
  - `backend/app/storage/s3.py`
- **Security Boundary:**
  1. Filenames are sanitized via `sanitize_filename` (strips directories, double dots, illegal characters).
  2. `LocalStorageProvider` verifies resolved real paths start with `base_dir / tenant_id` to prevent traversal.
  3. `S3StorageProvider` prefixes every operation (`save`, `get`, `delete`, `exists`, `get_size`) with `{tenant_id}/`.
- **Negative Scenarios Verified:**
  - `../../etc/passwd` $\rightarrow$ sanitized to `passwd`.
  - `..\\..\\windows\\system32\\cmd.exe` $\rightarrow$ sanitized to `cmd.exe`.
  - Absolute paths (`/var/log/syslog`) $\rightarrow$ sanitized to `syslog`.
  - S3 key generation with leading slashes (`/nested/doc.pdf`) $\rightarrow$ normalized under `{tenant_id}/nested/doc.pdf`.
- **Residual Risk:** Direct S3 bucket access must be restricted to backend service credentials with server-side validation.

---

### 1H. Background Job Reliability
- **Files Inspected:**
  - `backend/app/services/ingestion/recovery.py`
  - `backend/app/services/ingestion/service.py`
  - `backend/app/main.py`
- **Security Boundary:**
  1. Startup hook `recover_orphaned_jobs()` queries all `IngestionJob` and `EmbeddingJob` records stuck in `PROCESSING` on process start.
  2. Transitions them cleanly to `FAILED` with stage `INTERRUPTED` and error category `PROCESS_RESTART`.
  3. Associated documents left in `PROCESSING` are unlocked and transitioned to `FAILED`.
  4. Duplicate upload of identical file hash within the same KB creates a queued reprocessing job rather than duplicating storage files.
- **Negative Scenarios Verified:**
  - Orphaned jobs from simulated crash recovered cleanly and documents unlocked.
  - Safe retry available via `POST /api/v1/ingestion/jobs/{id}/retry`.
- **Residual Risk:** Resuming a failed ingestion job restarts the pipeline from extraction rather than partial chunk resume; this ensures clean idempotent recreation of chunks and vector points without orphaned records.

---

### 1I. Observability Security
- **Files Inspected:**
  - `backend/app/observability/tracer.py`
  - `backend/app/api/v1/observability.py`
- **Security Boundary:**
  1. Recursive `sanitize_value` redacts API keys (`sk-*`, `mmaip_live_*`), Bearer tokens, passwords, and secrets across strings, dicts, and lists.
  2. Traces are stored in tenant-partitioned ring buffers (`_tenant_traces[tenant_id]`).
  3. API endpoints `/api/v1/observability/traces` only return traces belonging to the authenticated workspace.
- **Negative Scenarios Verified:**
  - Dirty telemetry attributes containing OpenAI keys, platform keys, and passwords $\rightarrow$ successfully sanitized with `[REDACTED_API_KEY]`, `[REDACTED_TOKEN]`, and `[REDACTED]`.
  - Tenant B cannot view Tenant A's traces.
- **Architectural Qualification:**
  - *Known Limitation:* The tracer maintains an in-memory ring buffer (up to 1,000 traces per process). Server restart resets the buffer. Telemetry is not shared across multi-process clusters.

---

## 3. Summary of Remediations Applied in Stage 1

| Component | File | Issue | Remediation | Test Verification |
|---|---|---|---|---|
| Public Chat Session Expiration | `backend/app/services/publishing_service.py` | Expired session token caused duplicate key collision on `public_chat_sessions.session_token` | Added lookup by `session_token` and explicit check for `expires_at <= now`; raises `HTTPException(401, "Public chat session has expired...")` | `test_expired_public_session_isolation` PASSED |

---

## 4. Stage 1 Gate Decision

- **Gate Status:** **STAGE_1_PASS**
- **Criteria Met:**
  - [x] Zero critical tenant-isolation vulnerabilities.
  - [x] Public publishing domain whitelist and revocation verified.
  - [x] Developer API key scopes and assistant restrictions enforced.
  - [x] Qdrant empty filter fails closed.
  - [x] Commercial providers strictly require tenant BYOK credentials with zero platform fallback.
  - [x] Quota concurrency in-flight reservations prevent overspending.
  - [x] Storage path traversal rejected across all variants.
  - [x] Background job recovery verified.
  - [x] Observability secrets redacted and access tenant-scoped.
  - [x] Full regression test suite passing: **238 passed, 18 skipped, 0 failed**.
