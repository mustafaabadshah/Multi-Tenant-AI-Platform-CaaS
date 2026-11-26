# M10 Git Integration — Stage 3 Security and Configuration Release Review

**Date:** 2026-11-12
**Repository:** `E:\MM Office\Multi-Tanant-CaaS`
**Baseline:** `HEAD 9479847` plus the uncommitted M10 working-tree changes
**Reviewer:** Kilo (Stage 3 security review)
**Mode:** Read-only. No git mutations, deployments, browser automation, or paid provider calls were performed. The only repository write is this document.

## Scope

This review re-verifies, from source, the Stage 3 areas:

1. CORS configuration and middleware wiring.
2. Invitation role contracts and RBAC boundaries.
3. Object storage isolation and path safety.
4. BYOK/provider credential policy and error sanitization.
5. Secret scanning of the release surface (`git diff` plus untracked text files).
6. Docker build-context and environment/template hygiene.

Prior M10 reports were not treated as evidence; every verdict below is backed by current source lines or by tests run during this review.

---

## Executive verdict

| Area | Verdict | Basis |
|---|---|---|
| CORS | **PASS** | Centralized fail-closed policy; dev-only LAN regex gated by two conditions; explicit origins; middleware wired through `create_app`; 10 Stage 1 CORS tests + 6 M05 staging tests pass. |
| Invitations / RBAC | **PASS** | Canonical `SystemRole` values only; unknown roles return 400; non-owner owner/superadmin assignment returns 403; membership creation is tenant-scoped; no bare `manager`/`admin` invite values remain; 15 Stage 2 tests pass. |
| Object storage | **PASS** | Tenant-prefixed keys, S3 `..`/`.` neutralization, local `resolve()`/`relative_to()` containment, filename sanitization, tenant-scoped consumers; 12 Stage 3 storage + 4 S3 tests + 3 recovery/containment tests pass. Residual: S3 tests are mocked, no live round-trip. |
| Provider credentials (BYOK) | **PASS** | Commercial providers explicitly blocked without an active BYOK key before any provider call; provider errors sanitized at the runtime boundary; OmniRoute is not part of the commercial gate and direct providers are independently registered; 3 quota/BYOK tests + 19 provider-reliability tests pass. Residual: sanitizer pattern coverage and OmniRoute key semantics are documented below. |
| Secret scan | **PASS** | `git diff` added lines and all untracked text files scanned. Five raw pattern hits: two synthetic redaction-test fixtures and three documentation prose references. No `AKIA` or PEM key material; no real secret identified. |
| Docker / env hygiene | **PARTIAL** | Exclusions, placeholders, S3 production storage, CORS variables, and absence of developer-machine absolute paths all pass. One pre-existing configuration defect: the documented `SECRET_ENCRYPTION_KEY` variable is not wired to `Settings` or to the crypto layer. |

**Overall:** **PARTIAL — release-ready for the reviewed controls, with one pre-existing configuration defect and the residual risks below.** No genuine security defect introduced by the M10 remediation was found. Finding F1 predates the remediation; it is reported rather than fixed because this stage is read-only.

---

## Test evidence (run during this review)

| Command | Result |
|---|---|
| `pytest tests/test_remediation_stage1_cors.py tests/test_remediation_stage2_invitation_roles.py tests/test_remediation_stage3_storage.py tests/test_s3_storage.py tests/test_quota_and_byok_policy.py -q` | **44 passed** (1 Starlette/httpx deprecation warning) in ~38s |
| `pytest tests/test_m05_staging_readiness.py -q` | **6 passed** |
| `pytest tests/test_m05_file_recovery.py -q` | **3 passed** |
| `pytest tests/test_m05_provider_reliability.py -q` | **19 passed** in ~158s |
| Broader `tests/test_observability.py tests/test_m10_stage1_security_verification.py` run | **NOT RUN** — exceeded the 300s review timeout; not used as evidence. |

Collection counts: Stage 1 CORS 10, Stage 2 invitation roles 15, Stage 3 storage 12, S3 storage 4, quota/BYOK 3 (total 44).

---
## 1. CORS — PASS

### Findings

- **Single source of truth:** `backend/app/core/cors.py:26-80` computes `(allow_origins, allow_origin_regex)`; `backend/app/main.py:10` imports it, `:64` builds the policy, and `:66-73` installs `CORSMiddleware` with `allow_credentials=True`.
- **Development LAN regex is double-gated:** `backend/app/core/cors.py:51` checks `settings.ENVIRONMENT == "development"`, and `:57` applies `DEV_ORIGIN_REGEX` only when `settings.ALLOW_DEV_LAN_ORIGINS` is true. The regex itself is defined at `:11-13`; default localhost origins are `:16-19`.
- **Production rejects localhost origins:** `backend/app/core/cors.py:61-65` rejects any origin for which `_is_local_origin` (`:22-23`) is true.
- **Production rejects wildcard + credentials:** `backend/app/core/cors.py:67-71` raises when `"*"` is present in the explicit origin list.
- **Fails closed when no trusted origins:** `backend/app/core/cors.py:73-78` raises `RuntimeError` when both the explicit origins list and `CORS_ORIGIN_REGEX` are empty.
- **Explicit origins only:** origins come from `FRONTEND_URL` and comma-separated `ALLOWED_ORIGINS` at `backend/app/core/cors.py:43-49`; the production regex comes from `settings.CORS_ORIGIN_REGEX` at `:73`.
- **Defaults and documentation:** `backend/app/core/config.py:19-23` defines `FRONTEND_URL`, `ALLOWED_ORIGINS`, `ALLOW_DEV_LAN_ORIGINS` (default `False`), and `CORS_ORIGIN_REGEX`. Production template variables are documented at `.env.production.example:21-27`; development equivalents at `.env.example:16-23`.
- **No leftover implicit dev regex:** repository grep for `DEV_ORIGIN_REGEX|allow_origin_regex|allow_origins|CORSMiddleware|ALLOW_DEV_LAN_ORIGINS|CORS_ORIGIN_REGEX` found the policy only in `core/cors.py`, `core/config.py`, `main.py`, and the two test files. `main.py` has no hardcoded dev regex.
- **Behavioral coverage:** `backend/tests/test_remediation_stage1_cors.py:38-110` covers dev localhost acceptance, explicitly configured LAN acceptance, unconfigured LAN rejection, opt-in LAN regex, production trusted/untrusted origins, production rejection of the dev LAN origin, wildcard + credentials, missing-origin fail-closed, and localhost rejection. `backend/tests/test_m05_staging_readiness.py:121-177` covers `FRONTEND_URL`, Vercel preview regex, unrelated Vercel rejection, and untrusted origin rejection.

### Verdict and residual risk

**PASS.** The stated contract is implemented and tested.

Residual risks:

- `_is_local_origin` only rejects `http://localhost...` and `http://127.0.0.1...` (`core/cors.py:22-23`). An explicitly configured LAN origin such as `http://192.168.1.50:3000` in `ALLOWED_ORIGINS` would be accepted in production, despite the docstring at `:34-39` saying localhost/LAN origins are rejected. This requires an operator to explicitly trust that origin; it is not an implicit dev-regex leak. Correct the docstring or extend the check if LAN origins must be rejected even when explicit.
- The default production regex `^https://mmaip-frontend(-[a-zA-Z0-9_-]+)?\.vercel\.app$` (`core/config.py:23`) trusts any Vercel project whose name begins with `mmaip-frontend`. Any party able to create a Vercel project with that prefix obtains a matching origin. This is a preview-domain convenience with a broader trust boundary than an exact host allowlist. Prefer an exact preview-host allowlist or a team-scoped domain.
- CORS is a browser transport control, not authentication or authorization. It does not protect Bearer-token APIs from non-browser clients; tenant/RBAC checks remain the authorization boundary (see sections 2 and 3).
- The fail-closed "no trusted origins" branch is only exercised when `CORS_ORIGIN_REGEX` is explicitly cleared; the shipped default is a non-empty Vercel regex. This is acceptable if Vercel previews are intended, but operators should not read the default as "no trusted origins configured".

---

## 2. Invitations / RBAC — PASS

### Findings

- **Canonical role registry:** `backend/app/core/constants.py:27-36` defines `platform_superadmin`, `tenant_owner`, `org_admin`, `dept_admin`, `assistant_manager`, `knowledge_editor`, `employee`, `viewer`.
- **Frontend invite options are canonical:** `frontend/app/dashboard/employees/page.tsx:281-292` offers exactly `employee`, `org_admin`, `dept_admin`, `assistant_manager`, `knowledge_editor`, `viewer`. No `tenant_owner` or `platform_superadmin` option is exposed.
- **No alternate naming left in invite code:** a frontend-wide search for exact `"manager"` / `"admin"` string literals in `.ts/.tsx/.js/.jsx/.json` returned no matches. The only invite UI is `employees/page.tsx` (`api.inviteMember` call at `:59-64`; helper at `frontend/lib/api.ts:922-923`).
- **Unsupported roles are controlled 400:** `backend/app/api/v1/members.py:64-70` resolves the submitted role by name and returns HTTP 400 `Role '<name>' does not exist` when not found.
- **Owner/superadmin escalation is 403 for non-owners:** `backend/app/api/v1/members.py:72-77` rejects `tenant_owner`/`platform_superadmin` assignment when `ctx.is_owner` is false. The update path has the equivalent guard at `:172-185`.
- **Tenant scoping:** the route constructs `MemberRepository(db, ctx.tenant.id)` at `backend/app/api/v1/members.py:62` (and `:30`, `:154`, `:240`), so membership creation/listing/update/delete are scoped to the active tenant. The active tenant is derived from `X-Tenant-ID` and an active membership check at `backend/app/api/deps.py:100-171`; the `tenant_owner`/`platform_superadmin` predicate is `deps.py:41-46`.
- **Default role:** `MemberInviteRequest` defaults to employee; `backend/tests/test_remediation_stage2_invitation_roles.py:53-61` verifies the created membership role is `employee`.
- **Tests:** `backend/tests/test_remediation_stage2_invitation_roles.py` covers unsupported values (`manager`, `admin`, `super_admin`, `ROOT`, `org-owner`) returning 400 at `:28-37`, canonical values accepted at `:40-50`, default employee at `:53-61`, non-owner escalation 403 at `:64-93`, cross-tenant membership isolation at `:97-118`, and employee invite denial at `:121-127`. All 15 passed.

### Verdict and residual risk

**PASS.** The invitation contract now matches the canonical `SystemRole` registry, and the tested escalation boundaries hold.

Observations / residual risks:

- **Owner can assign `platform_superadmin`:** `members.py:73` blocks only non-owners. A workspace owner can therefore create a membership with the platform-level role name. Authorization remains tenant-membership-scoped (`deps.py:155-161`, `require_permission` at `:174-185`), so this does not by itself grant cross-tenant access; it is a role-semantics concern rather than a proven cross-tenant escalation. If `platform_superadmin` is meant to be a platform-only grant, add an explicit platform-admin check.
- Role rows are global (`backend/app/repositories/role_repository.py:21-29`) and only seeded system roles exist; there is no role-creation endpoint, which is why unknown names reliably return 400. Adding tenant-defined custom roles later would require revisiting the allowlist.
- `frontend/app/dashboard/employees/page.tsx:18` keeps a `roles` state populated at `:35-42` but the invite `<select>` uses hardcoded canonical options. This is cosmetic, not a security issue, but the fetched list could drift from the UI contract in the future.

---
## 3. Object storage — PASS

### Findings

- **Filename sanitization:** `backend/app/storage/base.py:8-19` strips directory components (including backslashes), replaces unsafe characters, strips leading dots, collapses `..`, and generates a random name if the result is empty. `build_storage_key` at `:53-63` applies `sanitize_filename` and partitions by `tenants/{tenant_id}/kbs/{kb_id}/docs/{doc_id}/v{version}/{name}`.
- **S3 key neutralization:** `backend/app/storage/s3.py:36-43` splits on both slash styles and drops `""`, `"."`, and `".."` segments before prefixing `{tenant_id}/`. This prevents `..` segments from escaping the tenant prefix in the object key namespace. `_check_configured` at `:45-50` fails if no bucket is configured.
- **Local path containment:** `backend/app/storage/local.py:13-15` resolves the base directory; `_resolve_tenant_path` at `:17-35` resolves the tenant root, strips a repeated `tenants/{tenant_id}/` prefix, resolves the target, and enforces `target_path.relative_to(tenant_root)` with `PermissionError` on escape (`:29-34`). All operations use it: `save` at `:37-49`, `get` at `:51-60`, `delete` at `:62-72`, `exists` at `:74-77`, `get_size` at `:79-88`. `save` writes to a temp file and replaces atomically (`:41-48`).
- **Fail-closed configuration:** `backend/app/storage/__init__.py:11-47` rejects `STORAGE_BACKEND=local` in production (`:23-30`), rejects unsupported backends (`:32-33`), requires `S3_BUCKET_NAME` (`:35-39`), and requires static credentials when `S3_ENDPOINT_URL` is set (`:41-47`). `get_storage_provider` calls the validator before constructing a provider (`:51-60`); `backend/app/main.py:19-22` also validates at startup.
- **Upload path:** `backend/app/api/v1/knowledge.py:243-250` verifies the knowledge base belongs to the active tenant before upload; `:265` constructs the ingestion service with `ctx.tenant.id`; `backend/app/services/ingestion/service.py:79-90` sanitizes the filename, builds the tenant/KB/document/version key, and saves with `str(self.tenant_id)`.
- **Read path:** `backend/app/services/ingestion/service.py:185` loads bytes through `self.storage.get(str(self.tenant_id), doc.file_path)`, i.e., with the active tenant identity.
- **Delete path:** `backend/app/api/v1/documents.py:56-64` obtains the document through the tenant-scoped `DocumentRepository(db, ctx.tenant.id)` and applies document ACL checks, then `:83-88` deletes the raw object with `str(ctx.tenant.id)`.
- **Authorization is not the tenant prefix:** the storage layer treats `tenant_id` as a key namespace only. Authorization happens at the route/service layer: active membership in `backend/app/api/deps.py:155-161`, permission checks in `:174-185`, KB ownership at `knowledge.py:243-250`, and document ownership/ACL at `documents.py:56-64` / `:34-47`.
- **Tests:** `backend/tests/test_remediation_stage3_storage.py:21-62` covers the configuration matrix (local dev allowed, production local rejected, S3 bucket/credential requirements, unsupported backend); `:73-101` covers tenant-separated S3 keys, leading-slash/`..` neutralization, filename sanitization, and tenant-partitioned keys; `:107-131` covers S3 error messages not containing the synthetic secret/access key. `backend/tests/test_s3_storage.py:19-26` checks tenant key prefixing; `:35-89` mocks save/get/exists/get_size/delete. `backend/tests/test_m05_file_recovery.py:265-270` verifies tenant B cannot read tenant A's restored local key, and `:378-388` verifies zip-slip rejection. All 12 + 4 + 3 tests passed.

### Verdict and residual risk

**PASS.** Tenant-prefixed keys, path neutralization, local containment, filename sanitization, and the upload/read/delete paths are all in place. Tenant prefix is correctly treated as defense-in-depth, not as authorization.

Residual risks:

- **No live S3 round-trip:** S3 tests mock `aioboto3`; they do not exercise a real S3/MinIO endpoint, IAM policy, bucket policy, or credential scoping. Run a staging round-trip (save/get/exists/get_size/delete) before production sign-off.
- **S3 exception wrapping:** `backend/app/storage/s3.py` does not catch or re-wrap SDK exceptions. The Stage 3 test supplies a generic `RuntimeError` and confirms the synthetic secret/access key are absent, but it does not prove that every real SDK error is credential-free. Add a defensive scrubber if SDK error text is emitted to clients or logs.
- **`exists()` masks errors:** `backend/app/storage/s3.py:138-142` returns `False` for any `head_object` exception, including authentication/permission failures. This can make a misconfigured credential look like a missing object. It does not leak data, but it weakens operational detection.
- **Provider singleton caching:** `get_storage_provider` is `lru_cache`d (`storage/__init__.py:50`); changing storage settings requires a process restart. This is expected for configuration, but document it for operators.
- **Local filesystem metadata:** local storage uses `resolve()` and containment checks; a filesystem-level symlink race is out of scope for application-level protection. Production must use S3 (enforced only when `ENVIRONMENT` is exactly `production`; see F5).

---

## 4. Provider credentials (BYOK) — PASS

### Findings

- **Strict commercial BYOK gate:** `backend/app/assistant_runtime/runtime.py:260-280` resolves the tenant's active credential and, for `openai`, `anthropic`, `gemini`, and `groq`, refuses to call the provider when no key is resolved. It releases the quota reservation, persists an assistant error message, emits an SSE `message_error`, and returns. The preview path has the same gate at `:495-502`.
- **No silent platform fallback in the runtime:** the provider adapters do have environment fallbacks (`backend/app/llm/providers/openai_provider.py:89-98`), but the commercial-provider gate runs before `provider.generate_stream` (`runtime.py:282-300`). Therefore a missing tenant BYOK key cannot silently fall through to `OPENAI_API_KEY` or another platform credential for a commercial assistant.
- **OmniRoute optional / direct providers independent:** `backend/app/llm/registry.py:25-54` registers Groq, Anthropic, Gemini, OpenAI, OmniRoute, and Mock independently. The directory metadata marks `omniroute` as `requires_api_key: False` (`:99-104`) and commercial providers as `requires_api_key: True` (`:75-98`). OmniRoute is not in the strict commercial gate in `runtime.py:262`, so it remains usable independently of the BYOK enforcement. Note: the OpenAI-compatible adapter still raises `LLMAuthenticationError` if the resolved key is empty (`openai_provider.py:103-104`, `:156-157`), so an unauthenticated local OmniRoute deployment would need the adapter to permit an empty key; this is a functional nuance, not a fallback risk.
- **Sanitized error paths:** `runtime.py:33-39` redacts `sk-...` API keys, Bearer tokens, `TEST_SECRET_*` values, and `password|pwd|secret|api_key|token = ...` patterns. It is applied to generation failures at `:309-322` and preview failures at `:527-528`. `backend/tests/test_m05_provider_reliability.py:296-341` injects a synthetic `sk-live-...` secret into a provider error and asserts it is absent from the SSE frames while `[REDACTED_API_KEY]` is present.
- **Credential storage and tenant scoping:** `backend/app/services/byok_vault.py:26-43` scopes list/get by `tenant_id`; `:54-87` encrypts the key with `encrypt_secret`, stores only a masked representation in `api_key_masked`, and validates the credential; `:169-191` resolves the active/default credential with tenant scoping, active/not-revoked filters, and health/default ordering. The API response schema exposes `api_key_masked`, not ciphertext or plaintext (`backend/app/schemas/provider.py:22-37`).
- **Tests:** `backend/tests/test_quota_and_byok_policy.py:80-125` creates an `openai` assistant with no BYOK key and asserts an actionable error and no paid call. `backend/tests/test_m05_provider_reliability.py` covers provider registry contracts, SSRF/link-local endpoint rejection, HTTP error normalization, SSE error sanitization, empty streams, cancellation, and persistence. All 3 + 19 tests passed.

### Verdict and residual risk

**PASS.** The commercial-provider path is fail-closed on missing BYOK credentials, error frames are sanitized for the tested secret shapes, and OmniRoute/direct providers are registered independently.

Residual risks:

- **Sanitizer pattern coverage:** `sanitize_error_message` does not explicitly cover Groq `gsk_...` or Google `AIza...` key formats, and `_handle_http_error` now includes up to 200 characters of provider error text in the raised exception (`openai_provider.py:210-234`) and logs it at `:227`. A provider or malicious custom `base_url` that echoes an authorization header could place an unredacted Groq/Gemini key in logs or an SSE error. Extend the sanitizer to all configured provider key formats and consider scrubbing before logging.
- **Provider error text is trusted for detail:** the runtime sanitizer is the only scrubber for user-facing provider errors. Keep it in the critical path for every new provider adapter.
- **Quota error detail is not sanitized:** `runtime.py:244-245` interpolates `detail_msg` from the quota exception directly into the persisted/streamed error. If a quota/database exception ever contains a DSN or secret, it would bypass `sanitize_error_message`. Sanitize this path too.
- **Documented encryption key is inert (see F1):** BYOK ciphertext is actually derived from `SECRET_KEY`, not `SECRET_ENCRYPTION_KEY`. The encryption mechanism works, but the documented rotation variable does not.
- **Credential validation is a network call:** `byok_vault.py:84-86` validates a new credential immediately, and the custom `base_url` is user-supplied. `validate_provider_endpoint` allows local/private targets (`allow_local=True` in `openai_provider.py:87`) and only blocks IP literals/known metadata hosts. A tenant administrator with `TENANT_UPDATE` can point a credential at an internal hostname. This is an SSRF-by-design risk of custom endpoints; restrict `base_url` for commercial providers or resolve/deny private hostnames if internal access is not intended.

---
## 5. Secret scanning — PASS

### Method

- Scanned added lines from `git diff` (tracked modifications) and the full contents of all untracked text files reported by `git ls-files --others --exclude-standard`. Binary files were skipped by extension and NUL-byte detection.
- Patterns: `sk-[A-Za-z0-9]{20,}`, `AKIA[0-9A-Z]{16}`, Fernet `gAAAAA`, `BEGIN (RSA|OPENSSH|PRIVATE) KEY`.
- Values are masked in this report; no real secret value is printed.

### Results

| File:line | Pattern | Classification | Notes |
|---|---|---|---|
| `backend/tests/test_m10_stage1_security_verification.py:528` | `sk-...` | **Synthetic test fixture** | Dictionary value used by `test_observability_recursive_secret_redaction` to exercise redaction. Not a live credential. |
| `backend/tests/test_observability.py:64` | `sk-...` | **Synthetic test fixture** | `raw_key` used by `test_tracer_attribute_redaction` to assert redaction. Not a live credential. |
| `docs/m10/M10_FINAL_GIT_INVENTORY.md:62` | `gAAAAA` | **Documentation prose** | The line describes the scan pattern (`Fernet (gAAAAA...)`), not a Fernet key. |
| `docs/m10/M10_REMEDIATION_FINAL_GIT_READINESS.md:160` | `gAAAAA` | **Documentation prose** | Lists the Fernet prefix as a scan pattern. |
| `docs/m10/M10_REMEDIATION_FINAL_GIT_READINESS.md:169` | `gAAAAA` | **Documentation prose** | Table entry saying the untracked-file hit is documentation prose, not key material. |

- **No `AKIA[0-9A-Z]{16}` hits.**
- **No `BEGIN (RSA|OPENSSH|PRIVATE) KEY` hits.**
- **No real secret identified** in the diff or untracked release surface.
- `.env.example` and `.env.production.example` contain placeholders only; no `sk-`, `AKIA`, Fernet, or PEM values.
- `git ls-files` confirms only `.env.example` and `.env.production.example` are tracked; the local `backend/.env` is ignored and excluded from Docker builds.

### Verdict and residual risk

**PASS.**

Residual risks:

- Ignored files (notably `backend/.env`) are outside the untracked-file scan by design. Confirm the deployment secret store is the only holder of live values and that `.env` remains ignored.
- Git history was not scanned; only the current diff/untracked surface was tested. Add a history-aware scanner (e.g., gitleaks/detect-secrets) to CI before publishing the repository.
- The two synthetic `sk-...` fixtures intentionally resemble OpenAI keys. Keep them clearly marked as test data; do not replace them with real-format high-entropy values.

---

## 6. Docker / environment hygiene — PARTIAL

### Findings that pass

- **Backend build-context exclusions:** `backend/.dockerignore:4-18` excludes `.venv/`, `venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, caches, egg-info, `.env`, `.env.*`, `*.db`, `data/`, `tests/`, `evaluations/`, and `local_storage/`.
- **Frontend build-context exclusions:** `frontend/.dockerignore:3-10` excludes `node_modules/`, `.next/`, `out/`, `.env`, `.env.*`, `*.tsbuildinfo`, `next-env.d.ts`, and `.git/`.
- **Dockerfiles respect the exclusions:** `infrastructure/docker/backend.Dockerfile:21` uses `COPY . /app/` with the `backend` context; `infrastructure/docker/frontend.Dockerfile:8` uses `COPY . .` with the `frontend` context. Both contexts have matching `.dockerignore` files.
- **Production template placeholders only:** `.env.production.example:30-43` uses `change-me...` placeholders and an empty `SECRET_ENCRYPTION_KEY`; `:49-51` uses `STRONG_PASSWORD_HERE`; `:60-69` uses bucket/credential placeholders; `:98-100` leaves provider keys empty. No real credentials.
- **Production storage is S3:** `.env.production.example:56-72` sets `STORAGE_BACKEND=s3`, requires `S3_BUCKET_NAME`, documents endpoint/credentials, and notes `STORAGE_PATH` is development-only. `render.yaml:87-101` sets `STORAGE_BACKEND: s3`, adds `S3_BUCKET_NAME`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, and region. This matches the fail-closed validator in `backend/app/storage/__init__.py:23-47`.
- **CORS variables documented:** `.env.production.example:21-27` documents `ALLOWED_ORIGINS`, `ALLOW_DEV_LAN_ORIGINS=false`, and `CORS_ORIGIN_REGEX`; `.env.example:16-23` documents the development equivalents and states the LAN regex is development-only.
- **No developer-machine absolute paths in production config:** a scan of `.env.production.example`, `render.yaml`, `.env.example`, `backend/.dockerignore`, and `frontend/.dockerignore` for `[A-Za-z]:\\`, `Users\\`, `/Users/`, or `C:/` returned no matches. The only absolute storage path is the container path `/app/data/storage` (`.env.production.example:72`, `render.yaml:100-101`).
- **Render secrets:** `render.yaml:38-54` uses `generateValue: true` for `SECRET_KEY`, `JWT_SECRET`, and `SECRET_ENCRYPTION_KEY`, and `sync: false` for provider keys and S3 credentials. `FRONTEND_URL` is explicit at `:56-59`. Database URLs are linked from the managed PostgreSQL service at `:28-36`.
- **Tracked/ignored state:** `git ls-files` shows only `.env.example` and `.env.production.example`; `backend/.env` is ignored (`.gitignore:44`) and `backend/data` is ignored (`.gitignore:51`). `backend/.dockerignore:12` excludes `.env` from the image context.

### Defect F1 — `SECRET_ENCRYPTION_KEY` is documented but not wired

**Severity:** Medium (configuration/operability; not an authentication bypass).

**Evidence:**

- `.env.production.example:39-41` documents `SECRET_ENCRYPTION_KEY` as the "BYOK Credential Encryption Key (Fernet 32-byte URL-safe base64 key)".
- `.env.example:85-87` documents the same variable.
- `render.yaml:50-52` generates `SECRET_ENCRYPTION_KEY`.
- `backend/app/core/config.py:106` defines `ENCRYPTION_KEY`, not `SECRET_ENCRYPTION_KEY`; `Settings` uses `extra="ignore"` (`config.py:11`), so a `SECRET_ENCRYPTION_KEY` environment value is silently ignored.
- `backend/app/core/crypto.py:22-24` derives the active Fernet key from `settings.SECRET_KEY`; `:27-35` derives previous keys from `settings.PREVIOUS_SECRET_KEYS`. Neither `ENCRYPTION_KEY` nor `SECRET_ENCRYPTION_KEY` is used.
- `SECRET_ENCRYPTION_KEY` was introduced in commit `bc194d0` (M05 deployment blueprint), not by this remediation; the crypto wiring predates it. It is therefore a pre-existing defect, not a regression introduced by Stage 3.

**Impact:**

- Operators who set or rotate `SECRET_ENCRYPTION_KEY` see no effect. BYOK credentials are actually encrypted under a key derived from `SECRET_KEY`.
- The runbooks that instruct rotating `SECRET_ENCRYPTION_KEY` and copying it to `PREVIOUS_SECRET_KEYS` (`docs/runbooks/security-operations.md:10-17`, `docs/runbooks/backup-and-recovery.md:66`) describe a non-functional operation.
- Encryption still occurs; Render auto-generates `SECRET_KEY`, so ciphertext is not using the development default in that blueprint. The risk is operational: an operator could believe they rotated the BYOK key when they did not, or leave `SECRET_KEY` weak while setting a strong unused `SECRET_ENCRYPTION_KEY`.

**Recommendation (not applied — read-only review):** either add `SECRET_ENCRYPTION_KEY` (and `ENCRYPTION_KEY`) to `Settings` and make `get_active_fernet_key` prefer it with a `SECRET_KEY` fallback for backward compatibility, or correct the templates/runbooks to state that BYOK encryption is derived from `SECRET_KEY` and `PREVIOUS_SECRET_KEYS`. Until then, treat `SECRET_KEY` as the BYOK encryption secret and keep it strong/stable.

### Other Docker/env observations

- **Frontend `.dockerignore` does not list `.venv`, `*.db`, or `data/`.** There are no such files in `frontend/` today, so the current image is clean, but adding any later would include them. Add the entries defensively.
- **`render.yaml` sets `ENVIRONMENT: staging` (`render.yaml:19-20`), not `production`.** The local-storage rejection in `validate_storage_configuration` is gated on `ENVIRONMENT == "production"` (`storage/__init__.py:23-30`), so a future staging override to `STORAGE_BACKEND=local` would be accepted. The blueprint currently sets S3, so this is a guardrail gap for staging, not a production defect. Consider a stricter production-like environment check or a separate staging guard.
- **Root `docker-compose.yml` is development-only:** it sets `ENVIRONMENT=development`, `STORAGE_BACKEND=local`, development secrets, and bind-mounts `./backend` (`docker-compose.yml:35-54`). It is not a production deployment path, but do not reuse it for staging/production.

---
## 7. Findings summary

| ID | Severity | Finding | Introduced by remediation? | Status |
|---|---|---|---|---|
| F1 | Medium (config) | `SECRET_ENCRYPTION_KEY` is documented/rendered but ignored; BYOK encryption derives from `SECRET_KEY`. | No (M05 `bc194d0`) | Open — reported, not fixed (read-only review) |
| F2 | Low | CORS docstring claims LAN origins are rejected in production, but `_is_local_origin` only rejects localhost/127.0.0.1; explicit LAN origins are accepted. | No (new CORS module, but behavior is intentional explicit trust) | Open — documentation/decision needed |
| F3 | Low | BYOK error sanitizer does not cover Groq `gsk_` / Gemini `AIza` formats; provider error detail is logged/raised. | Partially (detail inclusion is part of the M10 diff) | Open — extend sanitizer |
| F4 | Low | S3 provider exceptions are not wrapped/scrubbed; tests mock the SDK and there is no live round-trip. | No | Open — add staging round-trip and defensive scrubbing |
| F5 | Low | Default Vercel preview regex trusts any `mmaip-frontend*.vercel.app` project; `render.yaml` relies on the default regex and is in `staging`, so the local-storage guard is production-only. | No | Open — tighten allowlist/guardrails |
| F6 | Info | A tenant owner can assign the `platform_superadmin` role name; authorization remains tenant-membership-scoped. | No | Observe / clarify role semantics |
| F7 | Info | Frontend fetches roles but the invite select uses hardcoded canonical options; `roles` state is unused. | No | Cosmetic |
| F8 | Info | Broader `test_observability.py` + `test_m10_stage1_security_verification.py` run timed out at 300s. | N/A | Not used as evidence |

**No genuine security defect introduced by the M10 remediation was found.** F1 is pre-existing; F3's error-detail inclusion is the only remediation-adjacent hardening gap, and it is a defense-in-depth issue rather than a demonstrated exploit.

---

## 8. Release recommendation

- **CORS:** PASS — keep the centralized `build_cors_policy`; do not reintroduce a hardcoded dev regex.
- **Invitations/RBAC:** PASS — keep the `SystemRole` allowlist contract and the 400/403 tests. Clarify whether owners may assign `platform_superadmin`.
- **Object storage:** PASS for source-level controls. Add a live S3/MinIO staging round-trip before production and keep authorization at the route/service layer.
- **BYOK:** PASS for the strict commercial-provider policy. Extend error sanitization to all provider key formats and sanitize quota error details.
- **Secret scan:** PASS for the current diff/untracked surface. Add history-aware CI scanning and keep `.env` out of source control and images.
- **Docker/env:** PARTIAL because of F1. Correct the `SECRET_ENCRYPTION_KEY` wiring or the documentation/runbooks before relying on BYOK key-rotation procedures.

**Overall release gate:** **PARTIAL — approved for the reviewed security controls, with F1 tracked as a pre-existing configuration defect and the residual risks above accepted or scheduled.** This review did not modify code, configuration, git state, or deployments.

---

## Appendix — Evidence index

- CORS policy: `backend/app/core/cors.py:11-80`; wiring: `backend/app/main.py:10,62-73`; settings: `backend/app/core/config.py:19-23`.
- CORS tests: `backend/tests/test_remediation_stage1_cors.py:38-110`; `backend/tests/test_m05_staging_readiness.py:121-177`.
- Roles: `backend/app/core/constants.py:27-36`; invite UI: `frontend/app/dashboard/employees/page.tsx:281-292`; API: `backend/app/api/v1/members.py:52-143`; tenant context: `backend/app/api/deps.py:100-185`.
- Invitation tests: `backend/tests/test_remediation_stage2_invitation_roles.py:28-127`.
- Storage base/local/S3: `backend/app/storage/base.py:8-63`, `local.py:13-88`, `s3.py:36-163`, `__init__.py:11-60`; consumers: `backend/app/api/v1/knowledge.py:243-279`, `backend/app/services/ingestion/service.py:79-90,185`, `backend/app/api/v1/documents.py:56-88`.
- Storage tests: `backend/tests/test_remediation_stage3_storage.py:21-131`; `backend/tests/test_s3_storage.py:12-89`; `backend/tests/test_m05_file_recovery.py:265-270,378-388`.
- BYOK runtime: `backend/app/assistant_runtime/runtime.py:33-39,260-322,495-528`; registry: `backend/app/llm/registry.py:25-104`; vault: `backend/app/services/byok_vault.py:26-191`; adapter: `backend/app/llm/providers/openai_provider.py:27-98,103-104,156-157,210-234`; schema: `backend/app/schemas/provider.py:22-37`.
- BYOK tests: `backend/tests/test_quota_and_byok_policy.py:80-125`; `backend/tests/test_m05_provider_reliability.py:42-341`.
- Crypto/config mismatch: `.env.production.example:39-43`; `.env.example:85-87`; `render.yaml:50-54`; `backend/app/core/config.py:11,106`; `backend/app/core/crypto.py:22-35`.
- Docker/env: `backend/.dockerignore:4-18`; `frontend/.dockerignore:3-10`; `infrastructure/docker/backend.Dockerfile:21`; `infrastructure/docker/frontend.Dockerfile:8`; `.env.production.example:21-27,30-72,94-104`; `render.yaml:19-20,28-59,87-101`; `.env.example:16-23,49-52,85-87`.
- Prompt-injection residual: `backend/app/assistant_runtime/context.py:14-35,50-57,111-167` (prompt-hierarchy enforcement and untrusted-content neutralization; defense is prompt-based, not a hard security boundary).