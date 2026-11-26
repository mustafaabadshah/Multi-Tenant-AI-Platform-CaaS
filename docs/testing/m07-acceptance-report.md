# M07 Acceptance Test Report

## Executive Summary
- **Milestone**: M07 — Knowledge Studio, Retrieval Playground, BYOK Vault & Provider Management
- **Status**: `PASS`
- **Backend Test Suite**: 189 passed, 18 skipped, 0 failures (execution time: 94.51s)
- **Frontend Typecheck & Build**: `npx tsc --noEmit` clean (0 errors), Next.js production build (`npm run build`) succeeded with 16 optimized routes.
- **M05 Recovery Drills**: Preserved as `DEFERRED — NOT RUN` in non-Docker testing environments.

---

## Acceptance Verification Breakdown

| Test Area | Target Feature | Test Count | Result | Evidence |
|---|---|:---:|:---:|---|
| **Provider Registry** | Groq, Anthropic, Gemini, OpenAI, OmniRoute, Mock | 2 | `PASS` | `test_provider_registry_and_capabilities`, `test_provider_directory_api_endpoint` |
| **BYOK Key Vault** | Fernet encryption at rest, masked key, connection test, rotation, revocation, deletion | 2 | `PASS` | `test_byok_credential_lifecycle`, `test_byok_cross_tenant_isolation` |
| **Server-Side Quotas** | Pre-invocation rejection (429), atomic logs, monthly/daily counters | 2 | `PASS` | `test_quota_accounting_and_summary_endpoint`, `test_quota_service_rejection_at_limit` |
| **Safe URL Ingestion** | SSRF loopback, RFC 1918, cloud metadata 169.254.169.254, DNS rebinding | 3 | `PASS` | `test_ssrf_ip_validator_blocks_private_and_metadata`, `test_url_ingest_endpoint_blocks_ssrf`, `test_url_ingest_mock_success` |
| **Chunk Inspector** | Chunk indexing, character & token counts, page number, heading paths | 1 | `PASS` | `test_document_chunk_inspector_provenance` |
| **Retrieval Playground** | Measured latency ms, sparse score (`ts_rank_cd`), dense score, hybrid RRF rank | 1 | `PASS` | `test_retrieval_playground_query_and_metrics` |
| **Full Regression** | M01 through M06 backward compatibility | 178 | `PASS` | Full pytest suite pass across all auth, RBAC, assistants, versioning, and storage |
| **Ordinary User E2E** | Assistant creation, versioning, and runtime execution | 1 | `PASS` | `test_complete_ordinary_user_assistant_journey` |
