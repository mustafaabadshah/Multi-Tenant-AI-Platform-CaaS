# M11 Private Staging Security Profile

| Field | Value |
|---|---|
| Milestone | M11 - private staging readiness |
| Document | Secure-by-default staging security profile |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Date | 2026-11-12 |
| Status | **PROFILE PROPOSED - NOT APPLIED** |
| Baseline | `HEAD` = `fdb1246`; the working tree contains uncommitted M11 remediation changes |
| Change boundary | Documentation only. No code, cloud resource, account, billing, deployment, or Git mutation was performed. |
| Staging readiness | **NO for real documents** (M11 Stage 8); GO only for a closed synthetic-data cohort after the gates in this document |

> This profile defines the minimum configuration for a private staging environment. It is not a claim that the platform is secure in general, that the staging environment exists, or that every control below is complete. Missing controls are marked **MISSING**. Controls supported only by local or mocked tests are marked accordingly.

---

## 0. Status legend and evidence basis

| Label | Meaning in this document |
|---|---|
| **IMPLEMENTED** | Present in the working tree; not proof of live provider behavior. |
| **TESTED (LOCAL)** | A test exists and passed locally, either in a prior recorded run or in the verification pass described below. No live staging test was performed. |
| **PARTIAL** | Present with a material limitation that affects the staging decision. |
| **MISSING** | Not implemented in the repository or not configurable without a code/proxy/cloud change. |
| **UNVERIFIED** | Cannot be established without a live staging or provider check. Do not treat as fact. |
| **RECOMMENDED** | A profile decision, not an applied setting or a test result. |

### 0.1 Evidence used

| Evidence | What it supports |
|---|---|
| `docs/m11/M11_STAGE_1_ARCHITECTURE_DECISION.md` | Provider selection, verified 2026-11-12 Vercel/Render/R2 limits, topology, cost, and the Stage 8 dependency. |
| `docs/m11/M11_STAGE_2_POSTGRESQL_VALIDATION.md` and `M11_STAGE_2_POSTGRESQL_REVIEW_AND_REMEDIATION.md` | `LIVE_POSTGRESQL_MIGRATION_VERIFICATION = PASS`; fresh `alembic upgrade head` reaches `0010_m10_remediation_schema_alignment`; 46 application tables, 98 FKs, 119 `ix_%` indexes; 12 gated tests pass. |
| `docs/m11/M11_STAGE_7_SECURITY_AND_PRIVATE_TESTING.md` | Prior security baseline; 91-test targeted suite passed; open-registration/no-rate-limit findings that the current working tree now partially remediates. |
| `docs/m11/M11_STAGE_8_STORAGE_AND_BACKUP.md` | `STAGING_READY = NO` for real documents; S3 backup, versioning, reconciliation, key escrow, and delete convergence gaps. |
| `docs/m11/M11_STORAGE_AND_BACKUP_READINESS.md` | Compensating upload, delete ordering, failure cleanup, reconciliation CLI; 37-test regression passed. Remaining live S3 and backup gaps. |
| `docs/m11/M11_BACKUP_RESTORE_DRILL.md` | `LOCAL_PAIRED_DRILL = PASS` for local PostgreSQL plus local filesystem only; S3/R2, PITR, key escrow, scheduling, and retention remain untested. |
| `docs/m11/M11_BACKGROUND_JOB_RELIABILITY.md` | `READY_FOR_SINGLE_PROCESS_PRIVATE_STAGING`; atomic claim/lease; one API process with inline dispatcher. |
| `docs/m11/M11_OPTIONAL_INFRASTRUCTURE_DECISION.md` | Qdrant, Redis, Phoenix disabled; startup and retrieval do not contact Qdrant when disabled. |
| `docs/m11/M11_BACKEND_DEPENDENCY_LOCKFILE.md` | Hashed runtime/dev lockfiles validated; Docker and Render build commands use the lock. |
| `docs/m11/M11_STAGE_10_MANUAL_UI_ACCEPTANCE.md` | Manual UI acceptance is **PENDING**; 18 areas / 82 sub-checks not executed. |
| Source inspection | Current implementations and line references in Section 12. |

`M11_SECURITY_FINDINGS_REMEDIATION.md` and `M11_SECURITY_TEST_MATRIX.md` were requested as optional inputs. Neither file exists under `docs/m11/` at the time of writing; no result is attributed to them.

### 0.2 Verification performed for this profile

No code was changed. Local verification actions were run:

1. Targeted tests:

```text
tests/test_m11_registration_policy.py
tests/test_m11_rate_limiting.py
tests/test_m11_invitation_acceptance.py
tests/test_m11_embed_allowlist.py
tests/test_m11_public_metadata.py
tests/test_m11_storage_consistency.py
tests/test_remediation_stage1_cors.py
=> 75 passed, 1 warning in 57.33s
```

```text
tests/test_remediation_stage3_storage.py
tests/test_s3_storage.py
tests/test_health.py
tests/test_auth.py
=> 23 passed in 14.07s
```

These are local SQLite/mocked-provider tests, not staging proof.

2. Direct settings probes (no app started):

```text
ENVIRONMENT=staging, ALLOW_PUBLIC_REGISTRATION unset -> registration_allowed = False
ENVIRONMENT=staging, FRONTEND_URL=https://staging.example.com -> CORS origins = ['https://staging.example.com'], regex = None
ENVIRONMENT=staging, FRONTEND_URL=http://localhost:3000 -> RuntimeError (localhost rejected)
ENVIRONMENT=staging, FRONTEND_URL=http://192.168.1.50:3000 -> accepted (LAN origins are not auto-rejected)
ENVIRONMENT=staging, STORAGE_BACKEND=local -> validate_storage_configuration() returned without error
```

The staging-local-storage line is a **gap**: staging does not fail closed for local storage. The LAN line is a separate policy gap: only `http://localhost` and `http://127.0.0.1` are auto-rejected, so the profile must keep LAN origins out manually.

---

## 1. Recommended staging profile at a glance

1. Frontend on **Vercel Pro**, protected by **Vercel Authentication -> All Deployments**; testers are free **Viewer** seats.
2. Backend on **Render Web Service `1c-2g`**, one Uvicorn worker, region Oregon, auto-deploy off until smoke tests pass.
3. PostgreSQL 16 on **Render Postgres `0.5c-1g`** with pgvector; Cloudflare R2 private bucket for object storage.
4. `ENVIRONMENT=staging`, `DEBUG=false`, explicit `ALLOW_PUBLIC_REGISTRATION=false`; unique secrets and an escrowed `SECRET_ENCRYPTION_KEY`.
5. CORS uses the exact HTTPS frontend origin; no localhost, LAN, or wildcard origin; the preview regex is empty unless explicitly required.
6. Rate limits remain enabled for auth, invite acceptance, public chat, developer chat, and uploads; trusted-proxy list stays empty until real peer addresses are measured.
7. One API OS process, inline ingestion dispatcher enabled, `INGESTION_MAX_CONCURRENCY=1`, lease above the longest expected job.
8. pgvector + FTS hybrid retrieval with local 384-dimensional embeddings; Qdrant, Redis, Phoenix, and the standalone worker disabled.
9. Strict BYOK for commercial providers; no platform fallback. OmniRoute is optional and must not be funded without approval.
10. Public publishing and real documents remain disabled until the Stage 8 P0 controls and live storage/backup tests pass.

---

## 2. Environment-variable matrix for private staging

All values below are staging decisions. Placeholders in angle brackets are not real credentials. **Never commit generated secrets.** Store them in the Render/Vercel secret stores and in an external secrets manager for escrow.

### 2.1 Application and authentication

| Variable | Staging value | Rationale / implementation |
|---|---|---|
| `ENVIRONMENT` | `staging` | Enables the non-development CORS policy. Note: storage validation only treats `production` as fail-closed; see Section 3. |
| `DEBUG` | `false` | Do not expose debug behavior. `DEBUG` does not currently gate authentication (Stage 7), so it is not a security boundary by itself. |
| `PROJECT_NAME` | `Multi-Tenant AI Platform-CaaS` | Display metadata. |
| `API_V1_STR` | `/api/v1` | API prefix. |
| `ALLOW_PUBLIC_REGISTRATION` | `false` | Explicit opt-out. `registration_allowed()` returns this value; with it unset, staging also denies. |
| `SECRET_KEY` | `<generated 32-byte hex secret>` | Application secret. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. Never commit. |
| `JWT_SECRET` | `<different generated secret>` | JWT signing key. Must differ from `SECRET_KEY`. Never commit. |
| `SECRET_ENCRYPTION_KEY` | `<generated Fernet key>` | Encrypts BYOK secrets. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Escrow it externally. If unset, the code falls back to `SECRET_KEY`, which is not the desired staging posture. |
| `PREVIOUS_SECRET_KEYS` | `<empty>` initially | Comma-separated old key material for rotation. Set only during a controlled rotation; keep old material until all encrypted rows are re-encrypted. |
| `JWT_ALGORITHM` | `HS256` | Current default. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Current default. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Current default. Refresh tokens are not revocable server-side (Stage 7). |
| `FRONTEND_URL` | `https://<vercel-production-host>` | Exact HTTPS origin used by CORS and embed metadata. No trailing slash. |
| `BACKEND_URL` | `https://<render-service-host>` | Used by embed config and script URLs. |
| `ALLOWED_ORIGINS` | `<empty>` | Add only exact HTTPS origins, comma-separated. Do not add localhost or RFC1918 LAN origins; the policy does not automatically reject every LAN/loopback form. |
| `ALLOW_DEV_LAN_ORIGINS` | `false` | Ignored outside development; keep false. |
| `CORS_ORIGIN_REGEX` | `<empty>` | The code default is a Vercel pattern that can admit other matching hostnames. Set empty unless preview deployments must reach the backend; if required, use a narrow regex for the exact project. |

### 2.2 Rate limiting and proxy trust

| Variable | Staging value | Rationale / implementation |
|---|---|---|
| `RATE_LIMIT_ENABLED` | `true` | Master switch. Do not disable. |
| `TRUSTED_PROXY_IPS` | `<empty until verified>` | Exact peer IPs allowed to supply `X-Forwarded-For`. Only set after measuring the actual peer addresses. A wrong value permits identity spoofing and defeats per-IP limits. |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | `10` | Code default. Key is client IP + normalized email. |
| `RATE_LIMIT_REGISTER_PER_HOUR` | `5` (code default 20) | Registration is disabled, but the limiter still runs before the policy check. |
| `RATE_LIMIT_INVITE_ACCEPT_PER_HOUR` | `10` (code default 20) | Protects token guessing/abuse. |
| `RATE_LIMIT_PUBLIC_MESSAGE_PER_MINUTE` | `10` (code default 20) | Public publishing should be off; this is defense in depth if a publication is created. |
| `RATE_LIMIT_DEVELOPER_PER_MINUTE` | `30` (code default 60) | Keyed by API key ID. |
| `RATE_LIMIT_UPLOAD_PER_HOUR` | `30` (code default 60) | Keyed by tenant + user. |

The recommended lower values are profile decisions for a 3-5 tester cohort, not load-tested values. Limits are **per process**; see Section 5.
### 2.3 Database

| Variable | Staging value | Rationale / implementation |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://<user>:<password>@<internal-host>:5432/<db>` | Application async connection. Use the Render internal connection string for same-region private networking. The settings validator normalizes `postgres://`/`postgresql://` to asyncpg. |
| `DATABASE_SYNC_URL` | `postgresql://<user>:<password>@<internal-host>:5432/<db>` | Alembic migration connection. |
| `DB_POOL_SIZE` | `5` | Current default. |
| `DB_MAX_OVERFLOW` | `10` | Maximum 15 connections per process. |
| `DB_POOL_TIMEOUT` | `30` | Current default. |
| `DB_POOL_RECYCLE` | `1800` | Current default; pre-ping is enabled in the session layer. |

**SSL guidance:** use the internal Render connection string for backend-to-database traffic in the same workspace/region. If an external connection is used, require TLS at the provider (`sslmode=require` for the sync URL; the equivalent `ssl=require` for asyncpg) and verify it live. Do not append SSL parameters to an internal URL without confirming that the endpoint accepts them.

**Pool guidance:** one API process x 15 connections is well below the 100-connection limit of the `0.5c-1g` plan. Do not enable PgBouncer or multiple instances in the first staging cut. If multiple processes are later required, first verify asyncpg prepared-statement behavior in transaction-pooling mode and redo the connection budget.

### 2.4 Object storage

| Variable | Staging value | Rationale / implementation |
|---|---|---|
| `STORAGE_BACKEND` | `s3` | Durable object storage. Staging **must** set this explicitly; staging + `local` currently passes validation. |
| `STORAGE_PATH` | `<unset / remove>` | Ignored with S3. Removing it avoids accidental local use. |
| `S3_BUCKET_NAME` | `<private-staging-bucket>` | Bucket must not have public access. |
| `S3_ENDPOINT_URL` | `https://<account-id>.r2.cloudflarestorage.com` | R2 S3 API endpoint. |
| `S3_ACCESS_KEY_ID` | `<secret>` | R2 token scoped to Object Read & Write for this bucket only. Never commit. |
| `S3_SECRET_ACCESS_KEY` | `<secret>` | Never commit. |
| `S3_REGION_NAME` | `auto` | R2 documents `auto`; `us-east-1` is an alias, not a separate region. |
| `MAX_FILE_SIZE_BYTES` | `52428800` | 50 MB per file. Enforced after the body is read. |
| `MAX_FILES_PER_REQUEST` | `10` | Enforced before the loop; per-file commits mean partial batch success. |
| `MAX_EXTRACTED_TEXT_SIZE_BYTES` | `20971520` | 20 MB extracted text. |

The adapter uses backend-proxied reads/writes and no presigned URLs. No R2 CORS rule is required for the current design. The bucket token must not be reused from production or committed to `render.yaml`.

### 2.5 Ingestion, retrieval, and optional services

| Variable | Staging value | Rationale / implementation |
|---|---|---|
| `INGESTION_INLINE_DISPATCHER_ENABLED` | `true` | In-process dispatcher in the API lifespan. |
| `INGESTION_DISPATCHER_POLL_SECONDS` | `2` | Empty-queue poll interval. |
| `INGESTION_LEASE_SECONDS` | `3600` | Must exceed the longest expected job. There is no heartbeat; a longer-running live job can be requeued. |
| `INGESTION_MAX_CONCURRENCY` | `1` | One job at a time per process. |
| `DEFAULT_RETRIEVAL_MODE` | `hybrid` | pgvector + FTS. |
| `DEFAULT_VECTOR_STORE` | `pgvector` | No extra vector service. |
| `DEFAULT_EMBEDDING_PROVIDER` | `sentence-transformers` | Local CPU embedding path; avoids sending document text to an embedding API. |
| `DEFAULT_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 384 dimensions; matches the migration and `render.yaml` intent. |
| `DEFAULT_EMBEDDING_DIMENSIONS` | `384` | Must match the model and stored vectors. |
| `EMBEDDING_BATCH_SIZE` | `32` | Current default. |
| `RRF_K_CONSTANT` | `60` | Hybrid fusion constant. |
| `QDRANT_URL` | `<empty>` | No Qdrant service. Do not rely on the default localhost value. |
| `QDRANT_API_KEY` | `<empty>` | No Qdrant service. |
| `REDIS_URL` | `<empty>` | No runtime Redis usage; rate limiting is in-process. |
| `PHOENIX_ENABLED` | `false` | No Phoenix/OpenTelemetry runtime integration. |

**Embedding note:** the model downloads on first use into an ephemeral filesystem. The first ingestion after a deploy may be slower and depends on outbound access to the model host. This is a cold-start cost, not a security control. Code defaults in `config.py` are `omniroute`/1536 dimensions; staging must explicitly override them to the local 384-dimensional profile if that is the approved data-flow decision.

### 2.6 LLM gateway and BYOK policy

| Variable | Staging value | Rationale / implementation |
|---|---|---|
| `LLM_BASE_URL` | `<approved provider or gateway URL>` | Only a reachable, approved endpoint. Do not point at an unreachable local OmniRoute unless one is deployed. |
| `OMNIROUTE_API_KEY` | `<empty unless approved>` | A non-empty value can make OmniRoute platform-funded. Requires spend and data approval. |
| `OPENAI_API_KEY` | `<empty unless approved>` | The OpenAI-compatible provider reads this as an environment fallback. The runtime blocks commercial providers before use if no BYOK credential exists, but OmniRoute can use this fallback. Do not set it unless platform funding is approved. |
| `LLM_DEFAULT_MODEL` | `auto` only for OmniRoute/Groq; explicit model for direct providers | `.env.production.example` documents that `auto` is not valid for direct OpenAI/Anthropic/Gemini. |

**Strict BYOK rule:** for `openai`, `anthropic`, `gemini`, and `groq`, the runtime rejects the request when the workspace has no active BYOK credential. It does not silently use a platform key. `omniroute` is not in that strict list and can use environment credentials; treat that as a platform-cost decision, not a tenant BYOK control. Provider credentials are tenant-scoped and encrypted. Custom `base_url` values can target private/loopback networks (`allow_local=True`); there is no allowlist. Restrict this at the edge or add an allowlist before untrusted tenants can configure providers.

---

## 3. Startup fail-closed behavior

### 3.1 What refuses to start

| Misconfiguration | Result | Evidence |
|---|---|---|
| Non-development CORS with an `http://localhost` or `http://127.0.0.1` origin | `RuntimeError` from `build_cors_policy`; app creation fails | `backend/app/core/cors.py:22-23`, `60-65` |
| Non-development CORS with `*` | `RuntimeError`; wildcard cannot be combined with credentialed requests | `cors.py:67-71` |
| Non-development CORS with no origins and no regex | `RuntimeError`; no permissive default | `cors.py:73-78` |
| `ENVIRONMENT=production` + `STORAGE_BACKEND=local` | `RuntimeError`; startup validation fails | `backend/app/storage/__init__.py:23-30`; `backend/app/main.py:20-23` |
| S3 backend with no `S3_BUCKET_NAME` | `RuntimeError` | `storage/__init__.py:35-39` |
| S3 endpoint configured without access/secret keys | `RuntimeError` | `storage/__init__.py:41-47` |
| Unsupported storage backend | `ValueError` | `storage/__init__.py:32-33` |

CORS policy is computed in `create_app` before the app serves requests (`backend/app/main.py:122-133`). Storage validation runs at the start of the lifespan, outside the later `try` block, so a validation error aborts startup (`main.py:20-23`).

### 3.2 What does not refuse to start

| Condition | Current behavior | Why it matters |
|---|---|---|
| `ENVIRONMENT=staging` + `STORAGE_BACKEND=local` | **Starts.** Validation only rejects local for `production` (`storage/__init__.py:23-30`). | This profile requires an explicit `STORAGE_BACKEND=s3`; a missing S3 variable set can otherwise write to an ephemeral path. This is a **MISSING** staging guard. |
| Explicit LAN origin (for example `http://192.168.1.50:3000`) or `https://localhost` in `FRONTEND_URL`/`ALLOWED_ORIGINS` | **Starts.** Only `http://localhost` and `http://127.0.0.1` are auto-rejected; an explicitly listed LAN origin is accepted. | This is a **MISSING** policy guard; keep LAN and `https://localhost` origins out manually. |
| Development default `SECRET_KEY` / `JWT_SECRET` | **Starts.** There is no startup validator that rejects the known defaults (`config.py:27-30`). | A misconfigured staging deploy can sign tokens with a public default. This is **MISSING**. |
| Empty `SECRET_ENCRYPTION_KEY` | **Starts.** The crypto layer falls back to `SECRET_KEY` (Stage 7). | BYOK confidentiality becomes only as strong as `SECRET_KEY`, and rotation/escrow assumptions change. This is **PARTIAL** until a dedicated key is set. |
| Database unavailable at startup | Startup logs a warning and continues; `/ready` returns 503 | The process is alive but not ready. Do not route traffic until `/ready` is 200. |
| Wrong S3 bucket/credentials/region | Starts; first upload fails | Configuration validation checks settings, not connectivity. `/ready` does not check storage. This is **MISSING**. |
| Public publishing enabled | Starts; no global publish-off switch exists | Publication-level `is_active`/`visibility` gates apply, but there is no deployment-wide kill switch. This is **MISSING**. |
| `/docs`, `/redoc`, `/openapi.json` exposed | Starts; routes are enabled unconditionally | The backend URL is internet-facing. Block these at the proxy or add an environment flag if the staging policy requires it. This is **MISSING** as a configurable control. |
| Security headers absent | Starts; no app-level HSTS/CSP/X-Frame-Options middleware found | TLS is terminated at the edge, but app responses do not add these headers. This is **MISSING** / **UNVERIFIED** at the edge. |

**Startup schema caveat:** the lifespan also calls `Base.metadata.create_all` and seeds roles (`main.py:29-36`). This can create tables without Alembic. It is not a substitute for `preDeployCommand: alembic upgrade head`; deployment must verify the Alembic revision, not just that the app started.

---

## 4. Registration, invitation, and account lifecycle

### 4.1 Registration policy

- `registration_allowed()` returns an explicit `ALLOW_PUBLIC_REGISTRATION` when set; otherwise it allows registration only when `ENVIRONMENT` is `development` (`config.py:140-144`).
- The staging profile sets `ALLOW_PUBLIC_REGISTRATION=false`, and a direct staging probe confirmed the default also resolves to `False`.
- `POST /api/v1/auth/register` applies the registration rate limit first, then returns HTTP 403 with a stable message when registration is disabled (`auth.py:51-62`). No user or tenant is created.
- The frontend still contains a `/register` page and a link from `/login` (Stage 10). It is not a backend bypass: the API rejects the request. It is a UX/cleanup gap, not an authentication hole.

### 4.2 Invitations and first-owner bootstrap

The member invite endpoint now creates a real `Invitation` when the email is new (`members.py:120-130`):

- Raw token: `secrets.token_urlsafe(32)`; stored as SHA-256 hex, never plaintext (`invitation_service.py:16-23`, `41-52`).
- Expiry: 7 days (`INVITATION_EXPIRY_DAYS = 7`).
- Single use: acceptance sets `accepted_at`; a second attempt is rejected (`auth.py:143-150`).
- `POST /api/v1/auth/accept-invite` sets the invited user's password, marks the invitation accepted, and issues tokens (`auth.py:125-183`). It remains available when public registration is disabled.
- The invite response includes the raw `invitation_token` once (`members.py:157-158`). There is no email delivery and no frontend accept-invite page. The UI invite modal discards the token; an operator must use an approved API client to capture it and deliver it out of band.
- The invited membership is created `ACTIVE` immediately (`members.py:117`), while the user's password is a random placeholder until acceptance (`members.py:91-101`). The account cannot be used to log in before acceptance unless the operator resets it.

**First-owner bootstrap is unresolved.** With registration disabled, there is no committed bootstrap-admin CLI. The deployment must choose one of:

1. A short, approved bootstrap window with `ALLOW_PUBLIC_REGISTRATION=true`, protected by the Vercel gate and rate limits, followed immediately by a redeploy with `false`; or
2. A small, reviewed bootstrap command/operator script that creates the owner, tenant, and owner membership with an Argon2id password, executed once in the Render shell.

Do not leave registration enabled after the owner exists. This is a user decision in the deployment plan.

### 4.3 Missing account lifecycle controls

| Control | Status | Evidence |
|---|---|---|
| Password reset / forgot password | **MISSING** | No route in `backend/app/api/v1/router.py`; Stage 7 static finding remains. |
| Email verification | **MISSING / not enforced** | `is_verified` defaults to true and is not checked for authorization (Stage 7). |
| MFA / SSO | **MISSING** | No implementation. |
| Invite email delivery | **MISSING** | Token is returned in the API response only. |
| Frontend accept-invite page | **MISSING** | No route under `frontend/app/`; API-only onboarding. |
| Server-side logout/refresh revocation | **MISSING** | Logout is a no-op; refresh tokens remain valid until expiry (`auth.py:312-318`; Stage 7). |
| User-level suspension endpoint | **PARTIAL / MISSING** | Membership suspension exists; user/tenant suspension endpoints do not (Stage 7). |
---

## 5. Rate limits as implemented

The limiter is a dependency-free sliding window held in the Python process (`backend/app/core/rate_limit.py:1-13`, `38-92`). Keys are SHA-256 hashed before storage; logs include only an opaque prefix (`rate_limit.py:95-121`). State is lost on restart and is not shared between workers.

| Endpoint / action | Identity key | Limit / window (code default) | Recommended staging | Evidence |
|---|---|---|---|---|
| `POST /auth/register` | Client IP | `RATE_LIMIT_REGISTER_PER_HOUR` / 3600 s (20) | 5 | `auth.py:51-56` |
| `POST /auth/accept-invite` | Client IP | `RATE_LIMIT_INVITE_ACCEPT_PER_HOUR` / 3600 s (20) | 10 | `auth.py:132-137` |
| `POST /auth/login` | Client IP + lowercased email | `RATE_LIMIT_LOGIN_PER_MINUTE` / 60 s (10) | 10 | `auth.py:194-199` |
| `POST /public/assistants/{id}/chat` | Client IP | `RATE_LIMIT_PUBLIC_MESSAGE_PER_MINUTE` / 60 s (20) | 10 | `public_chat.py:73-78` |
| `POST /developer/.../chat` | API key ID | `RATE_LIMIT_DEVELOPER_PER_MINUTE` / 60 s (60) | 30 | `developer.py:157-161` |
| `POST /knowledge/.../upload` | Tenant ID + user ID | `RATE_LIMIT_UPLOAD_PER_HOUR` / 3600 s (60) | 30 | `knowledge.py:245-250` |

Exceeded requests receive HTTP 429 with `Retry-After` (`rate_limit.py:117-121`). The limiter is checked before expensive work: register before policy/DB, login before password verification, public chat before quota/session/provider, upload before storage.

**Limitations (do not overclaim):**

- Effective cluster-wide limit is approximately configured limit x number of worker processes. The recommended staging topology is one process. The current `render.yaml` still starts two workers (`render.yaml:15`), which would double limits and break single-process assumptions.
- There is no limit on `/auth/refresh`, `/auth/me`, `/auth/logout`, publishing routes, or all other endpoints. An authenticated user can call those without a limiter.
- State is in memory only. A restart clears counters. There is no Redis-backed shared limiter.
- The key store is bounded to 10,000 keys and evicts the oldest key, so an attacker rotating identities can cause eviction of legitimate counters.
- If `TRUSTED_PROXY_IPS` is wrong, `client_identity()` either ignores legitimate forwarding or trusts a spoofable header. The default empty list ignores `X-Forwarded-For` entirely (`rate_limit.py:124-136`).

---

## 6. Trusted-proxy rule

`client_identity()` uses `request.client.host` by default. It reads `X-Forwarded-For` only when that peer is exactly listed in `TRUSTED_PROXY_IPS`, and then uses only the first hop (`rate_limit.py:124-136`).

| Case | Behavior | Test |
|---|---|---|
| Empty trust list | `X-Forwarded-For` is ignored; peer address is used | `test_untrusted_client_ignores_forwarded_header` |
| Peer in trust list | First forwarded hop is used | `test_trusted_proxy_uses_first_forwarded_hop` |
| Peer in trust list, empty header | Falls back to peer | `test_trusted_proxy_with_empty_forwarded_value_falls_back` |

Staging recommendation: leave `TRUSTED_PROXY_IPS` empty until the actual Render edge peer addresses are measured. If Render presents all traffic from a shared proxy peer and the list is set to that peer, the first forwarded hop becomes the rate-limit identity; if the list is wrong, clients can spoof it. This is **UNVERIFIED** live and must be tested with two client addresses.

---

## 7. Public publishing and embed controls

### 7.1 Publication gates

- Public metadata requires an active publication with `visibility == "PUBLIC"`; otherwise 404 (`public_chat.py:29-58`). Workspace-only and inactive publications return 404.
- Public chat requires `pub.is_active` and `visibility == "PUBLIC"`; otherwise 403 (`public_chat.py:80-93`).
- Public retrieval is restricted at runtime to documents with `access_level == "PUBLIC"` and non-`DELETED` status (`runtime.py:185-194`).
- Public chat uses the publication's tenant quota and records `traffic_type="public"` (`public_chat.py:104-106`; `runtime.py:370-382`).
- Anonymous sessions are scoped to the publication, expire after 7 days, and a client-supplied token is accepted only for the same publication (Stage 7).
- Public chat rate limiting runs before quota, session creation, and provider calls (`public_chat.py:73-78`).

### 7.2 Embed allowlist behavior

`is_origin_allowed()` (`publishing_service.py:76-129`) has these semantics:

| Stored allowlist | Behavior |
|---|---|
| `None`, `""`, or `[]` | **Unrestricted**: any origin, including a missing Origin, is allowed. |
| Explicit `"*"` entry | Unrestricted. |
| Non-empty restricted list | Missing or malformed Origin/Referer is **denied**. |
| Exact host entry, e.g. `example.com` | Matches that host; subdomains do not match. |
| Wildcard entry, e.g. `*.example.com` | Matches subdomains only, not the bare domain. |
| Ports | Ignored unless the entry specifies one; default ports are 80/443. |
| Schemes | Only `http` and `https`; other schemes are denied. |
| Corrupt JSON | **Fails closed** (returns `False`). |

The tests cover the allowlist matrix and the missing-Origin denial when restricted (`test_m11_embed_allowlist.py`; included in the 75-pass run). **The allowlist is not authentication.** A non-browser client can send any `Origin` header; and an empty list allows everyone. Do not use it to keep a private assistant private.

### 7.3 Global public-publishing disablement

**MISSING.** There is no `ALLOW_PUBLIC_PUBLISHING` or equivalent setting. The only controls are:

- Keep every assistant `PRIVATE`/`WORKSPACE` and do not call publish.
- Unpublish existing publications via `POST /assistants/{id}/unpublish` (`publishing.py:89`).
- Optionally set `assistant_publications.is_active=false` through an operator-only database action (not exposed as a bulk admin API).

For private staging, public publishing is a **manual operational prohibition**, not an enforced platform control. This must be recorded as a residual risk.

### 7.4 Embed script and object access

- The embed script is served from the backend (`public_chat.py:190-221`) and derives the iframe origin from the script URL.
- The frontend publish UI's copied snippet assumes a same-origin proxy; Stage 10 records this as M-02. It is an integration risk, not a security boundary.
- R2 is private and the backend proxies object bytes. No presigned URLs are used. No browser ever receives bucket credentials.

---

## 8. Logging, redaction, health, and readiness

### 8.1 Redaction

| Control | Status | Evidence |
|---|---|---|
| Provider error sanitization | **IMPLEMENTED** | `sanitize_error_message()` redacts API-key-like strings, bearer tokens, test secrets, and `password/secret/api_key/token=` patterns (`runtime.py:33-39`). Used on generation errors. |
| Rate-limit identity hashing | **IMPLEMENTED** | Keys are SHA-256 hashed; logs include only `key[:12]` (`rate_limit.py:95-121`). |
| Raw BYOK key logging | **No raw key logging found** | Stage 7 static review; BYOK responses are masked and use key IDs/names. |
| Tracer secret redaction | **TESTED (LOCAL)** | `test_m10_stage1_security_verification.py` redaction test (Stage 7). |
| Central logging configuration / structured audit | **MISSING** | No `dictConfig`/`basicConfig`/structured logger setup found in `app/core` or `main.py`; Uvicorn defaults apply. |
| Request/header/body redaction policy | **MISSING** | No middleware or documented proxy policy for Authorization headers, query strings, or invitation tokens. |
| Provider error text returned to tenant admins | **PARTIAL** | `POST /providers/credentials/{id}/test` can return provider error text (Stage 7); this is not key material but may reveal endpoint details. |
| Trace persistence and purge | **PARTIAL / MISSING** | Traces persist to `backend/data/observability_traces.json` with tenant IDs; no purge API (Stage 8). |

Treat invitation tokens, JWTs, BYOK keys, and R2 credentials as secrets in logs, screenshots, tickets, and evidence. Do not enable request-body logging on the Render service.

### 8.2 Health and readiness exposure

| Endpoint | Authentication | What it reveals | Status |
|---|---|---|---|
| `GET /health` | None | Process liveness, version, timestamp | Public by design (`main.py:135-142`). |
| `GET /ready` | None | Database connectivity status | Public; checks PostgreSQL only (`main.py:144-157`). Storage is not checked. |
| `GET /docs`, `/redoc`, `/openapi.json` | None | Full API schema and interactive docs | Enabled unconditionally (`main.py:113-120`). No environment flag. |
| Render health check | N/A | Currently `/health`; recommended `/ready` | Current `render.yaml:16` uses `/health`. |

There is no application-level HSTS, CSP, `X-Frame-Options`, or `X-Content-Type-Options` middleware. Edge TLS exists at Vercel/Render, but the response headers are **UNVERIFIED** and not enforced by this repository. The backend URL is directly reachable; the Vercel gate does not protect it.

**Recommendation:** block `/docs`, `/redoc`, and `/openapi.json` at the edge for staging, or add an environment-gated disable in a separate code change. Add a storage readiness probe before real documents. Both are **MISSING** today.

---

## 9. Security control checklist

Status values are limited to those in Section 0. A test name means the test exists; the result column distinguishes tests re-run in this pass from prior evidence.

| # | Control | Status | Implementation / evidence | Residual gap |
|---:|---|---|---|---|
| 1 | Frontend private access | **RECOMMENDED / NOT PROVISIONED** | Stage 1: Vercel Pro, Vercel Authentication, All Deployments, free Viewer seats | No live access test; Vercel account and spend not approved. |
| 2 | Backend private access | **MISSING** | Render web service is public; CORS is not authentication | `/health`, `/ready`, `/docs`, auth endpoints, and public chat are directly reachable. |
| 3 | Open registration disabled | **IMPLEMENTED / TESTED (LOCAL)** | `config.py:140-144`; `auth.py:58-62`; `test_m11_registration_policy.py` (5 tests) | Frontend register page/link remains; UI cleanup pending. |
| 4 | Invitation acceptance | **IMPLEMENTED / TESTED (LOCAL)** | `auth.py:125-183`; `invitation_service.py:16-59`; `test_m11_invitation_acceptance.py` (6 tests) | No email delivery, no frontend accept page, no password reset. |
| 5 | Password hashing | **IMPLEMENTED** | Argon2id, time_cost 3, 64 MiB, parallelism 4 (`security.py:10-17`) | `needs_rehash()` not called on login (Stage 7). |
| 6 | Password policy | **PARTIAL** | Minimum 8 characters (`schemas/auth.py`; Stage 7) | No complexity, breach-list, or maximum length. |
| 7 | JWT access/refresh | **IMPLEMENTED / PARTIAL** | HS256, type checks, expiry; `security.py`; `auth.py` | No revocation/JTI denylist; logout no-op; refresh token not rotated/revoked. |
| 8 | Rate limiting | **IMPLEMENTED / TESTED (LOCAL)** | `rate_limit.py`; six endpoint call sites; `test_m11_rate_limiting.py` (part of 75-pass run) | Per-process only; not all endpoints; no Redis; wrong proxy list can weaken it. |
| 9 | Trusted proxy handling | **IMPLEMENTED / TESTED (LOCAL)** | `rate_limit.py:124-136`; three unit tests in the 75-pass run | Live Render peer addresses **UNVERIFIED**; keep list empty until measured. |
| 10 | CORS policy | **IMPLEMENTED / TESTED (LOCAL)** | `cors.py:26-80`; `main.py:122-133`; 10 CORS tests in the 75-pass run | Default Vercel regex is broader than necessary; override to empty/narrow. LAN/https://localhost origins are not auto-rejected; keep them out manually. |
| 11 | Startup CORS fail-closed | **IMPLEMENTED / TESTED (LOCAL)** | `cors.py:60-78`; staging localhost probe rejected | Staging uses the same path as production; confirmed by probe. |
| 12 | Production local-storage rejection | **IMPLEMENTED / TESTED (LOCAL)** | `storage/__init__.py:23-30`; `test_remediation_stage3_storage.py` (in 23-pass run) | Only `production`; see #13. |
| 13 | Staging local-storage rejection | **MISSING** | Direct staging probe: `validate_storage_configuration()` returned without error | A staging deploy can silently use ephemeral local storage if S3 vars are omitted. |
| 14 | Startup rejection of default secrets | **MISSING** | No validator in `config.py`; defaults at `config.py:27-30` | A misconfigured deploy can boot with public dev defaults. Add a preflight/env check. |
| 15 | S3 tenant key isolation | **IMPLEMENTED / TESTED (MOCKED)** | `s3.py:36-43`; `test_s3_storage.py`; `test_remediation_stage3_storage.py` | No live R2 round-trip; actual double-prefix key layout must be verified. |
| 16 | S3 live CRUD / connectivity | **UNVERIFIED / NOT RUN** | Stage 8 and Stage 1: mocked only | First live upload is the real test. |
| 17 | S3/R2 backup, versioning, lifecycle, inventory | **MISSING** | Stage 8: no object-store backup/reconciliation path; R2 S3 versioning is marked unimplemented | Real documents remain blocked. |
| 18 | Storage readiness probe | **MISSING** | `/ready` checks PostgreSQL only (`main.py:144-157`) | Bucket outage can look healthy. |
| 19 | BYOK encryption and rotation primitives | **IMPLEMENTED / TESTED (LOCAL)** | `crypto.py`; `byok_vault.py:169-191`; `test_remediation_encryption_key.py`; `test_quota_and_byok_policy.py` | Key escrow and full rotation coverage missing. |
| 20 | Dedicated encryption key and escrow | **PARTIAL / MISSING** | `SECRET_ENCRYPTION_KEY` supported; `render.yaml:51-52` uses `generateValue`; no escrow | Set a dedicated key manually and escrow it; do not rely on generated-only storage. |
| 21 | Rotation coverage | **PARTIAL** | `PREVIOUS_SECRET_KEYS` + MultiFernet; rotation command only scans `RetrievalConfig` (Stage 8) | Provider credentials and assistant keys are not rotated by the command. |
| 22 | Strict no platform fallback | **IMPLEMENTED / TESTED (LOCAL)** | `runtime.py:260-280`; `test_quota_and_byok_policy.py` | Applies to openai/anthropic/gemini/groq; OmniRoute can still use platform env keys. |
| 23 | BYOK base-URL egress allowlist | **MISSING** | `openai_provider.py` uses `allow_local=True`; Stage 7 finding | Tenant admins can target private/loopback networks. |
| 24 | Public publication gate | **IMPLEMENTED / TESTED (LOCAL)** | `public_chat.py:29-58`, `80-93`; `test_m11_public_metadata.py` | No global publish-off switch. |
| 25 | Public-only document restriction | **IMPLEMENTED / TESTED (LOCAL)** | `runtime.py:185-194`; `test_m08_publishing_and_api_keys.py`; `test_m10_stage1_security_verification.py` | Live retrieval not re-tested in this pass. |
| 26 | Public metadata minimization | **IMPLEMENTED / TESTED (LOCAL)** | `test_m11_public_metadata.py` (4 tests in 75-pass run) | None material. |
| 27 | Embed origin allowlist | **IMPLEMENTED / TESTED (LOCAL)** | `publishing_service.py:76-129`; `test_m11_embed_allowlist.py` | Empty list is unrestricted; not authentication; non-browser can forge Origin. |
| 28 | Global public-publishing disablement | **MISSING** | No config flag; only per-publication state | Manual prohibition only. |
| 29 | Tenant isolation | **TESTED (LOCAL, PRIOR)** | Stage 7: 91-test suite passed; `deps.py:49-171` | Citations, groups, audit reads, tenant status, and some conversation tests were static/partial. |
| 30 | Tenant status enforcement | **MISSING / PARTIAL** | Stage 7: `get_current_tenant_context` does not check `tenant.status` | Suspended tenants with active memberships remain reachable. |
| 31 | Audit coverage for auth/public traffic | **PARTIAL / MISSING** | Stage 7: no registration, login, failed login, logout, public chat, API-key, or BYOK audit events | Proxy access logs are the compensating control. |
| 32 | Health/readiness minimization | **PARTIAL** | `/health` and `/ready` public; DB only | No auth, no storage check, no rate limit. |
| 33 | API docs exposure | **MISSING** | `main.py:113-120` enables docs unconditionally | Block at edge or add a flag. |
| 34 | Security headers | **MISSING / UNVERIFIED** | No app middleware found | Edge headers not verified. |
| 35 | Backend dependency lockfile | **IMPLEMENTED / VALIDATED** | `backend/requirements.lock`, `requirements-dev.lock`; Dockerfile and `render.yaml` build use it | Lock and Dockerfile changes are uncommitted; include them in the release. |
| 36 | Background job claim/lease | **IMPLEMENTED / TESTED (LOCAL)** | `job_queue.py`; `test_m11_job_reliability.py`; Stage 5 37-pass run | No heartbeat; PG `SKIP LOCKED` live path not exercised. |
| 37 | PostgreSQL migration chain | **PASS (LOCAL PG)** | Stage 2: fresh `upgrade head` to `0010`; 46 tables, 98 FKs, 119 indexes; 12 tests | Not run against Render PostgreSQL. |
| 38 | Backup/restore drill | **LOCAL PASS / LIVE MISSING** | `M11_BACKUP_RESTORE_DRILL.md`: local paired drill PASS; S3/R2/PITR NOT TESTED | Live staging rehearsal required before real documents. |
| 39 | Optional services disabled | **VERIFIED (LOCAL)** | `M11_OPTIONAL_INFRASTRUCTURE_DECISION.md`: 0 Qdrant constructions; Qdrant/Redis/Phoenix disabled | No live staging service inventory; no Qdrant live tests. |
| 40 | Manual UI acceptance | **PENDING** | Stage 10: 18 areas / 82 sub-checks not executed | Complete before inviting testers. |
| 41 | Real-document readiness | **NO** | Stage 8: `STAGING_READY = NO` | P0-1 through P0-8 and live checks required. |

---

## 10. Explicit non-claims and missing controls

This profile does **not** claim any of the following:

- A complete security review, penetration test, or threat model.
- Live staging validation of Vercel, Render, R2, PostgreSQL, SSE, or provider calls.
- WAF, DDoS protection, bot management, or IP allowlisting for the backend.
- MFA, SSO, email verification, password reset, or account recovery.
- Server-side JWT revocation, refresh rotation, or logout invalidation.
- Tenant suspension enforcement, tenant erasure, or a deletion certificate.
- Malware scanning, DLP, content moderation, or prompt-injection defense.
- Complete audit coverage for authentication, public chat, API keys, or BYOK changes.
- Storage backup, object versioning, PITR verification, or live restore.
- A staging-specific guard against `STORAGE_BACKEND=local`; only production is guarded.
- A startup check that rejects development default secrets.
- A global switch that disables public publishing.
- Private access to the backend API; only the frontend edge is proposed to be private.
- Security headers at the application layer.
- Manual UI acceptance; Stage 10 remains pending.

These gaps are why the staging posture is **closed, synthetic-data only**, and why real documents are blocked.

---

## 11. Staging security go/no-go

### 11.1 GO conditions for a closed synthetic-data cohort

All of the following must be true and recorded:

1. User approves spend, provider choices, testers, data classification, and the real-document gate (see the deployment plan).
2. The reviewed release commit/tag includes the M11 working-tree changes and lockfiles; no uncommitted source is deployed.
3. Vercel Deployment Protection is enabled for all deployments; testers are Viewer seats; the frontend URL is not public.
4. Backend is deployed with `ENVIRONMENT=staging`, `DEBUG=false`, `ALLOW_PUBLIC_REGISTRATION=false`, exact CORS, S3 storage, one worker, and the rate limits in Section 2.
5. `SECRET_KEY`, `JWT_SECRET`, and `SECRET_ENCRYPTION_KEY` are unique, not defaults, not committed, and escrowed.
6. `/health` and `/ready` return 200; Alembic is at `0010`; pgvector extension exists; no local storage path is used.
7. R2 round-trip succeeds for a synthetic object; the actual key layout is recorded; no public bucket access.
8. Public publishing is disabled operationally; no PUBLIC publication exists.
9. Backend is reachable only as approved; if it is internet-facing, the residual risk is accepted in writing; `/docs` exposure is blocked or accepted.
10. A live backup/PITR check and a restore rehearsal are scheduled before any real document (or the cohort is synthetic-only).
11. Manual UI acceptance (Stage 10) is completed or explicitly waived for the synthetic cohort.
12. The 91-test security suite, the 12 PostgreSQL tests, and the targeted M11 tests are green in the release environment.

### 11.2 NO-GO conditions

Do not invite testers or upload data if any of these is true:

- Registration is enabled, or the frontend/backend is publicly reachable without the Vercel gate.
- `STORAGE_BACKEND=local` in staging.
- Default `SECRET_KEY`/`JWT_SECRET` or an unescrowed `SECRET_ENCRYPTION_KEY`.
- CORS includes localhost, LAN, or wildcard.
- More than one API worker/instance with the in-process dispatcher and no shared claim/limit review.
- Public publishing is enabled for the cohort.
- Real documents are uploaded before Stage 8 P0 closure and a live restore drill.
- `/docs`/`/openapi.json` exposure or an open backend URL is not accepted by the risk owner.
- No backup owner, no retention decision, or no restore evidence.

---

## 12. Source references for the checklist

| Area | Primary source |
|---|---|
| Settings and registration policy | `backend/app/core/config.py:14-33`, `56-132`, `140-147` |
| CORS | `backend/app/core/cors.py:11-80`; `backend/app/main.py:122-133` |
| Auth, invites, login | `backend/app/api/v1/auth.py:45-183`, `186-229`, `231-318`; `backend/app/services/invitation_service.py:13-59`; `backend/app/api/v1/members.py:53-159` |
| Rate limiting / proxy | `backend/app/core/rate_limit.py:38-136`; call sites in `auth.py`, `public_chat.py`, `developer.py`, `knowledge.py` |
| Storage validation / S3 / local | `backend/app/storage/__init__.py:11-60`; `s3.py:36-200`; `local.py:17-107`; `main.py:20-23` |
| Assistant runtime / BYOK | `backend/app/assistant_runtime/runtime.py:33-39`, `69-87`, `185-194`, `236-280`, `299-368`; `backend/app/services/byok_vault.py:169-191` |
| Public chat / embed | `backend/app/api/v1/public_chat.py:29-221`; `backend/app/services/publishing_service.py:76-129` |
| Health/readiness/docs | `backend/app/main.py:113-157` |
| Authorization | `backend/app/api/deps.py:49-171` |
| Password hashing | `backend/app/core/security.py:10-38` |

---

## 13. Final statement

**Recommended profile:** a closed, invite-only, synthetic-data staging environment on Vercel Pro + Render + Render PostgreSQL + private R2, with one API process, pgvector, strict BYOK, exact CORS, disabled optional services, and public publishing operationally off.

**Current verdict:** the repository has real controls, but the profile is **not fully enforced by code**. Staging local storage, default secrets, backend public exposure, missing storage readiness/backup, missing global publish-off, and incomplete account lifecycle controls remain. This is why the security profile is a set of gates, not a certification.

**Real documents:** **NO-GO** until M11 Stage 8 P0-1 through P0-8 are closed and a live backup/restore drill passes (or a written synthetic-only risk acceptance is recorded).

No accounts, cloud resources, deployments, billing, or Git mutations were created by this document.

---

## Addendum — post-report alignment (2026-11-12)

> Appended after the original report. The sections above are unchanged.

- `render.yaml` now matches the verified single-process staging profile: `--workers 1`, `autoDeploy: false`, `ALLOW_PUBLIC_REGISTRATION=false`, `RATE_LIMIT_ENABLED=true`, `TRUSTED_PROXY_IPS` supplied by the operator (`sync: false`), `INGESTION_INLINE_DISPATCHER_ENABLED=true`, `INGESTION_LEASE_SECONDS=3600`, `INGESTION_MAX_CONCURRENCY=1`, `DEFAULT_VECTOR_STORE=pgvector`, and no `STORAGE_PATH`.
- The hard-coded OpenAI `LLM_BASE_URL` and the generic `auto` `LLM_DEFAULT_MODEL` were removed from the blueprint. The approved provider or gateway URL and model are chosen at deploy time; selecting a provider/gateway remains a deployment decision.
- `healthCheckPath: /health`, `preDeployCommand: alembic upgrade head`, the S3 storage keys, `SECRET_*` generation, `DATABASE_URL`/`DATABASE_SYNC_URL` from the managed database, and the lockfile-based build command are preserved.
- Plan sizes and spend are **not** changed. Plan/spend selection still requires explicit user approval. This addendum does not approve or create any account, resource, or deployment.
- `.env.production.example` now agrees on the same staging variable names and values and uses provider/gateway placeholders instead of a hard-coded OpenAI endpoint.
