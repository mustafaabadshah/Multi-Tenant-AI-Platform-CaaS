# M09 Preflight: M08 Security & Integration Audit

**Project:** Multi-Tenant AI Assistant Platform (Chatbot-as-a-Service / CaaS)  
**Date:** November 10, 2026  
**Auditor:** Application Security Engineer & Principal Architect  
**Milestone:** M09 — Preflight Security Audit  

---

## 1. Executive Summary: M08 Security Posture

Milestone M08 introduced public distribution surfaces (standalone web chat, website embed widgets, and developer REST APIs). While multi-tenant database isolation and SHA-256 key hashing were correctly established, a rigorous security audit identified several critical areas requiring hardening in **Stage 1 (M08 Security Closure)** before proceeding to new feature work.

---

## 2. In-Depth Audit Across 9 Security Dimensions

### 2.1. Public Assistant Identifier Entropy
- **Current State:** `generate_opaque_public_id()` in `backend/app/services/publishing_service.py` returns `f"pub_{secrets.token_hex(8)}"`.
- **Entropy Analysis:** 8 random bytes = 16 hexadecimal characters = **64 bits of entropy**. While unguessable under normal conditions, 64 bits falls short of the enterprise standard ($\ge 128$ bits) against birthday attacks and high-scale automated enumeration.
- **Required Hardening (Stage 1):**
  1. Upgrade generation to 16 bytes (32 hex characters = **128 bits of cryptographic entropy**).
  2. Maintain strict backward compatibility: existing 16-hex `pub_...` IDs in database must continue resolving without breaking existing public URLs.
  3. Support controlled identifier rotation in Assistant Studio.

### 2.2. Publication Authorization & Immediate Revocation
- **Current State:** `get_public_assistant_metadata` and `public_chat_stream` check `pub.is_active` and `pub.visibility == "PUBLIC"`.
- **Vulnerability / Edge Case:** If an assistant is published, an anonymous visitor generates a `session_token`. If an admin immediately deactivates or unpublishes the assistant (`is_active = False`), does an ongoing or subsequent chat stream with an existing session token halt immediately?
- **Finding:** In `public_chat.py`, `pub.is_active` is verified at the start of each request. However, `PublicChatSession` records are not marked invalidated. Stage 1 must ensure session lookups explicitly verify parent publication liveness.

### 2.3. Public Knowledge Access & Document ACLs
- **Current State:** In `backend/app/assistant_runtime/runtime.py` (lines 148–158), if `is_public` is True, `Document.access_level == 'PUBLIC'` is enforced to collect `target_doc_ids`.
- **Identified Defect:**
  - If a knowledge base contains *only* confidential documents, `target_doc_ids` is evaluated as an empty list `[]`.
  - In `backend/app/vectorstores/qdrant_store.py` (line 167), the filter condition is written:
    ```python
    if filter_criteria.document_ids:
        must_conditions.append(qmodels.FieldCondition(key="document_id", match=qmodels.MatchAny(any=[str(d) for d in filter_criteria.document_ids])))
    ```
    When `filter_criteria.document_ids` is `[]`, `if filter_criteria.document_ids:` evaluates to `False`. Thus, Qdrant skips document filtering and searches the entire knowledge base, potentially retrieving confidential chunks!
- **Required Fix (Stage 1):** Align `qdrant_store.py` with `fts_store.py` and `pgvector_store.py`:
  ```python
  if filter_criteria.document_ids is not None and len(filter_criteria.document_ids) == 0:
      return []
  ```

### 2.4. Anonymous Conversation Ownership & IDOR Protection
- **Current State:** Migration `0008` made `conversations.user_id` nullable (`nullable=True`). Public chat associates conversations by `(tenant_id, assistant_id, user_id=None)`.
- **Security Check:**
  - Can an anonymous visitor manipulate session parameters to view authenticated internal conversation histories?
  - Can Visitor A read Visitor B's conversation?
- **Finding:** Anonymous visitors communicate solely via SSE token streaming and do not have access to `/api/v1/conversations/` CRUD endpoints (which require authenticated JWT `get_current_user`). However, public session resolution in `public_chat.py` matches the most recent conversation where `user_id is None`. This could cause two concurrent public visitors to cross-talk if not strictly partitioned by `session_token`! Stage 1 must bind `public_chat_sessions.conversation_id` explicitly.

### 2.5. Developer API Key Security & Scope Enforcement
- **Current State:**
  - Keys use prefix `mmaip_live_` followed by 32 cryptographically secure url-safe bytes.
  - Stored strictly as SHA-256 hashes in `api_keys.key_hash`.
  - Plaintext key is displayed exactly once upon generation.
  - Verification enforces `api_key.is_active` and `expires_at`.
- **Finding:** Scopes are currently coarse-grained (`assistant:read`, `assistant:chat`). Keys currently grant access to *all* assistants within the tenant.
- **Required Hardening (Stage 1):** Add support for optional per-key assistant restrictions (e.g., scoping a key to a specific assistant UUID).

### 2.6. Embed Security, Iframe Sandboxing & Origin Headers
- **Current State:** Embeds run in an iframe loaded from `/embed/[publicId]`.
- **Crucial Security Principle:** `Origin` and `Referer` headers are browser-level restrictions, not cryptographic authentication. Anyone using `curl` or a custom client can spoof headers.
- **Verification:**
  - Browser embeds are sandboxed with minimal attributes.
  - Public standalone chat (`/p/`) has its own access rules independent of host embeds.
  - Host-to-iframe communication does not use unsafe wildcard `postMessage('*')`.

### 2.7. TypeScript & Python SDK Packaging & Type Safety
- **Current State:**
  - `sdk/typescript/` and `sdk/python/` exist as clean, standalone libraries.
  - Neither SDK depends on internal platform code.
- **Verification Need (Stage 1):** Execute local build, type-check, and automated unit test suites for both SDKs using local mock/live test servers.

### 2.8. API Rate Limiting & Abuse Prevention
- **Current State:** Quotas are enforced at the monthly/daily tenant token level.
- **Vulnerability:** An unauthenticated visitor on `/p/[publicId]` could trigger hundreds of concurrent LLM streaming requests, exhausting the tenant's daily quota ("denial-of-wallet" attack).
- **Required Hardening (Stage 1):** Implement client IP / session rate limiting on public endpoints to throttle abusive requests.

### 2.9. Usage Attribution & Quota Race Conditions
- **Current State:** `QuotaService.check_quota` verifies current token counts against limits, and increments after the request completes.
- **Race Condition Risk:** Rapid concurrent requests can execute simultaneously before either has logged its tokens, exceeding limits.
- **Required Hardening (Stage 1):** Implement pre-invocation token reservation to atomically account for in-flight requests.
