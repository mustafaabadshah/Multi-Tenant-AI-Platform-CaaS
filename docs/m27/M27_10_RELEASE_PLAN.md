# M27.10 — Release Plan & Deployment Allowlist

## 1. Zero Database Migration Decision

- **Current Neon Staging Revision:** `0017_m22_conversation_attachments`
- **M27 Migration Status:** **ZERO MIGRATIONS REQUIRED.**
- The existing `Document`, `DocumentVersion`, and `DocumentChunk` schema accommodates web sources using `mime_type="text/html"`, `file_path=canonical_url`, and `metadata_json={"source_type": "web", "storage_mode": "REFERENCE", ...}`.
- No live database modification, table locking, or schema alterations are needed.

---

## 2. Configuration & Environment Variables

| Variable | Default Value | Description |
|---|---|---|
| `WEB_READER_ENABLED` | `true` | Enables outbound public web page reader (`web_read_url`) |
| `WEB_SEARCH_ENABLED` | `true` | Enables agentic public web search (`web_search`) |
| `WEB_KB_IMPORT_ENABLED` | `true` | Enables saving web sources to Knowledge Bases (`web_save_to_kb`) |
| `WEB_ALLOWED_DOMAINS` | `""` | Comma-separated domain allowlist (empty permits all public domains allowed by SSRF policy) |
| `BRAVE_SEARCH_API_KEY` | `None` | Optional commercial search API key; defaults to `MockSearchProvider` when unset |
| `WEB_MAX_PAGES_PER_REQUEST` | `5` | Maximum pages processed per request |

---

## 3. Git Release Allowlist

The exact set of modified and newly created files for M27 release:

### Backend Source Files
- `backend/app/api/v1/conversations.py`
- `backend/app/assistant_runtime/context.py`
- `backend/app/assistant_runtime/runtime.py`
- `backend/app/core/config.py`
- `backend/app/schemas/assistant.py`
- `backend/app/services/tools/builtin.py`
- `backend/app/services/tools/registry.py`
- `backend/app/services/web/__init__.py`
- `backend/app/services/web/ssrf.py`
- `backend/app/services/web/extractor.py`
- `backend/app/services/web/reader.py`
- `backend/app/services/web/search.py`
- `backend/app/services/web/context_store.py`
- `backend/app/services/web/kb_saver.py`

### Backend Test Files
- `backend/tests/test_m27_web_intelligence.py`

### Frontend Source Files
- `frontend/app/dashboard/conversations/page.tsx`
- `frontend/components/chat/MarkdownRenderer.tsx`
- `frontend/lib/api.ts`

### Documentation Suite
- `docs/m27/M27_1_EXISTING_CAPABILITY_AUDIT.md`
- `docs/m27/M27_2_SECURE_WEB_FETCH.md`
- `docs/m27/M27_3_WEB_CONTENT_EXTRACTION.md`
- `docs/m27/M27_4_SEARCH_PROVIDER_ARCHITECTURE.md`
- `docs/m27/M27_5_CONVERSATION_WEB_CONTEXT.md`
- `docs/m27/M27_6_KNOWLEDGE_BASE_WEB_SOURCES.md`
- `docs/m27/M27_7_AGENTIC_WEB_TOOLS.md`
- `docs/m27/M27_8_FRONTEND_UX.md`
- `docs/m27/M27_9_SECURITY_AND_REGRESSION.md`
- `docs/m27/M27_10_RELEASE_PLAN.md`
- `docs/m27/M27_MASTER_FINAL_REPORT.md`

---

## 4. Rollback Plan

If an unexpected production defect occurs:
1. **Feature Flag Kill Switch:** Set `WEB_READER_ENABLED=false` and `WEB_SEARCH_ENABLED=false` in Render environment variables. Outbound web requests immediately stop without redeployment.
2. **Git Rollback:** Revert commit back to `c4b935b2a582c7c42dce3e81d716e93bcef9888d`.
3. **Database Impact:** Zero impact. No schema migration was run, so no database rollback or downgrade migration is required.
