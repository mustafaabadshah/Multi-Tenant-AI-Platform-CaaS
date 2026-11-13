# M13.3 Stage 5/6 — Staging Environment Matrix

| Field | Value |
|---|---|
| Milestone | M13.3 Stage 5/6 |
| Document | Actual environment variable names, required/secret status, build/runtime behavior, staging values, blueprint sync state, and dashboard overrides |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Baseline | `main` @ `9c27e1b8d3e6aeec00dcf6ddb84cd849b9a607e8`; worktree includes M13.3 edits |
| Date | 2026-11-13 |
| Inputs | `render.yaml`, `backend/app/core/config.py`, `.env.example`, `.env.production.example`, `frontend/lib/api.ts`, provider adapters, M13/M13.2/M13.3 documents |
| Verification | Read-only source inspection. Local `Settings.model_fields` enumeration printed field names only; no environment value or secret was printed. No external call, provisioning, or deployment was performed |
| Name rule | Actual names only. A requested name that does not exist is recorded as absent rather than invented |

> No secret values appear in this document. Placeholders such as `<generated-secret>`, `<neon-async-url>`, `<private-b2-bucket>`, and `<exact-https-origin>` are not credentials. `sync: false` means Render prompts for the value; `generateValue: true` means Render generates it; a literal value is committed in the blueprint.

---

## 1. How to read the matrix

| Column | Meaning |
|---|---|
| `Variable` | Exact environment variable name as read by the named consumer |
| `Service` | `Backend` (FastAPI/Render Docker) or `Frontend` (Next.js/Render Node) |
| `Required?` | `Yes` = must be set for this staging envelope; `Conditional` = required for the stated feature; `Optional` = safe default exists; `No` = keep unset/empty; `Platform-injected` = supplied by Render |
| `Secret?` | `Yes` = secret material or a connection string with a password; `No` = non-secret; `Generated secret` = Render-generated secret |
| `Build/Runtime` | `Runtime` = read when the process starts or handles requests; `Build-time` = baked into the frontend bundle; `Build env` = consumed by the platform builder; `Migration` = used by Alembic |
| `Format` | Expected value shape |
| `Safe staging value/placeholder` | A safe non-secret value or placeholder, not a real credential |
| `Source` | Repository file and line where the name and/or value is defined |
| `sync:false?` | `Yes` = `sync: false` in `render.yaml`; `No (literal)` = literal value; `generateValue: true`; `Absent` = not in the blueprint |
| `Dashboard override needed?` | Whether the value must be confirmed or supplied in the Render Dashboard after a Blueprint sync |
| `Verified locally?` | `Yes (Settings field)` = present in the locally enumerated `Settings.model_fields`; `Yes (source)` = verified in the named repository source; `Name only` = platform-injected and not locally provable; `Not in Settings` = deliberately absent from `Settings` |

`Verified locally` means the name/source was verified on this workstation. It does **not** mean a live provider value was validated. No live Render, Neon, B2, or gateway value was checked.

---

## 2. Name corrections and mismatches

These are the material differences between commonly assumed names and the actual staging surface.

| Assumed / shorthand name | Actual status | Evidence | Correct action |
|---|---|---|---|
| `CORS_ORIGINS` | **Does not exist** | `Settings.model_fields`; `config.py` defines `ALLOWED_ORIGINS` and `CORS_ORIGIN_REGEX` | Use `ALLOWED_ORIGINS` (empty) plus `CORS_ORIGIN_REGEX=^$`; exact origins come from `FRONTEND_URL` |
| `ENCRYPTION_KEY` | **Exists but is unused** | `config.py:137`; the only runtime key read is `SECRET_ENCRYPTION_KEY` in `core/crypto.py:23-28` | Do not set `ENCRYPTION_KEY`; set `SECRET_ENCRYPTION_KEY` |
| `SECRET_ENCRYPTION_KEY` | Exists and is used | `config.py:36`; `core/crypto.py:23-28` | Use this name for BYOK Fernet key material |
| `CORS_ORIGIN_REGEX` | Exists | `config.py:31`; `render.yaml:84-85` | Set `^$` and confirm it persists |
| `RATE_LIMIT_*` | Seven actual names, not a wildcard | `config.py:116-124` | Use `RATE_LIMIT_ENABLED`, `RATE_LIMIT_LOGIN_PER_MINUTE`, `RATE_LIMIT_REGISTER_PER_HOUR`, `RATE_LIMIT_INVITE_ACCEPT_PER_HOUR`, `RATE_LIMIT_PUBLIC_MESSAGE_PER_MINUTE`, `RATE_LIMIT_DEVELOPER_PER_MINUTE`, `RATE_LIMIT_UPLOAD_PER_HOUR` |
| `PORT` | **Not in `Settings` or `.env.example`** | `render.yaml:27,156`; Render injects it | Do not set manually; the start commands use `$PORT` |
| `NEXT_PUBLIC_API_URL` | **Not in `render.yaml` or `.env.example`** | `frontend/lib/api.ts:3` accepts it as a fallback; `.env.production.example:141` has only a comment | Leave unset; `NEXT_PUBLIC_API_BASE_URL` takes precedence |
| `NEXT_PUBLIC_API_BASE_URL` | Exists in the frontend blueprint | `render.yaml:165-166`; `frontend/lib/api.ts:3-6` | Set before the serving build; rebuild after any change |
| `NODE_VERSION` | Render build environment, not a backend `Settings` field | `render.yaml:161-162` | Use `22.22.0`; do not look for it in `config.py` |
| `AWS_REQUEST_CHECKSUM_CALCULATION` / `AWS_RESPONSE_CHECKSUM_VALIDATION` | **Not `Settings` fields**; botocore environment variables | `render.yaml:141-144` | Set both to `when_required` for B2 |
| `DATABASE_SYNC_URL` | Exists, but online Alembic uses `DATABASE_URL` | `config.py:44`; `alembic/env.py:70-76` per the M13 inventory | Set both, but verify the migration target via `DATABASE_URL` |
| `OPENAI_API_KEY` / `OMNIROUTE_API_KEY` | Exist in `Settings` | `config.py:111-112`; `render.yaml:120-123` | Keep empty for BYOK-only staging |
| `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `GOOGLE_API_KEY` / `GROQ_API_KEY` | **Not `Settings` fields**; read directly by adapters | `anthropic_provider.py:44`; `gemini_provider.py:43`; `groq_provider.py:23` | Keep empty; do not expect them in `Settings` validation |
| `DEFAULT_EMBEDDING_MODEL` / `DEFAULT_EMBEDDING_DIMENSIONS` | Full names, not `MODEL`/`DIMENSIONS` | `config.py:130-131` | Use the full names |
| `MAX_EXTRACTED_TEXT_SIZE_BYTES` | Full name, not `MAX_EXTRACTED_TEXT_SIZE` | `config.py:78` | Use the full name |
| `OCR_ENABLED_DEFAULT` | Full name, not `OCR_ENABLED` | `config.py:95` | Use the full name |
| `ALLOWED_ORIGINS` | Exists; `CORS_ORIGINS` does not | `config.py:29` | Keep empty for staging |
| `ENABLE_API_DOCS` | Exists; absent from `render.yaml` | `config.py:25`; `main.py:117-128` | Staging derives `false`; set explicitly if an auditable value is required |
| `ALLOW_DEV_LAN_ORIGINS` | Exists; absent from `render.yaml` | `config.py:30` | Keep `false`; confirm the code default |
| `STORAGE_PATH` | Exists but should be unset with S3 | `config.py:70` | Do not set; use `STORAGE_BACKEND=s3` |
| `S3_REGION_NAME` | Exists; no literal blueprint value | `config.py:75`; `render.yaml:138-139` | Set the actual B2 bucket region, not `us-east-1` or `auto` |
| `LLM_DEFAULT_MODEL` | Exists, but is not a platform fallback switch | `config.py:113` | Optional; `auto` is only appropriate for OmniRoute/Groq |

---

## 3. Backend matrix — core runtime and URLs

| Variable | Service | Required? | Secret? | Build/Runtime | Format | Safe staging value/placeholder | Source | sync:false? | Dashboard override needed? | Verified locally? |
|---|---|---|---|---|---|---|---|---|---|---|
| `ENVIRONMENT` | Backend | Yes | No | Runtime | string | `staging` | `config.py:14`; `render.yaml:31-32` | No (literal) | No | Yes (Settings field) |
| `DEBUG` | Backend | Yes | No | Runtime | bool | `false` | `config.py:16`; `render.yaml:33-34` | No (literal) | No | Yes (Settings field) |
| `FRONTEND_URL` | Backend | Yes | No | Runtime | HTTPS origin | `https://<exact-frontend-origin>`; no trailing slash | `config.py:27`; `render.yaml:79-80` | Yes | Yes — supply the exact frontend origin | Yes (Settings field) |
| `BACKEND_URL` | Backend | Yes | No | Runtime | HTTPS origin | `https://<exact-backend-origin>`; no `/api/v1`, no trailing slash | `config.py:28`; `render.yaml:81-82` | Yes | Yes — supply the exact backend origin | Yes (Settings field) |
| `ALLOWED_ORIGINS` | Backend | Optional | No | Runtime | comma-separated exact origins | empty | `config.py:29`; `.env.example:34` | Absent | No — keep empty; do not add localhost/LAN/wildcard | Yes (Settings field) |
| `CORS_ORIGIN_REGEX` | Backend | Yes | No | Runtime | regex | `^$` | `config.py:31`; `render.yaml:84-85` | No (literal) | Confirm `^$` persisted; do not replace with the broad Vercel default | Yes (Settings field) |
| `ALLOW_DEV_LAN_ORIGINS` | Backend | No (must be false) | No | Runtime | bool | `false` | `config.py:30`; `.env.example:37` | Absent | No — confirm false | Yes (Settings field) |
| `ALLOW_PUBLIC_REGISTRATION` | Backend | Yes | No | Runtime | bool | `false` | `config.py:15`; `render.yaml:35-36` | No (literal) | No | Yes (Settings field) |
| `PUBLIC_PUBLISHING_ENABLED` | Backend | No (must be false) | No | Runtime | bool | `false` | `config.py:21` | Absent | Confirm false; set explicitly if the audit requires a pinned value | Yes (Settings field) |
| `DEVELOPER_API_ENABLED` | Backend | No (must be false) | No | Runtime | bool | `false` | `config.py:22` | Absent | Confirm false; set explicitly if the audit requires a pinned value | Yes (Settings field) |
| `CUSTOM_PROVIDER_ENDPOINTS_ENABLED` | Backend | No (must be false) | No | Runtime | bool | `false` | `config.py:23` | Absent | Confirm false; set explicitly if the audit requires a pinned value | Yes (Settings field) |
| `ENABLE_API_DOCS` | Backend | Conditional | No | Runtime | bool | `false` | `config.py:25`; `main.py:117-128` | Absent | Optional explicit `false`; in staging the derived default is false | Yes (Settings field) |
| `PORT` | Backend | Platform-injected | No | Runtime | integer string | `$PORT` (Render) | `render.yaml:27` | Not applicable | No — never set manually | Name only (Render-injected) |

---

## 4. Backend matrix — secrets and token lifetime

| Variable | Service | Required? | Secret? | Build/Runtime | Format | Safe staging value/placeholder | Source | sync:false? | Dashboard override needed? | Verified locally? |
|---|---|---|---|---|---|---|---|---|---|---|
| `SECRET_KEY` | Backend | Yes | **Generated secret** | Runtime | high-entropy string, at least 32 bytes | `<render-generated-secret>`; do not reuse as `JWT_SECRET` | `config.py:34`; `render.yaml:55-56` | `generateValue: true` | No — verify the fingerprint; override only if using an externally managed secret | Yes (Settings field) |
| `JWT_SECRET` | Backend | Yes | **Generated secret** | Runtime | high-entropy string, different from `SECRET_KEY` | `<render-generated-jwt-secret>` | `config.py:37`; `render.yaml:57-58` | `generateValue: true` | No — verify the fingerprint and that it differs from `SECRET_KEY` | Yes (Settings field) |
| `SECRET_ENCRYPTION_KEY` | Backend | Yes | **Generated secret** | Runtime | Fernet key material or high-entropy string | `<generated-fernet-key-or-escrowed-key>`; never equal to `SECRET_KEY` | `config.py:36`; `render.yaml:67-68`; `core/crypto.py:23-28` | `generateValue: true` | Recommended override if a separately escrowed key is required; verify non-empty and distinct | Yes (Settings field) |
| `PREVIOUS_SECRET_KEYS` | Backend | Optional | Yes (only during rotation) | Runtime | comma-separated old key material | empty on first use | `config.py:35`; `render.yaml:69-70` | No (literal) | No — keep empty until a rotation | Yes (Settings field) |
| `JWT_ALGORITHM` | Backend | Optional | No | Runtime | string | `HS256` | `config.py:38`; `render.yaml:59-60` | No (literal) | No | Yes (Settings field) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Backend | Optional | No | Runtime | int (minutes) | `60` | `config.py:39`; `render.yaml:61-62` | No (literal) | No | Yes (Settings field) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Backend | Optional | No | Runtime | int (days) | `7` | `config.py:40`; `render.yaml:63-64` | No (literal) | No | Yes (Settings field) |

The M13 secret inventory flags that the application does not reject the public development `SECRET_KEY` / `JWT_SECRET` defaults. With `generateValue: true`, Render supplies unique values; still verify fingerprints and keep an escrow reference for `SECRET_ENCRYPTION_KEY`.

---

## 5. Backend matrix — database

| Variable | Service | Required? | Secret? | Build/Runtime | Format | Safe staging value/placeholder | Source | sync:false? | Dashboard override needed? | Verified locally? |
|---|---|---|---|---|---|---|---|---|---|---|
| `DATABASE_URL` | Backend (runtime + migrations) | Yes | **Yes** (connection string) | Runtime and Migration | asyncpg URL | `postgresql+asyncpg://<user>:<password>@<neon-direct-host>/<db>?ssl=require` | `config.py:43`; `render.yaml:51-52` | Yes | Yes — `ssl=require`; no `sslmode`/`channel_binding`; add `prepared_statement_cache_size=0` only for the pooled endpoint | Yes (Settings field) |
| `DATABASE_SYNC_URL` | Backend (offline Alembic/tooling) | Conditional | **Yes** (connection string) | Migration/tooling | libpq URL | `postgresql://<user>:<password>@<neon-direct-host>/<db>?sslmode=require` | `config.py:44`; `render.yaml:49-50` | Yes | Yes — supply it, but note online Alembic uses `DATABASE_URL` | Yes (Settings field) |
| `DB_POOL_SIZE` | Backend | Optional | No | Runtime | int | `5` | `config.py:63` | Absent | No | Yes (Settings field) |
| `DB_MAX_OVERFLOW` | Backend | Optional | No | Runtime | int | `10` | `config.py:64` | Absent | No | Yes (Settings field) |
| `DB_POOL_TIMEOUT` | Backend | Optional | No | Runtime | int (seconds) | `30` | `config.py:65` | Absent | No | Yes (Settings field) |
| `DB_POOL_RECYCLE` | Backend | Optional | No | Runtime | int (seconds) | `1800` | `config.py:66` | Absent | No | Yes (Settings field) |

`DATABASE_URL` is the online Alembic target. `DATABASE_SYNC_URL` is for offline SQL and tooling; it does not redirect `alembic upgrade head`. The container command runs `alembic upgrade head` before Uvicorn, so a bad database URL is a failed deploy, not a running app with a stale schema.

---

## 6. Backend matrix — rate limiting and proxy trust

| Variable | Service | Required? | Secret? | Build/Runtime | Format | Safe staging value/placeholder | Source | sync:false? | Dashboard override needed? | Verified locally? |
|---|---|---|---|---|---|---|---|---|---|---|
| `RATE_LIMIT_ENABLED` | Backend | Yes | No | Runtime | bool | `true` | `config.py:116`; `render.yaml:73-74` | No (literal) | No | Yes (Settings field) |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | Backend | Optional | No | Runtime | int | `10` | `config.py:119`; `.env.example:56` | Absent | No — code default applies | Yes (Settings field) |
| `RATE_LIMIT_REGISTER_PER_HOUR` | Backend | Optional | No | Runtime | int | `20` | `config.py:120`; `.env.example:57` | Absent | No — code default applies | Yes (Settings field) |
| `RATE_LIMIT_INVITE_ACCEPT_PER_HOUR` | Backend | Optional | No | Runtime | int | `20` | `config.py:121`; `.env.example:58` | Absent | No — code default applies | Yes (Settings field) |
| `RATE_LIMIT_PUBLIC_MESSAGE_PER_MINUTE` | Backend | Optional | No | Runtime | int | `20` | `config.py:122`; `.env.example:59` | Absent | No — code default applies | Yes (Settings field) |
| `RATE_LIMIT_DEVELOPER_PER_MINUTE` | Backend | Optional | No | Runtime | int | `60` | `config.py:123`; `.env.example:60` | Absent | No — code default applies | Yes (Settings field) |
| `RATE_LIMIT_UPLOAD_PER_HOUR` | Backend | Optional | No | Runtime | int | `60` | `config.py:124`; `.env.example:61` | Absent | No — code default applies | Yes (Settings field) |
| `TRUSTED_PROXY_IPS` | Backend | Yes (measure first) | No (IP list) | Runtime | comma-separated exact IPs | empty until measured; then the exact Render edge peers | `config.py:118`; `render.yaml:75-76` | Yes | Yes — measure with two client addresses; no CIDRs or wildcards | Yes (Settings field); live value unverified |

Rate limiting is per process and in-memory. With `TRUSTED_PROXY_IPS` empty behind Render's proxy, clients can collapse into the proxy's bucket; a guessed value lets clients spoof identity. Keep one Uvicorn worker.

---

## 7. Backend matrix — ingestion dispatcher

| Variable | Service | Required? | Secret? | Build/Runtime | Format | Safe staging value/placeholder | Source | sync:false? | Dashboard override needed? | Verified locally? |
|---|---|---|---|---|---|---|---|---|---|---|
| `INGESTION_INLINE_DISPATCHER_ENABLED` | Backend | Yes | No | Runtime | bool | `true` | `config.py:85`; `render.yaml:108-109` | No (literal) | No | Yes (Settings field) |
| `INGESTION_DISPATCHER_POLL_SECONDS` | Backend | Yes | No | Runtime | int (seconds) | `3600` | `config.py:87`; `render.yaml:110-111` | No (literal) | No | Yes (Settings field) |
| `INGESTION_LEASE_SECONDS` | Backend | Yes | No | Runtime | int (seconds) | `3600` | `config.py:90`; `render.yaml:112-113` | No (literal) | No | Yes (Settings field) |
| `INGESTION_MAX_CONCURRENCY` | Backend | Yes | No | Runtime | int | `1` | `config.py:92`; `render.yaml:114-115` | No (literal) | No | Yes (Settings field) |

The 3,600-second poll is an empty-queue poll; uploads and retries still call `asyncio.create_task` immediately. The lease has no heartbeat, so a job running longer than 3,600 seconds can be requeued and executed twice. Keep one API process and one concurrent job.

---

## 8. Backend matrix — retrieval and embeddings

| Variable | Service | Required? | Secret? | Build/Runtime | Format | Safe staging value/placeholder | Source | sync:false? | Dashboard override needed? | Verified locally? |
|---|---|---|---|---|---|---|---|---|---|---|
| `DEFAULT_VECTOR_STORE` | Backend | Yes | No | Runtime | enum | `pgvector` | `config.py:128`; `render.yaml:90-91` | No (literal) | No | Yes (Settings field) |
| `DEFAULT_RETRIEVAL_MODE` | Backend | Yes | No | Runtime | enum | `hybrid` | `config.py:127`; `render.yaml:88-89` | No (literal) | No | Yes (Settings field) |
| `DEFAULT_EMBEDDING_PROVIDER` | Backend | Yes | No | Runtime | enum | `local` | `config.py:129`; `render.yaml:93-94` | No (literal) | No — do not switch to a model-downloading provider | Yes (Settings field) |
| `DEFAULT_EMBEDDING_MODEL` | Backend | Yes | No | Runtime | string | `local-feature-projection` | `config.py:130`; `render.yaml:95-96` | No (literal) | No | Yes (Settings field) |
| `DEFAULT_EMBEDDING_DIMENSIONS` | Backend | Yes | No | Runtime | int | `384` | `config.py:131`; `render.yaml:97-98` | No (literal) | No | Yes (Settings field) |

The code defaults are `omniroute` / `text-embedding-3-small` / `1536`; the staging blueprint overrides them to `local` / `local-feature-projection` / `384`. Do not deploy with the code defaults for a 512 MB instance.

---

## 9. Backend matrix — object storage and B2

| Variable | Service | Required? | Secret? | Build/Runtime | Format | Safe staging value/placeholder | Source | sync:false? | Dashboard override needed? | Verified locally? |
|---|---|---|---|---|---|---|---|---|---|---|
| `STORAGE_BACKEND` | Backend | Yes | No | Runtime | enum | `s3` | `config.py:69`; `render.yaml:128-129` | No (literal) | No — must be `s3`; `staging` does not reject `local` | Yes (Settings field) |
| `S3_BUCKET_NAME` | Backend | Yes | No | Runtime | bucket name | `<private-b2-bucket>` | `config.py:71`; `render.yaml:130-131` | Yes | Yes — private, DNS-safe bucket | Yes (Settings field) |
| `S3_ENDPOINT_URL` | Backend | Yes for B2 | No | Runtime | HTTPS URL | `https://s3.<b2-region>.backblazeb2.com`; no bucket appended, no trailing slash | `config.py:72`; `render.yaml:132-133` | Yes | Yes | Yes (Settings field) |
| `S3_ACCESS_KEY_ID` | Backend | Yes when endpoint is set | **Yes** | Runtime | key ID | `<b2-key-id>`; scope to one bucket with list/read/write/delete | `config.py:73`; `render.yaml:134-135` | Yes | Yes | Yes (Settings field) |
| `S3_SECRET_ACCESS_KEY` | Backend | Yes when endpoint is set | **Yes** | Runtime | secret | `<b2-application-key>` | `config.py:74`; `render.yaml:136-137` | Yes | Yes | Yes (Settings field) |
| `S3_REGION_NAME` | Backend | Yes | No | Runtime | region code | `<b2-region-code>`, for example `us-west-004`; never `auto` and not the `us-east-1` default | `config.py:75`; `render.yaml:138-139` | Yes | Yes — use the bucket's actual region | Yes (Settings field) |
| `AWS_REQUEST_CHECKSUM_CALCULATION` | Backend | Yes for B2 | No | Runtime (botocore) | enum | `when_required` | `render.yaml:141-142` | No (literal) | No | Yes (source; not a `Settings` field) |
| `AWS_RESPONSE_CHECKSUM_VALIDATION` | Backend | Yes for B2 | No | Runtime (botocore) | enum | `when_required` | `render.yaml:143-144` | No (literal) | No | Yes (source; not a `Settings` field) |
| `STORAGE_PATH` | Backend | No — do not set | No | Runtime | filesystem path | unset | `config.py:70`; `.env.example:99` | Absent | No — leave unset under S3 | Yes (Settings field) |

The bucket is private; there is no public bucket URL, website configuration, or public custom domain. B2 is versioned by default: `DeleteObject` hides the current version, older versions remain, and lifecycle management is required. Verify a real PUT/GET with the checksum settings before ingest testing.

---

## 10. Backend matrix — upload limits and OCR

| Variable | Service | Required? | Secret? | Build/Runtime | Format | Safe staging value/placeholder | Source | sync:false? | Dashboard override needed? | Verified locally? |
|---|---|---|---|---|---|---|---|---|---|---|
| `MAX_FILE_SIZE_BYTES` | Backend | Optional (effective default) | No | Runtime | int (bytes) | `10485760` (10 MiB) | `config.py:76`; `.env.example:105` | Absent | No — code default applies | Yes (Settings field) |
| `MAX_FILES_PER_REQUEST` | Backend | Optional (effective default) | No | Runtime | int | `2` | `config.py:77`; `.env.example:107` | Absent | No — code default applies; send one file per request | Yes (Settings field) |
| `MAX_EXTRACTED_TEXT_SIZE_BYTES` | Backend | Optional (effective default) | No | Runtime | int (bytes) | `5242880` (5 MiB) | `config.py:78`; `.env.example:109` | Absent | No — code default applies | Yes (Settings field) |
| `OCR_ENABLED_DEFAULT` | Backend | No (must be false) | No | Runtime | bool | `false` | `config.py:95`; `.env.example:111` | Absent | No — keep false; per-KB OCR can still be enabled | Yes (Settings field) |

Additional limits that exist but are not itemized in the request: `MAX_ARCHIVE_EXPANSION_BYTES=104857600`, `MAX_PROCESSING_DURATION_SECONDS=600`, `MAX_DOCUMENT_PAGES=1000` (`config.py:79-81`). They are enforced by the M13.2/M13.3 parsing path, but the staging posture remains small synthetic files, OCR off, and one ingestion at a time.

---

## 11. Backend matrix — LLM gateway and BYOK keys

| Variable | Service | Required? | Secret? | Build/Runtime | Format | Safe staging value/placeholder | Source | sync:false? | Dashboard override needed? | Verified locally? |
|---|---|---|---|---|---|---|---|---|---|---|
| `LLM_BASE_URL` | Backend | Conditional | No | Runtime | URL | empty, or `https://<approved-gateway>/v1`; never `http://localhost:20128/v1` in a cloud container | `config.py:110`; `render.yaml:118-119` | Yes | Yes — supply an approved endpoint or explicit empty value | Yes (Settings field) |
| `OPENAI_API_KEY` | Backend | No | **Yes** | Runtime | secret string | empty | `config.py:112`; `render.yaml:120-121` | Yes | Yes — keep empty for BYOK-only staging | Yes (Settings field) |
| `OMNIROUTE_API_KEY` | Backend | No | **Yes** | Runtime | secret string | empty | `config.py:111`; `render.yaml:122-123` | Yes | Yes — keep empty unless an approved gateway credential is required | Yes (Settings field) |
| `LLM_DEFAULT_MODEL` | Backend | Optional | No | Runtime | string | `auto` only for OmniRoute/Groq; explicit model for direct providers | `config.py:113` | Absent | No | Yes (Settings field) |
| `ANTHROPIC_API_KEY` | Backend | No | **Yes** | Runtime | secret string | empty | `llm/providers/anthropic_provider.py:44` | Absent | No — leave unset | Yes (adapter source; not in `Settings`) |
| `GEMINI_API_KEY` | Backend | No | **Yes** | Runtime | secret string | empty | `llm/providers/gemini_provider.py:43` | Absent | No — leave unset | Yes (adapter source; not in `Settings`) |
| `GOOGLE_API_KEY` | Backend | No | **Yes** | Runtime | secret string | empty | `llm/providers/gemini_provider.py:43` | Absent | No — leave unset | Yes (adapter source; not in `Settings`) |
| `GROQ_API_KEY` | Backend | No | **Yes** | Runtime | secret string | empty | `llm/providers/groq_provider.py:23` | Absent | No — leave unset | Yes (adapter source; not in `Settings`) |

Chat with `openai`, `anthropic`, `gemini`, and `groq` is BYOK-strict: the runtime rejects those providers when the workspace has no active credential. There is no platform-paid fallback for those four. OmniRoute and the OpenAI-compatible embedding path can use environment keys, so keeping every platform key empty is what makes the BYOK-only posture effective. `LLM_BASE_URL` does not redirect the registered OmniRoute chat provider because the registry sets a provider default first; do not rely on it for OmniRoute chat.

---

## 12. Frontend matrix

| Variable | Service | Required? | Secret? | Build/Runtime | Format | Safe staging value/placeholder | Source | sync:false? | Dashboard override needed? | Verified locally? |
|---|---|---|---|---|---|---|---|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Frontend | Yes | No | **Build-time (baked)** | HTTPS origin | `https://<exact-backend-origin>`; no `/api/v1`, no trailing slash | `render.yaml:165-166`; `frontend/lib/api.ts:3-6` | Yes | Yes — set before the serving build; a runtime-only change does not replace the inlined value | Yes (source) |
| `NEXT_PUBLIC_API_URL` | Frontend | No | No | **Build-time (baked)** | HTTPS origin | unset, or the same origin as `NEXT_PUBLIC_API_BASE_URL` | `frontend/lib/api.ts:3`; `.env.production.example:141` (comment only) | Absent | No — leave unset; `NEXT_PUBLIC_API_BASE_URL` takes precedence | Yes (fallback source) |
| `NODE_VERSION` | Frontend | Yes | No | Build env | string | `22.22.0` | `render.yaml:161-162` | No (literal) | No | Yes (source; Render build env) |
| `PORT` | Frontend | Platform-injected | No | Runtime | integer string | `$PORT` (Render) | `render.yaml:156` | Not applicable | No — never set manually | Name only (Render-injected) |

`frontend/lib/api.ts` resolves `NEXT_PUBLIC_API_BASE_URL || NEXT_PUBLIC_API_URL` first, then falls back to a local/LAN address in development, and fails closed in production when neither public variable is configured. Because both are `NEXT_PUBLIC_*`, they are inlined at build time. Changing the backend origin requires a frontend rebuild, not just a restart.

---

## 13. Related settings present but not itemized in the request

These names exist in the configuration surface. They are recorded so the matrix is not mistaken for the full `Settings` schema.

| Group | Actual settings | Staging posture | Source |
|---|---|---|---|
| Project/API identity | `PROJECT_NAME`, `API_V1_STR` | `Multi-Tenant AI Platform-CaaS`, `/api/v1`; literal in the blueprint | `config.py:17-18`; `render.yaml:37-40` |
| JWT lifetime | `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | `HS256`, `60`, `7`; literal | `config.py:38-40`; `render.yaml:59-64` |
| Database pool | `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE` | `5`, `10`, `30`, `1800`; code defaults | `config.py:63-66` |
| Local storage path | `STORAGE_PATH` | unset under S3; default `./data/storage` | `config.py:70`; `.env.example:99` |
| Archive/page/time budget | `MAX_ARCHIVE_EXPANSION_BYTES`, `MAX_PROCESSING_DURATION_SECONDS`, `MAX_DOCUMENT_PAGES` | `104857600`, `600`, `1000`; code defaults | `config.py:79-81` |
| OCR internals | `OCR_DEFAULT_PROVIDER`, `OCR_DEFAULT_LANGUAGE`, `TESSERACT_CMD`, `BADHO_OCR_API_KEY`, `BADHO_OCR_API_URL` | `tesseract`, `eng`, unset, empty, unset | `config.py:96-100` |
| Embedding tuning | `EMBEDDING_BATCH_SIZE`, `EMBEDDING_TIMEOUT_SECONDS`, `EMBEDDING_MAX_RETRIES`, `RRF_K_CONSTANT`, `RERANKING_ENABLED_DEFAULT`, `MAX_EMBEDDING_TOKENS_PER_REQUEST`, `MAX_TOP_K` | `32`, `30`, `3`, `60`, `false`, `8192`, `50`; code defaults/blueprint | `config.py:132-139`; `render.yaml:99-102` |
| Optional services | `REDIS_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION_NAME`, `PHOENIX_ENABLED` | empty/unused; no Redis, Qdrant, or Phoenix in staging | `config.py:103-107` |
| Legacy key | `ENCRYPTION_KEY` | **do not set**; unused; use `SECRET_ENCRYPTION_KEY` | `config.py:137`; `core/crypto.py:23-28` |
| Python provenance | `PYTHON_VERSION` | `3.12.3`; no-op under Docker | `render.yaml:42-43` |
| Frontend fallback | `NEXT_PUBLIC_API_URL` | unset; accepted fallback only | `frontend/lib/api.ts:3`; `.env.production.example:141` |

---

## 14. Post-Blueprint-sync dashboard override checklist

Render environment variables set in the Dashboard take precedence over blueprint values. `sync: false` values must be entered before the first deploy; generated secrets are stored after generation. Complete this checklist in order.

### 14.1 Before the first backend deploy

- [ ] `DATABASE_URL` is the Neon **direct** async URL, uses `postgresql+asyncpg://` and `?ssl=require`, and contains no `sslmode=` or `channel_binding=`.
- [ ] `DATABASE_URL` does not point at `localhost`; the target database is the intended staging database. If the pooled endpoint is used, `prepared_statement_cache_size=0` is present.
- [ ] `DATABASE_SYNC_URL` is the Neon **direct** sync URL with `postgresql://` and `?sslmode=require`; the operator records that online Alembic still uses `DATABASE_URL`.
- [ ] `FRONTEND_URL` is the exact HTTPS frontend origin, with no trailing slash.
- [ ] `BACKEND_URL` is the exact HTTPS backend origin, with no `/api/v1` and no trailing slash.
- [ ] `ALLOWED_ORIGINS` is empty.
- [ ] `CORS_ORIGIN_REGEX` is `^$` and the Dashboard shows the literal `^$`, not an empty value and not the broad Vercel preview regex.
- [ ] `ALLOW_DEV_LAN_ORIGINS` is `false`.
- [ ] `ALLOW_PUBLIC_REGISTRATION` is `false`.
- [ ] `PUBLIC_PUBLISHING_ENABLED` is `false` or absent (code default false).
- [ ] `DEVELOPER_API_ENABLED` is `false` or absent (code default false).
- [ ] `CUSTOM_PROVIDER_ENDPOINTS_ENABLED` is `false` or absent (code default false).
- [ ] `ENABLE_API_DOCS` is `false` or absent; in staging the derived default is false.
- [ ] `STORAGE_BACKEND` is `s3`; `STORAGE_PATH` is unset.
- [ ] `S3_BUCKET_NAME` is the private B2 bucket.
- [ ] `S3_ENDPOINT_URL` is `https://s3.<b2-region>.backblazeb2.com` with no bucket and no trailing slash.
- [ ] `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` are the scoped B2 application key; the secret is not in the repository.
- [ ] `S3_REGION_NAME` is the bucket's actual B2 region code, not `auto` and not the `us-east-1` code default.
- [ ] `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` and `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required` are present.
- [ ] `TRUSTED_PROXY_IPS` is empty until measured, or contains the exact measured Render edge peers; no CIDRs and no wildcards.
- [ ] `LLM_BASE_URL` is an approved externally reachable gateway URL or an explicit empty value; it is not `http://localhost:20128/v1`.
- [ ] `OPENAI_API_KEY` and `OMNIROUTE_API_KEY` are empty unless a platform-funded gateway is explicitly approved.
- [ ] `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, and `GROQ_API_KEY` are empty.
- [ ] `OCR_ENABLED_DEFAULT` is `false`.
- [ ] `INGESTION_INLINE_DISPATCHER_ENABLED=true`, `INGESTION_DISPATCHER_POLL_SECONDS=3600`, `INGESTION_LEASE_SECONDS=3600`, `INGESTION_MAX_CONCURRENCY=1`.
- [ ] `DEFAULT_RETRIEVAL_MODE=hybrid`, `DEFAULT_VECTOR_STORE=pgvector`, `DEFAULT_EMBEDDING_PROVIDER=local`, `DEFAULT_EMBEDDING_MODEL=local-feature-projection`, `DEFAULT_EMBEDDING_DIMENSIONS=384`.
- [ ] `SECRET_KEY`, `JWT_SECRET`, and `SECRET_ENCRYPTION_KEY` are generated values (or externally supplied), all different, non-default, and fingerprinted; `SECRET_ENCRYPTION_KEY` has an escrow reference.
- [ ] The backend service has one instance, one Uvicorn worker, and `autoDeploy: false`.
- [ ] `PORT` was not set manually; the container command binds `$PORT`.

If any of `SECRET_KEY`, `JWT_SECRET`, or `SECRET_ENCRYPTION_KEY` is changed from `generateValue: true` to a literal or Dashboard-supplied value, set it before the first deploy, keep all three distinct, and record fingerprints and the `SECRET_ENCRYPTION_KEY` escrow reference.

### 14.2 Before the frontend build

- [ ] `NEXT_PUBLIC_API_BASE_URL` is set to the exact backend HTTPS origin, with no `/api/v1` and no trailing slash.
- [ ] `NEXT_PUBLIC_API_URL` is unset, or is the identical origin. Do not set it to a different value; `NEXT_PUBLIC_API_BASE_URL` wins.
- [ ] `NODE_VERSION` is `22.22.0`.
- [ ] The frontend service has one instance and `autoDeploy: false`.
- [ ] After any change to `NEXT_PUBLIC_API_BASE_URL`, rebuild the frontend. A restart alone does not replace the inlined value.
- [ ] `PORT` was not set manually; `npm run start -- -p $PORT` uses Render's value.

### 14.3 After sync and before acceptance

- [ ] The Render Dashboard values match this matrix, or every override is recorded with an owner and reason.
- [ ] `GET /health` returns 200; `/health` is the platform probe.
- [ ] A deliberate `GET /ready` returns 200 with `database=connected`; it is not polled continuously.
- [ ] `POST /api/v1/auth/register` returns 403 with registration disabled.
- [ ] CORS preflight from the exact frontend origin succeeds; an unlisted origin and `http://localhost:3000` fail.
- [ ] An upload writes to B2, not to the Render filesystem; the object key is tenant-prefixed; the bucket is private.
- [ ] A B2 PUT/GET/DELETE smoke test succeeds with `when_required` checksums; the billed/version state is recorded.
- [ ] No platform-paid LLM key is configured; a chat path either uses an approved gateway/BYOK credential or fails closed.
- [ ] Public publishing, Developer API, and custom provider endpoints remain disabled for the synthetic cohort.
- [ ] No keep-alive, uptime ping, or scheduled `/ready` probe is configured.
- [ ] No second backend process, separate ingestion worker, or paid Render add-on is present.

---

## 15. Findings: missing, unpinned, or unsafe settings

| Rank | Finding | Severity | Evidence | Smallest safe action |
|---:|---|---|---|---|
| 1 | `CORS_ORIGINS` does not exist | Low (naming) | `Settings.model_fields`; `config.py:29-31` | Use `ALLOWED_ORIGINS` plus `CORS_ORIGIN_REGEX`; do not invent `CORS_ORIGINS` |
| 2 | `ENCRYPTION_KEY` exists but is unused | Medium (misleading) | `config.py:137`; only `SECRET_ENCRYPTION_KEY` is read at `core/crypto.py:23-28` | Do not set `ENCRYPTION_KEY`; set `SECRET_ENCRYPTION_KEY` |
| 3 | Public development `SECRET_KEY` / `JWT_SECRET` defaults are not rejected | High | `config.py:34,37`; M13 secret inventory Section 5.3 | Keep `generateValue: true` or supply unique secrets; verify fingerprints are not the public defaults |
| 4 | `SECRET_ENCRYPTION_KEY` uses Render `generateValue` but has no built-in escrow | High | `render.yaml:67-68`; M13 secret inventory | Record a dual-control escrow reference; override with an externally generated key if policy requires |
| 5 | `ENABLE_API_DOCS`, `PUBLIC_PUBLISHING_ENABLED`, `DEVELOPER_API_ENABLED`, and `CUSTOM_PROVIDER_ENDPOINTS_ENABLED` are absent from `render.yaml` | Medium (auditability) | `config.py:21-25`; M13.3 blueprint review | Confirm the false defaults in the Dashboard; pin them explicitly if the review requires dashboard-visible values |
| 6 | `ALLOW_DEV_LAN_ORIGINS` and `ALLOWED_ORIGINS` are absent from `render.yaml` | Low/Medium | `config.py:29-30` | Confirm `ALLOW_DEV_LAN_ORIGINS=false` and `ALLOWED_ORIGINS` empty; do not add LAN/localhost origins |
| 7 | `CORS_ORIGIN_REGEX` was previously an empty string that Render might drop | High if reverted | `render.yaml:84-85`; M13.3 review | Keep the literal `^$`; confirm it persisted after sync |
| 8 | `S3_REGION_NAME` has no literal blueprint value | High operational | `config.py:75`; `render.yaml:138-139` | Set the actual B2 region code in the Dashboard |
| 9 | `LLM_BASE_URL` code default is `http://localhost:20128/v1` | High in a cloud container | `config.py:110` | Set an approved external gateway URL or an explicit empty value; never leave localhost |
| 10 | `TRUSTED_PROXY_IPS` is `sync: false` with no value | Medium operational | `config.py:118`; `render.yaml:75-76` | Measure the exact Render edge peers; empty collapses per-IP buckets behind the proxy |
| 11 | `DATABASE_SYNC_URL` does not control online Alembic | High operational | `config.py:44`; `alembic/env.py:70-76` per M13 inventory | Verify the `DATABASE_URL` target before migration; keep both URLs consistent |
| 12 | No `PORT` setting exists in `Settings` or `.env.example` | Low (platform) | `render.yaml:27,156` | Do not add `PORT` to `.env`; Render injects it and the start commands use `$PORT` |
| 13 | `NEXT_PUBLIC_API_URL` is not in `render.yaml` or `.env.example` | Low | `frontend/lib/api.ts:3`; `.env.production.example:141` | Leave it unset; use `NEXT_PUBLIC_API_BASE_URL` only |
| 14 | `MAX_FILE_SIZE_BYTES`, `MAX_FILES_PER_REQUEST`, `MAX_EXTRACTED_TEXT_SIZE_BYTES`, and `OCR_ENABLED_DEFAULT` are not pinned in `render.yaml` | Medium (auditability) | `config.py:76-78,95` | Confirm the code defaults in staging; pin them explicitly if the review requires a dashboard-visible envelope |
| 15 | `STORAGE_PATH` remains a code default even when S3 is selected | Low/Medium | `config.py:70` | Leave `STORAGE_PATH` unset; verify no local file appears after an upload |
| 16 | `.env.example` and `.env.production.example` contain development/paid-profile values (`ENABLE_API_DOCS=true`, `ALLOW_PUBLIC_REGISTRATION=true`, `sentence-transformers`, larger upload limits) | Medium (copy risk) | `.env.example:10,26,133-135`; `.env.production.example:102-113` | Do not copy either template into the Free staging environment; use this matrix and `render.yaml` |
| 17 | `CORS_ORIGIN_REGEX` comment in `render.yaml` still says "Explicitly empty" while the value is `^$` | Low (documentation drift) | `render.yaml:83-85`; M13.3 review | Treat the value as authoritative; fix the comment only in a future approved edit |
| 18 | `NEXT_PUBLIC_API_BASE_URL` is build-time only | Medium operational | `frontend/lib/api.ts:3-6`; `render.yaml:165-166` | Set it before the first serving build; rebuild after any backend-origin change |

---

## 16. Verification record

- `backend/app/core/config.py` was read directly; `Settings.model_fields` was enumerated from the class and only field names were printed. No `.env` contents or secret values were printed.
- `render.yaml` was read directly; the M13.3 review already parsed it as two Free web services with no `databases` block and confirmed the `$PORT` / `exec` command shape.
- `frontend/lib/api.ts` was read directly; the precedence is `NEXT_PUBLIC_API_BASE_URL` first, then `NEXT_PUBLIC_API_URL`.
- `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, and `GROQ_API_KEY` were confirmed in provider adapter source, not in `Settings.model_fields`.
- `AWS_REQUEST_CHECKSUM_CALCULATION` and `AWS_RESPONSE_CHECKSUM_VALIDATION` were confirmed only in `render.yaml`; they are botocore environment variables, not `Settings` fields.
- No external provider, account, billing, or deployment action was performed. No secret value was generated, printed, recorded, or written.

---

## 17. Report summary

**Documents:**

- `docs/m13/M13_3_FREE_TIER_CAPACITY_AND_LIMITATIONS.md`
- `docs/m13/M13_3_STAGING_ENVIRONMENT_MATRIX.md`

**Environment-name mismatches found:**

1. `CORS_ORIGINS` does not exist; the actual names are `ALLOWED_ORIGINS` and `CORS_ORIGIN_REGEX`.
2. `ENCRYPTION_KEY` exists but is unused; the actual BYOK key is `SECRET_ENCRYPTION_KEY`.
3. `PORT` is not a `Settings` or `.env.example` field; it is Render-injected and used as `$PORT` in the start commands.
4. `NEXT_PUBLIC_API_URL` is not in `render.yaml` or `.env.example`; it is a code fallback behind `NEXT_PUBLIC_API_BASE_URL`.
5. `AWS_REQUEST_CHECKSUM_CALCULATION` and `AWS_RESPONSE_CHECKSUM_VALIDATION` are botocore variables, not `Settings` fields.
6. `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, and `GROQ_API_KEY` are adapter-read, not `Settings` fields.
7. `DATABASE_SYNC_URL` exists but online Alembic uses `DATABASE_URL`.
8. The rate-limit wildcard is actually seven variables: `RATE_LIMIT_ENABLED` plus six per-endpoint limits.
9. `DEFAULT_EMBEDDING_MODEL` and `DEFAULT_EMBEDDING_DIMENSIONS` are the full names, not `MODEL`/`DIMENSIONS`.

**Missing or unpinned settings:**

- `CORS_ORIGINS` is absent by design; no such variable exists.
- `PORT` is absent from application configuration; Render supplies it.
- `NEXT_PUBLIC_API_URL` is absent as an active blueprint/template setting; it is only a commented example and a code fallback.
- `ENABLE_API_DOCS`, `PUBLIC_PUBLISHING_ENABLED`, `DEVELOPER_API_ENABLED`, `CUSTOM_PROVIDER_ENDPOINTS_ENABLED`, `ALLOW_DEV_LAN_ORIGINS`, `ALLOWED_ORIGINS`, `MAX_FILE_SIZE_BYTES`, `MAX_FILES_PER_REQUEST`, `MAX_EXTRACTED_TEXT_SIZE_BYTES`, and `OCR_ENABLED_DEFAULT` are not pinned in `render.yaml`; they rely on safe code defaults.
- `S3_REGION_NAME` and `TRUSTED_PROXY_IPS` are `sync: false` with no blueprint values; both need operator input.
- `LLM_BASE_URL` is `sync: false` with a localhost code default; it needs an approved external value or explicit empty value.
- `SECRET_ENCRYPTION_KEY` is Render-generated but not escrowed by the blueprint; escrow is a manual control.
