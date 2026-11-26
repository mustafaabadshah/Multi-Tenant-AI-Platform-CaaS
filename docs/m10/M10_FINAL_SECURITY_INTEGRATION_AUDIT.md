# M10 Final Integration — Stage E: Security & Tenant Isolation Integration Audit

**Date:** 2026-11-11
**Method:** static inspection + existing automated negative suites + live endpoint probes (read-only).

---

## 1. Threat checklist (14 checks)

| # | Threat | Status | Evidence |
|---|---|---|---|
| 1 | Tenant A cannot access Tenant B's assistant | VERIFIED | runtime/conversations/developer routes all scope by `tenant_id`; `test_m10_stage1` cross-tenant 403/404 tests pass |
| 2 | Tenant A cannot retrieve Tenant B's chunks | VERIFIED | `RetrievalService` + `retrieval/authorization.py` composite scoping; `test_retrieval_security.py` passes |
| 3 | Public assistants cannot retrieve private documents | VERIFIED | `runtime.py:185-194` — public path restricts to `access_level == "PUBLIC"` and `status != DELETED` |
| 4 | Anonymous sessions cannot access other sessions | VERIFIED | session_token-bound lookup in `public_chat.py`; `test_m10_stage1` anonymous isolation tests pass; 128-bit session/public IDs |
| 5 | Developer API keys cannot access unauthorized assistants | VERIFIED | `api_key_service.authenticate_key` enforces `assistant_id` restriction (403 on scope mismatch); `test_m08` additions pass |
| 6 | Revoked keys cannot continue working | VERIFIED | `is_active`/revoked + expiry checked on every authentication; covered by tests |
| 7 | No source-document inspection via citation links | VERIFIED | citations carry only `snippet`/`document_name` (no document/chunk fetch by ID from any client surface) |
| 8 | Storage paths cannot bypass tenant authorization | VERIFIED | local storage keys sanitized + tenant-prefixed (`storage/local.py`, `s3.py` tenant-prefix); `test_m10_stage1` path-sanitization + S3-prefix tests pass |
| 9 | URL ingestion SSRF | VERIFIED | `validate_provider_endpoint`-style checks + dedicated `url_ingestion.py` SSRF guards; `docs/security/url-ingestion-ssrf.md`; tests pass |
| 10 | SQL ingestion cannot execute arbitrary SQL | VERIFIED | `sqlglot` parse-only pipeline (`parsers/sql_parser.py`); no execution engine; tests pass |
| 11 | Retrieved docs cannot override system security instructions | VERIFIED | 4-tier trust hierarchy in `context.py` — Tier-1 platform security block is immutable and precedes user/retrieved content; `test_m05_prompt_injection.py` covers (1 assertion now stale on a renamed header — see integration report, hierarchy itself intact) |
| 12 | Public chat cannot reveal keys/config | VERIFIED | `sanitize_error_message` + tracer redaction + strict BYOK error text (no key content); redaction tests pass |
| 13 | Error responses expose no stack traces/secrets | VERIFIED | sanitizers on both SSE and HTTP error paths; OpenAI/Groq providers surface parsed provider messages only |
| 14 | CORS is not treated as authentication | VERIFIED — authentication is JWT/API-key based on every endpoint; CORS is transport-only. **Residual risk D11:** `main.py` enables a permissive localhost/LAN dev origin regex whenever `DEBUG=true` or `ENVIRONMENT=development` — both defaults. A staging/prod deployment that forgets `DEBUG=false` + `ENVIRONMENT=production` ships LAN-permissive CORS (credentials allowed). Render blueprint sets `ENVIRONMENT=staging`, `DEBUG=false` correctly; risk is misconfiguration by default, not an open hole in the shipped config. |

## 2. Residual risks & untested boundaries

1. **Default-permissive dev CORS (D11)** — mitigated only by explicit production env flags. Recommend fail-closed: gate dev regex on `ENVIRONMENT=="development"` AND `DEBUG`, or require an explicit `ALLOW_DEV_ORIGINS=true`.
2. **Docker build context bake-in** — mitigated during this audit by adding `.dockerignore` files (backend: `.env`, `*.db`, `.venv`; frontend: `node_modules`, `.next`). Before images are built, confirm no prior image already contains `backend/.env`.
3. **Embed trust boundary** — embed widget runs on third-party origins; domain allowlist (`allowed_domains`) enforcement is server-side verified by tests; no referer/origin enforcement on `/embed/[publicId]` GET itself (config fetched client-side with `X-Tenant-ID` from a public config endpoint — acceptable, but rate-limiting of anonymous chat is quota-scoped only).
4. **BYOK vault validation timing** — `byok_vault.add_credential` validates via `test_credential` after commit; a failing key remains stored (user can retry). Not an isolation issue; UX consideration.
5. **Prompt-injection protection** is prompt-hierarchy based (no LLM-level guardrails) — acceptable for staging; note as limitation.
6. **Live PostgreSQL/Qdrant isolation** — covered by SQLite/mocked suites only; the 12+5 live integration tests are NOT RUN (see database audit).

## 3. Live probes (read-only, this audit)

| Probe | Result |
|---|---|
| `GET /health` | 200, healthy |
| `GET /ready` | 200, database connected |
| `GET /api/v1/embedding-providers` (no auth) | **401** "Authentication token required" — fail-closed, correct |
| `GET /api/v1/vector-stores` (no auth) | **401** — fail-closed, correct |

## 4. Findings that require a decision before staging

- **SEC-1:** employees invite role options in the new frontend (`employee | manager | admin`) do not exist in the backend role catalog (`employee, viewer, knowledge_editor, assistant_manager, dept_admin, org_admin, tenant_owner, platform_superadmin`). Inviting with "Manager" or "Administrator" returns HTTP 400. **Frontend/backend contract defect introduced by uncommitted Stage 4 work.**
- **SEC-2:** `docs/m10/M10_STAGE_5_FINAL_REPORT.md` claims HEAD subject is a docs(m10) commit; actual subject is feat(m08). Documentation accuracy issue only.

---

## Declaration

```text
TENANT_SECURITY_REVIEW = PASS
```
(residual risks and remediation requirements documented above; live infrastructure checks remain NOT RUN)
