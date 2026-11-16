# M25 — Security, Regression & Multi-Tenant Boundaries

## 1. Security Regression Matrix

| Scope | Threat Vector | Safeguard | Automated Test Status |
|---|---|---|---|
| M22 Attachments | Cross-tenant document download | Scoped query by `tenant_id` + `conversation_id` | PASSED (`test_m22_conversation_attachments`) |
| M22 Attachments | Cross-conversation document leak | Scoped search query by `conversation_id` | PASSED (`test_m22_conversation_attachments`) |
| M22 Promotion | Cross-tenant KB promotion | Enforces dual tenant ownership verification | PASSED (`test_m25_security_regression`) |
| M22 Attachment Deletion | Unauthorized deletion across tenants | Fail-closed tenant check returning 404 | PASSED (`test_m25_security_regression`) |
| M23 Audio Upload | Oversized audio denial of service | Enforces strict 15 MB audio payload cap | PASSED (`test_m25_security_regression`) |
| M23 Audio Format | Malicious file disguised as audio | MIME type validation (fail-closed HTTP 400) | PASSED (`test_m23_speech`) |
| M24 Voice & Tools | Audio bypass of tool approvals | Approval requires cryptographic token | PASSED (`test_m20_7_agentic_mcp_e2e`) |
| M16–M20 Core | Regressions in existing auth, tools, MCP | Full regression suite executed | PASSED (24/24 tests) |

## 2. Test Execution Totals
- **Backend Milestone Tests (M22–M25)**: 14/14 tests passing.
- **Backend Historical Security & Regression Tests**: 24/24 tests passing.
- **Backend Total**: 38/38 tests passing.
- **Frontend Typecheck (`npx tsc --noEmit`)**: 0 errors.
- **Frontend Production Build (`npm run build`)**: 0 errors, 22/22 routes successfully generated.
