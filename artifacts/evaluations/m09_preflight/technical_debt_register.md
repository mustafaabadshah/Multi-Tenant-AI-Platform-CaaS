# M09 Preflight: Technical Debt & Architectural Defect Register

**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Date:** November 10, 2026  
**Auditor:** Principal Software Architect  
**Milestone:** M09 — Preflight Audit  

---

## 1. Executive Summary

This register catalogs known technical debt, structural edge cases, and architectural defects identified during the Stage 0 preflight inspection. Each item is classified by severity, affected component, blast radius, and designated milestone stage for resolution.

---

## 2. Technical Debt & Defect Catalog

### TD-01: Public Assistant Identifier Entropy (64-bit vs 128-bit)
- **Component:** `backend/app/services/publishing_service.py`
- **Severity:** **HIGH**
- **Root Cause:** Identifier generator uses `secrets.token_hex(8)` (16 hex chars = 64 bits of entropy).
- **Risk:** High-scale distributed brute force could theoretically collide or enumerate public endpoints.
- **Resolution Plan (Stage 1):** Upgrade to 16 bytes (32 hex chars = 128 bits of entropy) for all newly generated publications (`pub_[32 hex chars]`). Support backward compatibility for existing 16-hex IDs in the database.

### TD-02: Qdrant Vector Store Empty `document_ids` Filter Bypass
- **Component:** `backend/app/vectorstores/qdrant_store.py`
- **Severity:** **CRITICAL**
- **Root Cause:** When `filter_criteria.document_ids` is evaluated as an empty list `[]` (e.g., when a public assistant connects to a knowledge base containing zero public documents), `if filter_criteria.document_ids:` evaluates to `False`. Qdrant skips adding the `document_id` filter condition and searches all documents across the KB.
- **Risk:** Potential retrieval of confidential chunks during public chat.
- **Resolution Plan (Stage 1):** Align with `fts_store.py` and `pgvector_store.py` by adding:
  ```python
  if filter_criteria.document_ids is not None and len(filter_criteria.document_ids) == 0:
      return []
  ```

### TD-03: Public Chat Session to Conversation Mapping Disconnect
- **Component:** `backend/app/api/v1/public_chat.py`
- **Severity:** **HIGH**
- **Root Cause:** Public chat resolves conversations via `select(Conversation).where(..., Conversation.user_id.is_(None)).order_by(Conversation.created_at.desc()).limit(1)`.
- **Risk:** Concurrent anonymous visitors chatting with the same public assistant could collide on the same conversation thread instead of having distinct session histories.
- **Resolution Plan (Stage 1):** Add `conversation_id` foreign key column to `public_chat_sessions` table (or establish explicit 1:1 mapping by session token) so each visitor's session token maps deterministically to their own unique conversation record.

### TD-04: Developer API Key Coarse Scoping & Lack of Assistant Restriction
- **Component:** `backend/app/services/api_key_service.py` & `backend/app/api/v1/developer.py`
- **Severity:** **MEDIUM**
- **Root Cause:** Keys currently grant tenant-wide access to all assistants without the ability to restrict a key to a specific assistant UUID.
- **Resolution Plan (Stage 1):** Support optional `assistant_id` restriction on API keys. Add scopes: `assistant:eval`, `knowledge:read`.

### TD-05: In-Process Background Task Execution Loss on Restart
- **Component:** `backend/app/ingestion/service.py` & `backend/app/models/ingestion.py`
- **Severity:** **HIGH**
- **Root Cause:** Background document ingestion tasks are spawned via `asyncio.create_task`. If the backend process crashes or restarts, jobs remain stuck in `RUNNING` or `PROCESSING` state in the database without automatic recovery.
- **Resolution Plan (Stage 5):** Implement a durable job state machine with startup recovery: on startup, identify orphaned `RUNNING` jobs, mark them as `FAILED_INTERRUPTED` or retry them if attempts $< \text{max\_attempts}$.

### TD-06: Pre-Invocation Quota Reservation Race Condition
- **Component:** `backend/app/services/quota_service.py`
- **Severity:** **MEDIUM**
- **Root Cause:** Quota check verifies token limits before inference, but usage is only logged after inference completes. Rapid concurrent requests can execute simultaneously before either has updated the usage logs.
- **Resolution Plan (Stage 4):** Implement an atomic pre-invocation estimated token reservation and post-invocation reconciliation mechanism.

### TD-07: Inaccurate Terminology: PostgreSQL Full-Text vs Okapi BM25
- **Component:** `docs/architecture/ai-runtime-and-retrieval.md` & `backend/app/vectorstores/fts_store.py`
- **Severity:** **LOW / CLARITY**
- **Root Cause:** Documentation in some places refers to lexical search as BM25, whereas the underlying PostgreSQL implementation uses `ts_rank_cd` (cover density).
- **Resolution Plan (Stage 2/7):** Honestly document the algorithm as PostgreSQL Cover Density (`ts_rank_cd`), clearly distinguishing it from Okapi BM25.

### TD-08: Lack of Real Observability & Span Tracing
- **Component:** Platform execution runtime
- **Severity:** **MEDIUM**
- **Root Cause:** Telemetry is currently limited to basic Python logger outputs and `provider_usage_logs` token counts. Developers cannot inspect individual retrieval latency vs provider latency breakdown.
- **Resolution Plan (Stage 3):** Implement lightweight structured request lifecycle tracing capturing timestamps and latency spans (retrieval, provider, streaming) with strict redaction of sensitive prompts/credentials.

### TD-09: Absence of Automated AI Evaluation & Groundedness Testing
- **Component:** Platform quality verification
- **Severity:** **HIGH (M09 TARGET)**
- **Root Cause:** The platform currently lacks an integrated framework to benchmark assistant answer accuracy, retrieval Recall@K, and citation groundedness against ground-truth datasets.
- **Resolution Plan (Stage 2):** Implement `backend/app/evaluation/` with deterministic local datasets and evaluators for Recall@K, MRR, Faithfulness, and Citation presence.
