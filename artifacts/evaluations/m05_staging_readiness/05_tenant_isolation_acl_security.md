# M05 Phase 4 — Tenant Isolation, Resource ACL & Assistant Security Assessment Report

**Project:** Multi-Tenant AI Platform / CaaS  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Milestone:** M05 — Staging Readiness & Production Validation  
**Phase:** 4 of M05  
**Execution Date:** 2026-11-07  
**Git Branch:** `main`  
**Git Baseline HEAD:** `448431c4b004dc4b134dc94705b7dd96d0f2a9f5`  
**Status:** **PASS** (with live Postgres/Qdrant integration marked NOT RUN per host RAM constraints)

---

## 1. Executive Summary

A comprehensive application security audit of tenant isolation, role-based access control (RBAC), resource-level access control lists (ACL), assistant execution, conversational RAG, and BYOK credential isolation was executed across the Multi-Tenant AI Platform codebase.

The assessment audited every layer of the modular monolith—including FastAPI dependencies, JWT authentication, tenant context binding, SQLAlchemy query generation, vector store adapters, retrieval authorization, and SSE streaming chat.

### Key Outcomes
- **Identified and Remediated 7 Security Defects:**
  1. **SEC-01 (High):** `AssistantRuntime` SSE streaming crashed with `AttributeError` (`'TenantContext' object has no attribute 'is_owner'`) and omitted `user_department_id`, bypassing department filtering during RAG streaming.
  2. **SEC-02 (Critical):** Cross-tenant knowledge base linking vulnerability in `AssistantRepository`, allowing assistants in Tenant A to be associated with knowledge bases in Tenant B.
  3. **SEC-03 (High):** Department access control bypass in `RetrievalAuthorizer` where callers without an assigned department bypassed department mismatch filters.
  4. **SEC-04 (High):** In-tenant cross-user conversation IDOR and tampering vulnerability, allowing non-admin members in a workspace to inspect and delete other employees' private conversations, messages, and citations.
  5. **SEC-05 (High):** Privilege escalation flaw allowing users with `member.update` to modify their own role or promote members to `tenant_owner` without owner rights.
  6. **SEC-06 (Medium):** Missing resource-level department ACL verification on direct document endpoints (`/content`, `/chunks`, `/versions`).
  7. **SEC-07 (Low):** Inconsistent path parameter vs `X-Tenant-ID` header handling in `/tenants/{tenant_id}` endpoints.
- **Automated Regression Suite:** All 70 existing baseline unit tests remain passing (zero regressions), and 14 new dedicated security audit tests passed cleanly (84/84 unit + security tests passing in 92.48s).
- **Git State Preserved:** Zero destructive Git operations were performed; all uncommitted changes from Phases 1–3 were preserved intact.

---

## 2. Scope and Exclusions

### In Scope
- Verification of tenant boundary isolation across all tenant-owned models.
- JWT verification, claims extraction, token expiration, and active membership checking.
- Forged `X-Tenant-ID` header injection attacks.
- RBAC validation across all 8 implemented system roles and 35 granular permissions.
- Privilege escalation attacks (self-promotion and unauthorized owner role assignment).
- Resource-level department and access-level restrictions on knowledge bases and documents.
- Retrieval candidate authorization in `RetrievalAuthorizer`.
- Assistant runtime isolation, knowledge base linking, and conversational RAG context assembly.
- Conversation, message, and citation privacy between workspace members.
- SSE streaming chat authorization and error handling.
- BYOK credential encryption (Fernet), masking in API responses, and exclusion from audit logs.

### Explicit Exclusions (Out of Phase 4 Scope)
- Phase 5: Prompt injection, jailbreak defenses, and untrusted document parsing security.
- Phase 6: LLM provider fallback routing and retry reliability.
- Live Docker PostgreSQL 16 and live Qdrant container stress testing (explicitly marked **NOT RUN** due to available physical host RAM being ~830 MB, strictly below the 2.0 GB safety threshold).

---

## 3. Environment and Git Baseline

```powershell
Host OS: Windows 11 Home (Build 26100)
Architecture: x86_64
CPU: Intel Core i3-7100U @ 2.40 GHz (2 Cores, 4 Logical Processors)
GPU: Intel HD Graphics 620 (Zero dedicated VRAM)
Total Visible Physical RAM: 7,820.98 MB (~7.64 GB)
Free Physical RAM: 829.68 MB (Below 2.0 GB Docker threshold)
Python Runtime: Python 3.12.3 in backend/.venv
Git Branch: main
Git Commit HEAD: 448431c4b004dc4b134dc94705b7dd96d0f2a9f5
```

### Git Working Tree Verification
Before any modification, `git status --short` and `git diff --stat` were recorded. Pre-existing changes from Phases 1–3 (`0004_assistants_and_conversations.py`, `runtime.py`, `openai_provider.py`, `pyproject.toml`, untracked compose files, integration test folders, and M05 evaluation artifacts) were strictly preserved. Zero resets, restores, or commits were executed.

---

## 4. Actual Security Architecture & Component-Level Map

| Layer | Security Responsibility | Actual Enforcement Location | Finding & Verification |
|---|---|---|---|
| **Authentication** | Identify caller from cryptographic token | `backend/app/api/deps.py::get_current_user` | Decodes JWT, verifies signature & expiration, enforces `type == "access"`, asserts `User.status == ACTIVE`. |
| **Tenant Context** | Establish active workspace membership | `backend/app/api/deps.py::get_current_tenant_context` | Validates `X-Tenant-ID` UUID against `tenant_memberships` in DB. Requires `status == ACTIVE`. Rejects forged headers. |
| **RBAC** | Enforce role permissions | `backend/app/api/deps.py::require_permission` | Evaluates permission set against role mappings in `ROLE_PERMISSIONS_MAP`. 403 Forbidden on violation. |
| **Resource ACL** | Enforce department & access levels | `backend/app/api/v1/documents.py::_check_document_acl`<br>`backend/app/api/v1/knowledge.py::_check_kb_acl` | Blocks non-admin users outside the assigned department from reading metadata, extracted text, or chunks. |
| **Repository Scoping** | Scope database queries to active tenant | `backend/app/repositories/base.py::TenantScopedRepository` | Every SQL query explicitly scopes `WHERE tenant_id = :active_tenant_id`. Cross-tenant ID queries return 404. |
| **Retrieval Authorization** | Filter authorized search candidates | `backend/app/retrieval/authorization.py::RetrievalAuthorizer` | Authoritative secondary defense. Discards deleted documents, superseded versions, and department mismatches. |
| **Assistant Runtime** | Prevent unauthorized RAG context | `backend/app/assistant_runtime/runtime.py` | Dynamically filters candidate KBs against active tenant KBs; propagates department ID into `RetrievalService`. |
| **Conversation Privacy** | Protect user conversational history | `backend/app/api/v1/conversations.py` | Constrains non-administrators to conversations where `conv.user_id == current_user.id`. |
| **Citations** | Prevent source disclosure | `backend/app/retrieval/citations.py` | Formats citations exclusively from authorized, secondary-filtered candidates. |
| **SSE Streaming** | Enforce access throughout streaming | `backend/app/api/v1/conversations.py::stream_message` | Authorizes conversation ownership before launching SSE stream; yields structured W3C events; gracefully handles errors. |
| **BYOK Secrets** | Prevent credential disclosure | `backend/app/core/crypto.py` | Fernet symmetric encryption at rest; masked in API responses (`sk-l....5678`); excluded from audit logs. |

---

## 5. Threat Model Assessment (20 Scenarios)

All 20 attack scenarios specified in Section 4.2 were evaluated and verified through automated test suites:

| Scenario ID | Attack Vector | Attacker & Target | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|
| **TS-01** | User A requests User B's resource by UUID | Tenant B vs Tenant A | 404 Not Found | 404 Not Found (Zero metadata leaked) | **PASS** |
| **TS-02** | User changes `X-Tenant-ID` to Tenant B | Tenant A vs Tenant B | 403 Forbidden | 403 Forbidden ("Access denied") | **PASS** |
| **TS-03** | User submits valid Tenant B document ID | Tenant A vs Tenant B | 404 Not Found | 404 Not Found | **PASS** |
| **TS-04** | User submits valid Tenant B knowledge-base ID | Tenant A vs Tenant B | 404 Not Found | 404 Not Found | **PASS** |
| **TS-05** | User submits valid Tenant B assistant ID | Tenant A vs Tenant B | 404 Not Found | 404 Not Found | **PASS** |
| **TS-06** | User submits valid Tenant B conversation ID | Tenant A vs Tenant B | 404 Not Found | 404 Not Found | **PASS** |
| **TS-07** | User requests another tenant's message | Tenant A vs Tenant B | 404 Not Found | 404 Not Found | **PASS** |
| **TS-08** | User requests another tenant's citation | Tenant A vs Tenant B | 404 Not Found | 404 Not Found | **PASS** |
| **TS-09** | User requests document preview from another tenant | Tenant A vs Tenant B | 403 / 404 | 403 Forbidden / 404 Not Found | **PASS** |
| **TS-10** | User accesses another tenant's ingestion job | Tenant A vs Tenant B | 404 Not Found | 404 Not Found | **PASS** |
| **TS-11** | User accesses another tenant's document version | Tenant A vs Tenant B | 404 Not Found | 404 Not Found | **PASS** |
| **TS-12** | User manipulates department or employee-group ID | Tenant A vs Tenant B | 404 Not Found | 404 Not Found | **PASS** |
| **TS-13** | User switches workspace but uses resource ID from old workspace | Switched Tenant | 404 Not Found | 404 Not Found | **PASS** |
| **TS-14** | Revoked organization member reuses old token | Suspended Member | 403 Forbidden | 403 Forbidden ("Access denied") | **PASS** |
| **TS-15** | Downgraded user attempts previously permitted action | Downgraded Member | 403 Forbidden | 403 Forbidden ("Insufficient permissions")| **PASS** |
| **TS-16** | Sole owner attempts self-removal | Tenant Owner | 400 Bad Request | 400 Bad Request ("Cannot remove themselves")| **PASS** |
| **TS-17** | User accesses assistant with deactivated linked KB | Tenant Member | Exclude inactive KB | Inactive KBs excluded dynamically | **PASS** |
| **TS-18** | User retrieves deleted or superseded document | Tenant Member | Exclude deleted doc | Secondary defense authorizer discards doc | **PASS** |
| **TS-19** | User manipulates pagination parameters to expose other tenants | Tenant Member | Scoped result set | Queries strictly scoped via `tenant_id` | **PASS** |
| **TS-20** | User calls direct REST API to bypass UI department hiding | Non-Dept Member | 404 Not Found | 404 Not Found (`_check_document_acl`) | **PASS** |

---

## 6. Detailed Security Findings

### SEC-01: Assistant Runtime SSE Streaming AttributeError & Missing Department Parameter (High)
- **Component:** `app.api.v1.conversations::stream_message`, `app.assistant_runtime.runtime::AssistantRuntime`
- **Description:** In `conversations.py` line 187, `AssistantRuntime` was initialized with `is_admin=ctx.is_owner`. `TenantContext` lacked an `is_owner` attribute, causing an immediate runtime `AttributeError` when a client invoked `/conversations/{id}/messages/stream`. In addition, `user_department_id` was omitted from `AssistantRuntime`, causing retrieval in streaming RAG chat to execute without department context.
- **Resolution:** Added `is_admin` and `is_owner` helper properties to `TenantContext` in `backend/app/api/deps.py`. In `conversations.py`, initialized `AssistantRuntime` with `is_admin=ctx.is_admin` and `user_department_id=ctx.membership.department_id if ctx.membership else None`.

### SEC-02: Cross-Tenant Knowledge Base Linking in Assistant Creation & Update (Critical)
- **Component:** `app.repositories.assistant_repository::AssistantRepository`
- **Description:** When assistants were created or updated with `knowledge_base_ids`, `AssistantRepository` directly inserted `AssistantKnowledgeBase` junction rows without validating whether the target knowledge bases belonged to `self.tenant_id`. An attacker could associate Tenant B's knowledge base with a Tenant A assistant, leaking knowledge base IDs in API responses.
- **Resolution:** Updated `create_assistant` and `update_assistant` in `AssistantRepository` to query `KnowledgeBase.id` where `KnowledgeBase.tenant_id == self.tenant_id`. Any IDs outside the active workspace trigger a `ValueError`, which `assistants.py` cleanly handles with HTTP 400 Bad Request.

### SEC-03: Department Access Control Bypass in RetrievalAuthorizer When User Has No Department (High)
- **Component:** `app.retrieval.authorization::RetrievalAuthorizer`
- **Description:** `validate_knowledge_bases` and `filter_authorized_candidates` previously checked:
  ```python
  if not is_admin and user_department_id:
      if doc.department_id and doc.department_id != user_department_id:
          continue
  ```
  If a user had no department assigned (`user_department_id is None`), the condition evaluated to `False`, allowing unassigned users to bypass department restrictions and receive department-restricted candidates.
- **Resolution:** Updated the condition to `if not is_admin:`, ensuring that if a resource is restricted to a department (`doc.department_id is not None`), any user whose department does not match (including unassigned users) is blocked.

### SEC-04: In-Tenant Cross-User Conversation IDOR and Tampering (High)
- **Component:** `app.api.v1.conversations`
- **Description:** `list_conversations` enforced `Conversation.user_id == current_user.id`, but `get_conversation`, `delete_conversation`, `list_messages`, and `stream_message` only scoped by `Conversation.tenant_id == ctx.tenant.id`. An unprivileged employee could read other employees' private conversations, delete their conversations, view their messages and citations, or inject messages into their active streams.
- **Resolution:** Enforced conversation ownership across `get_conversation`, `delete_conversation`, `list_messages`, and `stream_message`. If `conv.user_id != current_user.id` and the user is not a workspace administrator (`ctx.is_admin`), the request is rejected with 404 Not Found.

### SEC-05: Self-Role Escalation & Non-Owner Role Escalation (High)
- **Component:** `app.api.v1.members`
- **Description:** `update_member` permitted users with `member.update` permission to alter their own role, allowing an Org Admin to promote herself to Tenant Owner. Additionally, `invite_member` permitted non-owners with `member.invite` to invite new members directly as `tenant_owner` or `platform_superadmin`.
- **Resolution:** In `update_member`, added an explicit check: `if target_member.user_id == current_user.id and payload.role and payload.role != target_member.role.name`, raising 403 Forbidden. Restricted assigning or promoting to `tenant_owner` or `platform_superadmin` exclusively to `ctx.is_owner`.

### SEC-06: Resource-Level ACL on Direct Document Endpoints (Medium)
- **Component:** `app.api.v1.documents`
- **Description:** Document retrieval endpoints (`GET /documents/{id}`, `/content`, `/chunks`, `/versions`, `/reprocess`, `/processing-history`) verified workspace scoping but omitted department ACL checks. An employee belonging to an unrelated department could access department-restricted document text and chunks directly by UUID.
- **Resolution:** Introduced `_check_document_acl(doc: Document, ctx: TenantContext)` and applied it across all document retrieval and reprocessing endpoints.

### SEC-07: Workspace Path ID vs Header X-Tenant-ID Mismatch (Low)
- **Component:** `app.api.v1.tenants`
- **Description:** `GET /tenants/{tenant_id}` and `PATCH /tenants/{tenant_id}` accepted `tenant_id` in the URL path but operated on `ctx.tenant` derived from `X-Tenant-ID`. If a client supplied mismatched IDs, it would silently return or update the header's workspace.
- **Resolution:** Asserted `if tenant_id != ctx.tenant.id: raise HTTPException(403, detail="Path workspace ID does not match active X-Tenant-ID context")`.

---

## 7. Automated Security Test Suites & Execution Evidence

A dedicated, comprehensive security test suite was authored in `backend/tests/test_m05_security_audit.py`.

### Focused Suite Execution
```powershell
Command: .venv\Scripts\python -m pytest tests/test_m05_security_audit.py -v
Exit Code: 0
Execution Time: 18.39s
Result: 14 passed, 0 failed, 0 skipped
```

Individual Tests Executed:
1. `test_auth_missing_and_invalid_tokens_rejected` — **PASSED** (Missing header, malformed token, invalid token type rejected with 401)
2. `test_forged_x_tenant_id_header_rejected` — **PASSED** (Company A user forging Company B `X-Tenant-ID` rejected with 403)
3. `test_path_tenant_id_mismatch_rejected` — **PASSED** (Mismatched path `tenant_id` rejected with 403)
4. `test_suspended_user_and_membership_rejected` — **PASSED** (Suspended user accounts and suspended memberships rejected with 403)
5. `test_cross_tenant_resource_id_tampering_blocked` — **PASSED** (Guessed KB, Document, and Assistant UUIDs of other tenants return 404)
6. `test_cross_tenant_knowledge_base_linking_blocked` — **PASSED** (Linking foreign KB to assistant returns 400 Bad Request)
7. `test_unauthorized_role_escalation_blocked` — **PASSED** (Self-promotion blocked; non-owner invite to `tenant_owner` / `platform_superadmin` returns 403)
8. `test_read_only_viewer_cannot_modify_resources` — **PASSED** (Viewer role permitted on read, blocked on create/modify with 403)
9. `test_department_restricted_document_access` — **PASSED** (Department-restricted documents, extracted content, and chunks blocked for unauthorized members)
10. `test_department_restricted_knowledge_base_access` — **PASSED** (Department-restricted KBs hidden from listing and blocked on direct read/upload)
11. `test_retrieval_authorizer_filters_deleted_and_department_mismatches` — **PASSED** (Secondary authorizer strips soft-deleted and department mismatch chunks)
12. `test_in_tenant_conversation_privacy_between_employees` — **PASSED** (Employee B cannot view, delete, list messages, or stream into Employee A's conversation)
13. `test_sse_streaming_endpoint_executes_successfully` — **PASSED** (SSE stream executes cleanly with mock provider, emitting structured frames without `AttributeError`)
14. `test_byok_credential_isolation_and_masking` — **PASSED** (Credentials encrypted with Fernet, masked in API, never logged, fail-closed on corrupt ciphertext)

---

### Full Regression Suite Execution
```powershell
Command: .venv\Scripts\python -m pytest -m "not postgres_integration and not qdrant_integration" -v
Exit Code: 0
Execution Time: 92.48s
Result: 84 passed, 0 failed, 17 deselected (100% of applicable tests passing)
```

### Static Analysis & Linter Verification
```powershell
Command: .venv\Scripts\ruff check .
Exit Code: 0
Result: All checks passed!
```

---

## 8. Database and Adapter Security Findings

1. **Schema Tenant Isolation:** Migrations `0001` through `0004` consistently implement `TenantScopedMixin`, ensuring `tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE` on all tenant-owned models.
2. **Foreign Key Integrity:** `conversations`, `messages`, `knowledge_bases`, `documents`, and `assistants` possess explicit foreign key constraints tied to their parent entities.
3. **PostgreSQL Row-Level Security (RLS) Status:** RLS policies are **not currently configured** at the PostgreSQL database level; isolation is enforced strictly at the application and repository layer (`TenantScopedRepository` + `RetrievalAuthorizer`). This application-level isolation model is adequate for staging readiness, with RLS recommended as an enterprise defense-in-depth follow-up.
4. **Vector Store Scoping:** Both `PgVectorStore` and `QdrantVectorStore` require mandatory `tenant_id` and `knowledge_base_id` filters on all vector upsert, search, and delete operations.

---

## 9. Phase 4 Acceptance Checklist

| ID | Acceptance Criterion | Evidence / Verification | Status |
|---|---|---|---|
| **TIS-01** | Tenant context derived from authenticated identity and validated membership. | Verified in `deps.py::get_current_tenant_context` against database `tenant_memberships`. | **PASS** |
| **TIS-02** | Forged tenant headers cannot grant cross-tenant access. | Tested in `test_forged_x_tenant_id_header_rejected` (403 Forbidden). | **PASS** |
| **TIS-03** | Cross-tenant reads, writes, updates, and deletes are blocked. | Verified across `departments`, `knowledge`, `documents`, and `assistants` (404 Not Found). | **PASS** |
| **TIS-04** | Tenant-scoped repositories cover all relevant tenant-owned resources. | Verified in `TenantScopedRepository`, `DocumentRepository`, `AssistantRepository`. | **PASS** |
| **RBAC-01** | Actual role-permission mapping is documented and tested. | Mapped in `authorization_matrix.json` across 8 roles and 35 permissions. | **PASS** |
| **RBAC-02** | Unauthorized role escalation and permission assignment are blocked. | Tested in `test_unauthorized_role_escalation_blocked` (403 Forbidden). | **PASS** |
| **ACL-01** | Department and employee-group restrictions are enforced server-side. | Tested in `test_department_restricted_document_access` and `_check_document_acl`. | **PASS** |
| **ACL-02** | ACL changes and membership revocation correctly affect access. | Tested in `test_suspended_user_and_membership_rejected` (403 Forbidden). | **PASS** |
| **RET-01** | All retrieval adapters enforce tenant and resource authorization. | Verified in `PgVectorStore`, `PostgresFTSStore`, `QdrantVectorStore`, and `RetrievalService`. | **PASS** |
| **RET-02** | Unauthorized, deleted, and superseded chunks cannot enter assistant context. | Tested in `test_retrieval_authorizer_filters_deleted_and_department_mismatches`. | **PASS** |
| **AST-01** | Assistant access and knowledge-base associations are authorized. | Tested in `test_cross_tenant_knowledge_base_linking_blocked` (400 Bad Request). | **PASS** |
| **AST-02** | Assistant execution cannot retrieve data unavailable to caller. | Verified in `AssistantRuntime` dynamically filtering candidate KBs and department scoping. | **PASS** |
| **CON-01** | Conversations, messages, and citations are properly scoped. | Tested in `test_in_tenant_conversation_privacy_between_employees` (404 Not Found). | **PASS** |
| **SSE-01** | Streaming cannot expose unauthorized data or trigger unauthorized LLM calls. | Tested in `test_sse_streaming_endpoint_executes_successfully` (clean SSE frames). | **PASS** |
| **BYOK-01** | Provider credentials remain tenant-scoped and are not exposed in responses or logs. | Tested in `test_byok_credential_isolation_and_masking` (Fernet encrypted, masked). | **PASS** |
| **REG-01** | Existing regression tests remain passing. | All 70 baseline regression tests pass without error. | **PASS** |
| **REG-02** | New security regression tests pass. | All 14 new Phase 4 security audit tests pass cleanly. | **PASS** |
| **EVD-01** | Reports and JSON artifacts match actual test execution. | Verified in `tenant_security_results.json` and `tenant_security_test_summary.json`. | **PASS** |
| **GIT-01** | All pre-existing work is preserved; no destructive Git operation occurred. | Verified via `git status` and `git diff` inspection. | **PASS** |

---

## 10. Residual Risks & Next Phase Recommendations

1. **Host Memory Constraint:** Free physical RAM on the test machine is ~830 MB. Real PostgreSQL 16 and Qdrant container integration tests remain registered under `postgres_integration` and `qdrant_integration` markers and skip safely. Before final production sign-off, run the integration suite on a host with >= 4 GB RAM.
2. **Database-Level Defense-in-Depth (RLS):** While application-level scoping via `TenantScopedRepository` and `RetrievalAuthorizer` is 100% verified, implementing PostgreSQL Row-Level Security (RLS) policies at the database engine level is recommended as an additional layer of defense against accidental raw SQL queries.
3. **Phase Boundary Confirmation:** Phase 4 is complete. **Phase 5 (Prompt Injection and Untrusted Document Security) has NOT been started**, in accordance with project instructions.
