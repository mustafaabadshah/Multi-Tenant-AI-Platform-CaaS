# M13.3 Stage 7 — Private Staging Operator Runbook

> **OPERATOR-ONLY. PREPARED, NOT EXECUTED.**
>
> **RUNBOOK_EXECUTED = NO**
>
> **DEPLOYMENT_AUTHORIZED = NO**
>
> This document is a runbook and approval record, not a deployment result. It does not create an account, provision a service, generate or reveal a secret, run a migration, upload data, invite a tester, or authorize a deployment. Every external action below requires the approval named in its phase.

| Item | Value |
|---|---|
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Milestone | M13.3 Stage 7 |
| Document | Private staging operator runbook |
| Prepared | 2026-11-13 |
| Topology | Render Free backend (Docker) + Render Free frontend (Node) + Neon Free PostgreSQL 16 + Backblaze B2 Free private bucket |
| Environment | `staging` |
| Data class | Synthetic only |
| Network posture | Public Render URLs protected by application authentication; **not network-private** |
| API docs | Default off |
| Onboarding | Invite-only |
| Payment posture | No card, no paid plan, no platform-paid LLM fallback |
| Phase count | 10 phases: A through J |

---

## 0. Scope, non-execution, and conventions

### 0.1 Scope

This runbook covers the approved free-tier staging cut:

- two Render Free web services: `mmaip-backend` and `mmaip-frontend`;
- external Neon Free PostgreSQL 16 database `mmaip_staging`;
- external Backblaze B2 Free private bucket;
- synthetic-only validation, invite-only testers, and no paid fallback.

It does **not** cover production, a custom domain, Render Postgres, Cloudflare R2, Google Cloud Run, Vercel Pro, paid add-ons, real customer data, or public publishing.

### 0.2 Non-execution statement

The authoring session was read-only. It did not deploy, provision, migrate, upload, invite, generate a secret, make an external call, or mutate Git. The presence of a command in this document is not evidence that it ran.

### 0.3 Placeholder convention

All angle-bracket values are placeholders. Never replace them with real values in this document, a chat, a ticket, a screenshot, a commit, or a shell transcript.

| Placeholder | Meaning |
|---|---|
| `<backend-host>` | Assigned Render backend hostname, without scheme or path |
| `<frontend-host>` | Assigned Render frontend hostname, without scheme or path |
| `<neon-direct-host>` | Neon direct (unpooled) hostname |
| `<db-password>` | Generated URL-safe database password |
| `<private-bucket>` | B2 private bucket name |
| `<b2-region-code>` | Actual B2 region code, for example `us-west-004` |
| `<b2-key-id>` | B2 application key ID |
| `<b2-application-key>` | B2 application key secret |
| `<tenant-uuid>` | Synthetic staging tenant UUID |
| `<owner-email>` | Operator-provisioned synthetic owner email |
| `<tester-email-N>` | Named tester's synthetic email |
| `<synthetic-password>` | Synthetic account password held outside the repository |
| `<approved-branch>` | Branch Render will track |
| `<approved-release-message>` | Approved release commit message |

### 0.4 Evidence discipline

Record only names, references, fingerprints, status codes, timestamps, and redacted evidence. Never record a secret value, password, token, connection string with a password, or full provider key. Store acceptance evidence outside the repository unless an approved artifact location exists.

---

## 1. Preconditions and approvals

### 1.1 Hosting architecture

| Component | Approved shape | Key limit or constraint |
|---|---|---|
| Backend | Render Free Docker web service `mmaip-backend` | 0.1 CPU / 512 MB; one instance; no persistent disk; ephemeral filesystem; no shell or one-off jobs; cannot receive private-network traffic |
| Frontend | Render Free Node web service `mmaip-frontend` | 0.1 CPU / 512 MB; `next build` then `next start`; `/login` health check |
| Render allowance | 750 Free instance-hours per workspace per month | Shared by both services; exhaustion suspends all Free web services until the next month |
| Database | Neon Free PostgreSQL 16, `mmaip_staging` | 100 CU-hours/project/month; 1 GB storage; 5 GB egress; scale-to-zero after 5 minutes; 6-hour instant restore; one manual snapshot |
| Object storage | Backblaze B2 Free, private bucket | First 10 GB account-wide, including all versions; egress free up to 3x average monthly storage; versioning always on |
| Not approved | Render Postgres, Redis, Cloudflare R2, Google Cloud Run, Vercel Pro, paid add-ons, custom domain | Do not create, enable, or purchase |

The architecture is a demo/staging envelope, not a high-availability or production topology. Do not describe it as private infrastructure.

### 1.2 Public Render URLs — application auth, not network privacy

Render Free web services are internet-reachable. The backend URL `https://<backend-host>` and frontend URL `https://<frontend-host>` are public. The controls are:

- application authentication and tenant-membership checks;
- invite-only onboarding;
- exact CORS origins with no wildcard;
- API docs disabled;
- public publishing, developer API, custom provider endpoints, and public registration disabled;
- rate limiting;
- no platform-paid LLM fallback;
- synthetic data only.

CORS is a browser policy, not authentication. `/health` and `/ready` are public. `/ready` performs a real database round trip and can wake Neon; do not poll it. If an approval requires a network-private environment or an IP-allowlisted backend, **stop**: this architecture does not provide that.

### 1.3 Cost and usage risk

A free allowance is not a zero-charge guarantee. The approved stack remains at $0 only while all of these are true:

- both Render services stay within the shared 750 instance-hours and 5 GB bandwidth;
- Neon stays within 100 CU-hours, 1 GB storage, and 5 GB egress;
- B2 stays within 10 GB storage including all versions and its egress allowance;
- no payment method is added;
- no paid add-on, upgrade, or fallback is enabled.

Known arithmetic:

- two Render services kept warm 24/7 consume 1,440 instance-hours, about 192% of the pool; idle spin-down is what keeps the demo inside the allowance;
- a backend kept awake 24/7 can consume about 180 Neon CU-hours in a 30-day month and exhaust the allowance in roughly 16.7 days; scale-to-zero and the 3,600-second dispatcher poll reduce idle wakeups, but requests, uploads, and chat still wake the database;
- B2 versioning means deleted or overwritten objects still count toward 10 GB until lifecycle deletion;
- Render may suspend Free services at a limit; B2 or Neon may restrict or suspend service rather than bill when no card is present. Do not test the overage path.

Monitor usage daily during the cohort. Stop traffic before any allowance is exhausted.

### 1.4 API-docs policy — default off

API docs are development-only by default. `ENABLE_API_DOCS` unset or `None` derives off in `staging`; setting it to `false` makes the posture explicit. When disabled, `/docs`, `/redoc`, and `/openapi.json` are not mounted and must return 404.

Do not enable API docs in staging. Full schema disclosure on a public Render URL is not approved. If a future exception is requested, it requires a separate written security approval and an edge/network control; it is not part of this runbook.

### 1.5 Synthetic staging data policy

- Use only synthetic tenants, users, knowledge bases, assistants, conversations, and files.
- Use identities such as `m12.*@example.invalid` and markers such as `M13-TXT-MARKER`.
- Do not upload customer documents, production exports, personal data, regulated data, or real credentials.
- Do not restore a production database or production object store into this environment.
- Do not use real BYOK keys unless a separate approval explicitly permits a disposable tester-owned key. Prefer the `mock` provider.
- Delete synthetic test artifacts after acceptance; record the cleanup.

### 1.6 Invite-only onboarding

- `ALLOW_PUBLIC_REGISTRATION=false` is mandatory.
- There is no approved public sign-up path for testers.
- The operator provisions the first owner by an approved bootstrap method and invites named testers.
- Invitation tokens are delivered out of band, never pasted into a shared channel or committed.
- The current frontend has no `/accept-invite` route. Use the documented API acceptance path (`POST /api/v1/auth/accept-invite`) or record the cohort as blocked. Do not enable registration to work around the missing UI.
- No shared accounts, demo credentials, or tester self-service tenant creation.

### 1.7 No platform-paid fallback

- `OPENAI_API_KEY` and `OMNIROUTE_API_KEY` remain empty.
- `LLM_BASE_URL` remains empty unless a separately approved operator gateway is funded and documented; for this runbook it is empty.
- No Anthropic, Gemini, Groq, or other platform provider key is configured.
- The zero-cost chat path is the `mock` provider. A tester may use a tester-owned BYOK key only if that is separately approved; it is not a platform-paid fallback.
- `DEFAULT_EMBEDDING_PROVIDER=local`, model `local-feature-projection`, dimensions `384`; do not use a network embedding provider.

### 1.8 No card or paid plan

No payment method is approved for Render, Neon, or Backblaze B2. If a console asks for a card, billing profile, paid plan, paid trial, identity verification beyond normal sign-up, or a paid add-on, **stop**. Adding a payment method requires a separate explicit approval and is outside this runbook.

### 1.9 Approval gates

There are 10 phases (A-J) and 12 approval gates. A gate is not satisfied by reading this document; record the named approver, UTC timestamp, decision, and evidence reference.

| Gate | Phase | Decision | Required approver |
|---|---|---|---|
| A1 | A | Hosting architecture, public-URL exposure, cost envelope, docs-off, synthetic-data, invite-only, no-fallback, no-card posture | Product owner + security/risk owner + cost owner + data owner |
| B1 | B | Create Render, Neon, and B2 accounts/resources without a payment method | Account owner |
| C1 | C | Generate and escrow secrets; approve secret custody | Security owner + escrow custodian |
| D1 | D | Commit and push the exact reviewed release | Release owner + deployment owner |
| D2 | D | Sync the Render Blueprint and create the two services | Deployment owner + account owner |
| E1 | E | Confirm database identity and pgvector; accept the target | Database owner |
| E2 | E | Run `alembic upgrade head` (only if this path is chosen) | Database owner + deployment owner |
| F1 | F | Deploy the backend and accept log/health/flag verification | Deployment owner |
| G1 | G | Build and deploy the frontend with the exact backend origin | Deployment owner |
| H1 | H | Execute the synthetic 12-step B2/storage drill | Data owner + security owner |
| I1 | I | Sign manual UI acceptance | Product owner |
| J1 | J | Invite the named cohort and open synthetic testing | Product owner + security owner |

### 1.10 Named owners

Record names outside this document; do not record personal data here.

| Role | Named owner |
|---|---|
| Deployment owner | `<deployment-owner>` |
| Account owner | `<account-owner>` |
| Security/risk owner | `<security-owner>` |
| Secret-escrow custodian | `<escrow-custodian>` |
| Database owner | `<database-owner>` |
| Data owner | `<data-owner>` |
| Cost owner | `<cost-owner>` |
| Product owner | `<product-owner>` |
| Rollback approver | `<rollback-approver>` |

---

## Phase A — Approvals and release identity

**Gate A1.** Before any external action, obtain written approval for:

1. the hosting architecture and the no-paid/no-card boundary;
2. public Render URLs protected only by application auth, not network privacy;
3. the Render/Neon/B2 cost and usage envelope;
4. API docs off by default;
5. synthetic-only data;
6. invite-only onboarding;
7. no platform-paid LLM fallback.

Record the approval, approvers, UTC time, and any conditions.

### A.1 Verify the release identity

Run these read-only checks on the operator workstation. They do not deploy or mutate anything.

```powershell
Set-Location -LiteralPath "E:\MM Office\Multi-Tanant-CaaS"
git status --short
git rev-parse HEAD
git log -1 --oneline
git diff --check
```

Required outcome:

- the exact release commit is known;
- the worktree is clean, or every remaining change is explicitly excluded from the release and recorded;
- no whitespace error blocks the release;
- the deployable blueprint and application changes are in the commit, not only in the worktree.

A dirty worktree is not deployable. The M13.3 blueprint corrections and application changes must be in the reviewed commit before Phase D. If they are only uncommitted worktree content, stop at Gate D1.

### A.2 Verify the reviewed blueprint properties

Read-only checks:

```powershell
Select-String -LiteralPath "render.yaml" -Pattern "exec uvicorn|CORS_ORIGIN_REGEX|generateValue|sync: false|plan: free|databases:"
git diff -- render.yaml
```

Required outcome:

- exactly two web services: `mmaip-backend`, `mmaip-frontend`;
- both `plan: free`;
- backend Docker command contains `alembic upgrade head && exec uvicorn ... --workers 1`;
- `CORS_ORIGIN_REGEX` is `^$`, not an empty value and not a broad Vercel preview regex;
- no `databases:` block and no Render managed database;
- `autoDeploy: false` on both services;
- `ALLOW_PUBLIC_REGISTRATION=false`, `DEBUG=false`, `ENVIRONMENT=staging`;
- no secret value appears in the file.

Record the commit SHA and the reviewed diff reference. Do not proceed to Phase B from an unreviewed tree.

**Gate A1 output:** signed approval record and release SHA. No external account, secret, migration, or deployment exists yet.

---

## Phase B — External account setup

**Gate B1.** Each account and resource is an external mutation. Create it only after Gate B1 is recorded. Stop immediately if any provider requests a card, billing profile, paid plan, paid trial, or paid add-on. No payment method is approved.

### B.1 Render account and workspace

1. Create or sign in to a Render workspace on the **Free** plan.
2. Do not add a payment method.
3. Do not create Render Postgres, Redis, a persistent disk, a private service, a background worker, or a paid add-on.
4. Record the workspace ID and owner. Do not connect the repository yet; that is Phase D.
5. Confirm the account can see the repository that will be connected later.

Stop conditions: a card prompt, a paid-plan preselection, an existing billable service that cannot be separated, or an account that is not controlled by the approved owner.

### B.2 Neon PostgreSQL 16

Follow [M13 Database and Storage Setup](M13_DATABASE_AND_STORAGE_SETUP.md), Section 2, with these gates:

1. Create project `mmaip-staging`.
2. Select PostgreSQL **16** if offered. If only another major version is offered, stop and record the offered version for approval.
3. Select the Free plan and the region nearest Render `oregon`; record the exact region ID.
4. Create database `mmaip_staging` owned by role `mmaip_user`. Do not use the project owner/superuser role for the application.
5. Connect to `mmaip_staging` and run, as the database owner:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

6. Retrieve the **direct** (unpooled) connection string and, separately, the pooled string. Start with the direct host for both migration and runtime.
7. Store both connection strings in the approved secret manager. Record only the project ID, region, PostgreSQL version, database name, role name, and non-secret host label.
8. Do not print a password or a full connection string in the terminal, chat, ticket, screenshot, or this document.

Stop conditions: card/billing prompt, wrong PostgreSQL major version without approval, wrong region, an existing unknown project/database, extension creation failure, or any uncertainty about the target.

### B.3 Backblaze B2 private bucket and application key

Follow [M13 Database and Storage Setup](M13_DATABASE_AND_STORAGE_SETUP.md), Section 3, with these gates:

1. Create the B2 account only after approval. Stop if a card, billing profile, or paid plan is requested.
2. Create a **Private** bucket named `<private-bucket>` in the region nearest Render `oregon`. Record the exact region code, for example `us-west-004`.
3. Leave Object Lock disabled unless a separate retention approval exists.
4. Create a bucket-scoped application key named `mmaip-staging-app` with `listFiles`, `readFiles`, `writeFiles`, and `deleteFiles`; add `listAllBucketNames` only if the SDK requires it for a bucket-restricted key.
5. Do not grant `writeBuckets`, `deleteBuckets`, account-wide access, or a master key.
6. Configure a lifecycle rule for old versions: keep only the last version, or a separately approved retention period. Configure unfinished large-upload cleanup if the console offers it. Record the rule and retention.
7. Record the bucket name, bucket ID, region code, key ID, scope, capabilities, creation date, lifecycle rule, and rotation owner. Do not record the application key secret.

B2 versioning is always on. Deleting an object hides the current version; old versions remain and count toward the 10 GB allowance until lifecycle deletion. Versioning is not a backup.

Stop conditions: card/billing prompt, public bucket preselection, wrong region, account-wide key, inability to keep the bucket private, or no lifecycle control.

**Gate B1 output:** Render workspace, Neon project/database/role, and B2 private bucket/key exist. No service is deployed, no migration has run, and no secret value is recorded.

---

## Phase C — Secrets

**Gate C1.** Secret generation and custody require the security owner and escrow custodian. Generate values locally, in a disposable terminal, and enter them directly into the approved secret manager. Do not redirect output to a file, use `Tee-Object`/`Out-File`, or save a transcript.

### C.1 Generate independent values

Run each command only in the operator's local terminal. The output prints to that terminal; it is not to be copied into this document, chat, ticket, screenshot, commit, or repository file.

```powershell
Set-Location -LiteralPath "E:\MM Office\Multi-Tanant-CaaS"

# Run twice: use one output for SECRET_KEY and a different output for JWT_SECRET.
& "backend\.venv\Scripts\python.exe" -c "import secrets; print(secrets.token_urlsafe(64))"

# Dedicated BYOK encryption key material.
& "backend\.venv\Scripts\python.exe" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# URL-safe database password, if the provider does not supply one.
& "backend\.venv\Scripts\python.exe" -c "import secrets; print(secrets.token_urlsafe(48))"

# Record only a fingerprint; paste the secret at the hidden prompt, not into the command line.
& "backend\.venv\Scripts\python.exe" -c "import hashlib, getpass; v=getpass.getpass('Secret (hidden): '); print(hashlib.sha256(v.encode()).hexdigest())"
```

Rules:

- `SECRET_KEY` is a unique random value.
- `JWT_SECRET` is a different unique random value.
- `SECRET_ENCRYPTION_KEY` is a dedicated Fernet key and must not equal `SECRET_KEY`.
- The database password is unique and URL-safe; percent-encode only if the provider requires it.
- Record only SHA-256 fingerprints and secret-manager/escrow references.
- Clear the clipboard, close the disposable terminal, and rotate anything that may have been captured by shell history, screen recording, or a screenshot.

### C.2 Escrow the encryption key

- Store `SECRET_ENCRYPTION_KEY` in the provider secret manager **and** in a separate dual-control escrow accessible to the escrow custodian.
- Record the fingerprint and escrow reference. Never record the key.
- The application derives the active Fernet key with SHA-256 from this key material. Do not pre-derive a different key.
- If `SECRET_ENCRYPTION_KEY` is empty, the application falls back to `SECRET_KEY`; that fallback is not acceptable for staging.
- Loss of `SECRET_ENCRYPTION_KEY` makes BYOK data unrecoverable even if the database is restored. Treat escrow failure as a release-blocking incident.

### C.3 Blueprint `generateValue` reconciliation

The reviewed blueprint currently declares `generateValue: true` for `SECRET_KEY`, `JWT_SECRET`, and `SECRET_ENCRYPTION_KEY`. That is a Render convenience, not escrow.

Choose exactly one source before the first backend deploy, and record the decision at Gate D2:

1. **Preferred:** set the operator-generated values in the Render Dashboard before the first deploy. If the Dashboard does not permit replacement before first creation, allow the service to be created, replace the values immediately, and redeploy before any tester, upload, or real use.
2. **Exception:** accept the Render-generated values and escrow the exact deployed `SECRET_ENCRYPTION_KEY` with dual control before any tester.

Never leave an unescrowed generated encryption key, and never run both flows as if they were the same key. The deployed value is the only value that matters.

### C.4 `PREVIOUS_SECRET_KEYS` rotation note

- Keep `PREVIOUS_SECRET_KEYS` empty on first use.
- It is a comma-separated fallback list used for decrypting existing BYOK ciphertext, not a permanent keyring and not a JWT-session fallback.
- To rotate `SECRET_ENCRYPTION_KEY`: generate a new key; set it as `SECRET_ENCRYPTION_KEY`; move the old key material into `PREVIOUS_SECRET_KEYS` (comma-separated, no ambiguity); deploy; re-encrypt/rotate the affected rows; verify one retrieval configuration, one provider credential, and one assistant key decrypt successfully; then remove the old key from `PREVIOUS_SECRET_KEYS`.
- Keep the escrow copy of the old key until retention permits destruction.
- Rotating `JWT_SECRET` invalidates existing access and refresh tokens. Users must sign in again. Do not claim that `PREVIOUS_SECRET_KEYS` preserves sessions.
- Rotating `SECRET_KEY` alone does not replace a dedicated `SECRET_ENCRYPTION_KEY`; do not rely on it as a BYOK migration.

**Gate C1 output:** secret fingerprints and escrow references recorded; no secret value appears in the repository, document, chat, or evidence bundle. No deployment has occurred.

---

## Phase D — Render Blueprint sync

Phase D has two separate gates. **D1 is a hard prerequisite for D2.** Do not connect the repository or click Blueprint sync until the exact reviewed commit is pushed.

**Gate D1.** Separately approved commit and push.
**Gate D2.** Separately approved Blueprint sync.

### D.1 Commit and push the reviewed release first

Render reads `render.yaml` from the connected Git branch. A worktree edit, an unpushed commit, or an uncommitted secret-adjacent file is not deployable.

Before staging anything:

```powershell
Set-Location -LiteralPath "E:\MM Office\Multi-Tanant-CaaS"
git status --short
git diff --check
git diff -- render.yaml
git rev-parse HEAD
```

Confirm:

- the release contains the corrected `exec uvicorn` command and `CORS_ORIGIN_REGEX: "^$"`;
- the release contains the staging-only schema guard (`should_initialize_schema`) and docs gating;
- both services are `plan: free`, there are exactly two services, and there is no `databases:` block;
- no `.env`, secret, token, password, local database, virtual environment, or acceptance evidence is staged;
- the intended commit includes every application change the deployed image needs, not only `render.yaml`.

Only after Gate D1:

```powershell
git add "<approved-file-1>" "<approved-file-2>"
git commit -m "<approved-release-message>"
git push origin "<approved-branch>"
git rev-parse HEAD
git rev-parse "origin/<approved-branch>"
```

The two SHA values must match. Record the commit SHA. If the remote branch cannot be read or the SHA differs, stop.

A read-only YAML parse can confirm the service shape before sync:

```powershell
& "backend\.venv\Scripts\python.exe" -c "import yaml, pathlib; d=yaml.safe_load(pathlib.Path('render.yaml').read_text(encoding='utf-8')); print('services=', [(s.get('name'), s.get('runtime'), s.get('plan')) for s in d.get('services', [])]); print('databases_present=', 'databases' in d); print('has_exec=', 'exec uvicorn' in str(d))"
```

Expected: exactly `mmaip-backend` and `mmaip-frontend`, both `free`; `databases_present=False`; `has_exec=True`. If not, fix the release and repeat Gate D1; do not sync.

### D.2 Connect the repository and sync the Blueprint

Under Gate D2:

1. In Render, choose **New > Blueprint**.
2. Connect the GitHub account that can read the approved repository and branch. Grant the minimum repository access Render needs.
3. Select the repository, `<approved-branch>`, and the reviewed commit SHA. Do not select a different branch or an auto-deploying preview branch.
4. Review the detected services **before** applying the Blueprint. Required:
   - exactly two web services: `mmaip-backend` and `mmaip-frontend`;
   - both `plan: free`;
   - no managed database, Redis, private service, background worker, persistent disk, or paid add-on;
   - backend runtime Docker, frontend runtime Node;
   - `autoDeploy: false`;
   - no secret value visible in the Blueprint preview.
5. If Render detects an extra service or a database, stop. Fix the reviewed commit; do not delete existing resources without separate approval.
6. An old Render Postgres from an earlier topology may still exist. It is not part of this environment. Do not create a new one; cleanup is a separate approved action.

### D.3 Inspect and correct the Dashboard environment

`sync: false` means the Blueprint does not manage the value. Render prompts for it at creation, and later syncs do **not** overwrite it. A stale Dashboard value therefore survives silently. After the sync, open the service environment pages and inspect every value below. Correct stale values before the first backend deploy.

| Variable | Required value or placeholder | Check |
|---|---|---|
| `ENVIRONMENT` | `staging` | Must not be `development` or `production` |
| `DEBUG` | `false` | Must be false |
| `ALLOW_PUBLIC_REGISTRATION` | `false` | Invite-only; must not be true |
| `ENABLE_API_DOCS` | `false` (or unset; staging derives off) | Never `true` in staging |
| `PUBLIC_PUBLISHING_ENABLED` | `false` | Explicit or default false; public publishing disabled |
| `DEVELOPER_API_ENABLED` | `false` | Explicit or default false |
| `CUSTOM_PROVIDER_ENDPOINTS_ENABLED` | `false` | Explicit or default false |
| `DATABASE_URL` | `postgresql+asyncpg://mmaip_user:<db-password>@<neon-direct-host>:5432/mmaip_staging?ssl=require` | Direct async URL; no `sslmode`, no `channel_binding`, no pooled host, no localhost |
| `DATABASE_SYNC_URL` | `postgresql://mmaip_user:<db-password>@<neon-direct-host>:5432/mmaip_staging?sslmode=require` | Direct libpq URL; not used by online Alembic |
| `FRONTEND_URL` | `https://<frontend-host>` | Exact HTTPS origin; no trailing slash, no path, no localhost |
| `BACKEND_URL` | `https://<backend-host>` | Exact HTTPS origin; no `/api/v1`, no trailing slash, no localhost |
| `ALLOWED_ORIGINS` | empty | Do not add wildcard or unapproved origins |
| `CORS_ORIGIN_REGEX` | `^$` | Must be stored as `^$`; a missing/dropped value can restore the broad default regex |
| `S3_BUCKET_NAME` | `<private-bucket>` | Private bucket only |
| `S3_ENDPOINT_URL` | `https://s3.<b2-region-code>.backblazeb2.com` | Same region as the bucket; not an R2 endpoint |
| `S3_ACCESS_KEY_ID` | `<b2-key-id>` | Bucket-scoped key only |
| `S3_SECRET_ACCESS_KEY` | `<b2-application-key>` | Secret; never display, log, or record |
| `S3_REGION_NAME` | `<b2-region-code>` | Actual B2 region, e.g. `us-west-004`; never `auto` or `us-east-1` unless that is the bucket region |
| `TRUSTED_PROXY_IPS` | empty until measured | Do not guess; a wrong value enables spoofing; empty collapses per-IP buckets behind Render's proxy |
| `LLM_BASE_URL` | empty | No platform gateway in this runbook |
| `OPENAI_API_KEY` | empty | No platform-paid fallback |
| `OMNIROUTE_API_KEY` | empty | No platform-paid fallback |
| `NEXT_PUBLIC_API_BASE_URL` | `https://<backend-host>` | Backend origin only; no `/api/v1`, no trailing slash; inlined at frontend build time |
| `STORAGE_BACKEND` | `s3` | Do not use `local`; Render's filesystem is ephemeral |
| `DEFAULT_VECTOR_STORE` | `pgvector` | Qdrant is not deployed |
| `DEFAULT_EMBEDDING_PROVIDER` | `local` | Zero-download local provider |
| `DEFAULT_EMBEDDING_MODEL` | `local-feature-projection` | Must match the local provider |
| `DEFAULT_EMBEDDING_DIMENSIONS` | `384` | Must match the local provider and stored vectors |
| `RATE_LIMIT_ENABLED` | `true` | Do not disable |
| `INGESTION_INLINE_DISPATCHER_ENABLED` | `true` | Single-process envelope |
| `INGESTION_DISPATCHER_POLL_SECONDS` | `3600` | Avoid idle Neon wakeups |
| `INGESTION_LEASE_SECONDS` | `3600` | Must exceed the longest expected job |
| `INGESTION_MAX_CONCURRENCY` | `1` | Keep one job at a time |

Correction rules:

- **Neon URLs:** re-open the Dashboard after every sync. `sync: false` preserves stale values. Correct both URLs if the host, database, role, pool mode, or TLS parameter changed.
- **Origins:** use the actual Render hostnames, not provisional or localhost values. A backend that sees a localhost frontend origin in `staging` fails closed.
- **B2 region and keys:** a stale region or a key from another bucket produces SigV4 or 403 failures. Correct the region code and re-enter the scoped key if it was rotated.
- **`TRUSTED_PROXY_IPS`:** leave empty until measured with two client addresses. Do not set a guessed Render edge address.
- **`LLM_BASE_URL`:** empty for this runbook. If someone proposes an operator gateway, it needs a separate approval and a budget; do not silently point at a paid endpoint.
- **`CORS_ORIGIN_REGEX`:** verify it is actually stored as `^$`. If Render drops it or stores an empty string, set it again and restart the backend; otherwise the code default broad Vercel preview regex can return.
- **Secrets:** resolve the C.3 source decision now. Do not deploy with an unescrowed encryption key.

Do not click **Deploy** until all rows are checked and the service list is exactly the approved topology. Record a snapshot of variable names and non-secret values; never record secret values.

**Gate D2 output:** exactly two Free web services, no managed database, no paid add-on, and a corrected environment. A service may exist but must not be considered deployed or accepted.

---

## Phase E — Database identity, pgvector, and migration

Phase E precedes the first backend deploy. `/health` can only be checked after a backend is running; if a backend is already live (for example during a redeploy), use the health commands at the end of this phase. Otherwise the authoritative health check is Phase F.

**Gate E1.** Confirm the database identity.
**Gate E2.** Run `alembic upgrade head` only with explicit approval.

### E.1 Set the direct Neon URLs for the operator session

Use single-quoted PowerShell strings so a `$` in a password is not interpolated. Do not print the URL.

```powershell
Set-Location -LiteralPath "E:\MM Office\Multi-Tanant-CaaS\backend"

$env:DATABASE_URL = 'postgresql+asyncpg://mmaip_user:<db-password>@<neon-direct-host>:5432/mmaip_staging?ssl=require'
$env:DATABASE_SYNC_URL = 'postgresql://mmaip_user:<db-password>@<neon-direct-host>:5432/mmaip_staging?sslmode=require'
```

Print the parsed target without the password and inspect the query keys:

```powershell
& ".venv\Scripts\python.exe" -c "from sqlalchemy.engine.url import make_url; import os; u=make_url(os.environ['DATABASE_URL']); print(f'host={u.host} port={u.port} db={u.database} user={u.username}'); print('scheme=', u.drivername); print('query_keys=', sorted(u.query.keys()))"

& ".venv\Scripts\python.exe" -c "from sqlalchemy.engine.url import make_url; import os; u=make_url(os.environ['DATABASE_SYNC_URL']); print(f'host={u.host} port={u.port} db={u.database} user={u.username}'); print('scheme=', u.drivername); print('query_keys=', sorted(u.query.keys()))"
```

Expected:

- async scheme `postgresql+asyncpg`, query keys exactly `['ssl']`;
- sync scheme `postgresql`, query keys exactly `['sslmode']`;
- host is the Neon **direct** host, not a `-pooler` host;
- database `mmaip_staging`, user `mmaip_user`, port `5432`.

If `sslmode`, `channel_binding`, `connect_timeout`, or any other libpq-only parameter appears in `DATABASE_URL`, stop. asyncpg treats those as connect keywords and fails. Do not disable TLS or certificate verification.

### E.2 Confirm database identity with SQL

Use `psql` or the Neon SQL Editor connected to the direct host as `mmaip_user`. Do not put the password in the process list or shell history.

```sql
SELECT current_database(), current_user, inet_server_addr(), inet_server_port();
SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid();
SHOW server_version;
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
SELECT count(*) AS public_tables FROM pg_tables WHERE schemaname = 'public';
SELECT count(*) AS non_alembic_public_tables
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename <> 'alembic_version';
```

Expected on a fresh staging database:

| Check | Expected |
|---|---|
| `current_database()` | `mmaip_staging` |
| `current_user` | `mmaip_user` |
| `inet_server_addr()` / port | The approved Neon endpoint / `5432`; not a production or unknown host |
| `pg_stat_ssl.ssl` | `t` |
| `server_version` | `16.x`, or the approved alternative recorded at creation |
| `vector` extension | One row: `vector` |
| `public_tables` | `0`, or `1` if only `alembic_version` exists from a prior attempt |
| `non_alembic_public_tables` | `0` |

If `non_alembic_public_tables` is not zero, stop. Determine whether this is a reused or wrong database. Do not run migrations over an unknown schema.

**Gate E1 output:** parsed target and SQL identity match the approved Neon project; pgvector exists; no unexpected tables. Record the host label without the password.

### E.3 Run the migration only after Gate E2

Preconditions for `alembic upgrade head`:

- Gate E1 passed;
- `alembic current` shows no revision, or an explicitly expected staging baseline;
- `non_alembic_public_tables` is `0`;
- `vector` exists;
- exactly one migration owner is operating;
- the Render backend is not starting its own `alembic upgrade head` at the same time.

The Render Docker command also runs `alembic upgrade head` on every container start. Choose one first-cut path: operator-run migration in Phase E, or container-start migration in Phase F. If you run Phase E, finish it before triggering the backend; the container's later run is an idempotent no-op. Never run both concurrently.

```powershell
& ".venv\Scripts\python.exe" -m alembic current
& ".venv\Scripts\python.exe" -m alembic heads
& ".venv\Scripts\python.exe" -m alembic upgrade head
& ".venv\Scripts\python.exe" -m alembic current
```

Required outcome:

- `alembic heads` shows exactly one head: `0010_m10_remediation_schema_alignment`;
- `alembic current` after the upgrade shows `0010_m10_remediation_schema_alignment (head)`;
- the command exits successfully.

Post-migration SQL:

```sql
SELECT version_num FROM alembic_version;
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
SELECT count(*) AS public_tables FROM pg_tables WHERE schemaname = 'public';
```

Expected `version_num` is `0010_m10_remediation_schema_alignment`. Record the actual public table count rather than asserting a count from another release.

If the migration fails:

1. Do not rerun blindly.
2. Capture the error with credentials redacted.
3. Query `SELECT version_num FROM alembic_version;` if the table exists.
4. Determine whether failure occurred before or after partial DDL.
5. Preserve the failure state. Do not run `alembic downgrade`, `DROP DATABASE`, `DROP TABLE`, or a destructive reset. Escalate.

### E.4 Health checks

Only if a backend is already running:

```powershell
$env:BACKEND_URL = "https://<backend-host>"

$health = Invoke-WebRequest -UseBasicParsing -Uri "$($env:BACKEND_URL)/health" -Method Get
"HEALTH_HTTP=$($health.StatusCode)"
$health.Content
```

```powershell
$ready = Invoke-WebRequest -UseBasicParsing -Uri "$($env:BACKEND_URL)/ready" -Method Get
"READY_HTTP=$($ready.StatusCode)"
$ready.Content
```

Expected: `/health` 200 with `status=healthy`; `/ready` 200 with `status=ready` and `database=connected`.

`/ready` performs a real database round trip and can wake Neon. Call it sparingly, not on a schedule. On a cold start, one 503 followed by a successful retry is acceptable; a persistent 503 is a failure. Do not poll `/ready`.

**Gate E2 output:** migration head `0010` confirmed and pgvector present, or the migration was deliberately deferred to the container-start path in Phase F. No destructive rollback has been run.

---

## Phase F — Backend deployment and verification

**Gate F1.** Deploy the backend only after Phase D environment checks and Phase E database identity (or the deliberate container-start migration decision) are recorded.

### F.1 Deploy

1. Confirm `autoDeploy: false`; trigger a manual deploy of the reviewed commit.
2. Do not change the plan, add a disk, add a database, or add a paid add-on.
3. Render Free may restart or spin down at any time. A cold start reruns the container command, including the idempotent Alembic step.
4. Watch the build and start logs in Render. Do not declare success from a green build alone.

### F.2 Log sequence and secret hygiene

Required log evidence:

- Alembic output appears before Uvicorn, for example `Running upgrade` or an idempotent no-op;
- Uvicorn starts with `Uvicorn running on http://0.0.0.0:<port>` and `Application startup complete`;
- no literal `$PORT` text appears;
- the deployed command or Blueprint line contains `alembic upgrade head && exec uvicorn ... --workers 1`;
- no traceback exposes a DSN, password, token, key, or full connection string;
- no log line prints `DATABASE_URL`, `DATABASE_SYNC_URL`, `SECRET_KEY`, `JWT_SECRET`, `SECRET_ENCRYPTION_KEY`, `S3_SECRET_ACCESS_KEY`, or a B2 application key.

`exec` matters: Uvicorn replaces the shell, receives Render's termination signal, and runs the FastAPI lifespan shutdown (dispatcher stop, up to 30 seconds of drain, cancellation, engine disposal). Free has no shell to inspect PID 1, so record the Blueprint line and observe a graceful redeploy/stop.

If a secret appears in logs, stop immediately, preserve the redacted evidence, rotate the exposed value, and escalate as a security incident. Do not paste the secret into the incident record.

### F.3 Health and readiness

```powershell
$env:BACKEND_URL = "https://<backend-host>"

$health = Invoke-WebRequest -UseBasicParsing -Uri "$($env:BACKEND_URL)/health" -Method Get
"HEALTH_HTTP=$($health.StatusCode)"
$health.Content
```

```powershell
$ready = Invoke-WebRequest -UseBasicParsing -Uri "$($env:BACKEND_URL)/ready" -Method Get
"READY_HTTP=$($ready.StatusCode)"
$ready.Content
```

Expected:

- `/health` 200, `status=healthy`;
- `/ready` 200, `status=ready`, `database=connected`.

`/health` proves only that the process is alive; it does not prove database or storage. `/ready` proves only PostgreSQL connectivity; it does not prove migrations, storage, or provider reachability. Call `/ready` sparingly; do not add a poller.

### F.4 Storage private check

- In the B2 console, confirm the bucket is **Private**, not Public.
- Confirm the application key is bucket-scoped and has only the approved capabilities.
- Confirm the lifecycle rule for old versions and unfinished large uploads is present.
- Confirm no public bucket URL or public object URL is used in the application.
- Do not make the bucket public to debug a failure. Do not broaden the key.

The full storage behavior is validated in Phase H; Phase F only confirms the configuration is private and scoped.

### F.5 Feature flags, docs, and public surfaces

Verify the effective environment values. If a value is absent and the code default is safe, prefer setting it explicitly to `false` for auditability.

| Setting | Required effective value |
|---|---|
| `PUBLIC_PUBLISHING_ENABLED` | `false` |
| `DEVELOPER_API_ENABLED` | `false` |
| `CUSTOM_PROVIDER_ENDPOINTS_ENABLED` | `false` |
| `ALLOW_PUBLIC_REGISTRATION` | `false` |
| `ENABLE_API_DOCS` | `false` (or unset; staging derives off) |
| `DEBUG` | `false` |
| `ENVIRONMENT` | `staging` |
| `STORAGE_BACKEND` | `s3` |

#### F.5.1 API docs must be absent

```powershell
foreach ($path in @("/docs", "/redoc", "/openapi.json")) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "$($env:BACKEND_URL)$path" -Method Get
    "$path HTTP=$($response.StatusCode)"
  } catch {
    "$path HTTP=$([int]$_.Exception.Response.StatusCode)"
  }
}
```

Expected: every path returns 404. A 200 is a failure. Do not enable docs to "verify" the API; use the application and tests.

#### F.5.2 Registration must be denied

```powershell
$registrationBody = '{"email":"synthetic-blocked@example.invalid","password":"<synthetic-password>","full_name":"Synthetic Blocked"}'
try {
  $registration = Invoke-WebRequest -UseBasicParsing -Method Post `
    -Uri "$($env:BACKEND_URL)/api/v1/auth/register" `
    -ContentType "application/json" `
    -Body $registrationBody
  "REGISTER_HTTP=$($registration.StatusCode)"
} catch {
  "REGISTER_HTTP=$([int]$_.Exception.Response.StatusCode)"
}
```

Expected: 403. A 201 or any created account is a stop condition. Do not use a real email or real password.

#### F.5.3 Publishing, developer API, and custom endpoints

- Attempting to publish a synthetic assistant must return 403 with a message that public publishing is disabled. Do not enable the flag to make a test pass.
- Attempting to create a developer API key must return 403 with a message that the developer API is disabled.
- Attempting to create a provider credential with a non-official `base_url` must be rejected because custom provider endpoints are disabled. Do not test loopback, RFC1918, link-local, metadata, or internal hosts.
- Confirm no active public publication and no active developer key in the fresh staging database:

```sql
SELECT count(*) AS active_public_publications
FROM assistant_publications
WHERE UPPER(visibility) = 'PUBLIC' AND is_active = true;

SELECT count(*) AS active_api_keys
FROM api_keys
WHERE is_active = true;
```

Expected: `0` and `0`. A non-zero value is a stop condition; investigate before inviting anyone.

### F.6 No platform-paid fallback

- Confirm `OPENAI_API_KEY` and `OMNIROUTE_API_KEY` are empty.
- Confirm `LLM_BASE_URL` is empty.
- Confirm `DEFAULT_EMBEDDING_PROVIDER=local`.
- A mock-provider chat is the only zero-cost LLM path in this runbook.
- If a tester-owned BYOK key is separately approved, it must be the tester's key, scoped to that tester's tenant, and never treated as a platform fallback.

**Gate F1 output:** backend logs show Alembic before Uvicorn with `exec` in the deployed command; `/health` is 200; no secret appears in logs; bucket is private; docs return 404; registration, publishing, developer API, and custom endpoints are disabled. Record evidence; do not infer success from a deploy status alone.

---

## Phase G — Frontend deployment and CORS

**Gate G1.** Build and deploy the frontend only after the backend origin is final and the backend CORS values are corrected.

### G.1 Set the API base before the build

Set `NEXT_PUBLIC_API_BASE_URL` to the **backend origin only**:

```text
https://<backend-host>
```

Rules:

- no `/api/v1` suffix;
- no trailing slash;
- no `localhost`, `127.0.0.1`, LAN address, or placeholder host;
- use the final assigned Render hostname, not a provisional one;
- do not set a conflicting `NEXT_PUBLIC_API_URL`; the canonical value is `NEXT_PUBLIC_API_BASE_URL`;
- changing this value requires a **rebuild**, not only a restart, because Next inlines it at build time.

### G.2 Build and deploy

1. Trigger a manual frontend deploy of the reviewed commit.
2. The build runs `npm ci && npm run build`; `npm ci` requires the committed `frontend/package-lock.json`.
3. The start command is `npm run start -- -p $PORT`.
4. Open `https://<frontend-host>/login`. The frontend health check uses `/login`; it does not prove API connectivity.
5. In the browser network panel, confirm API requests target exactly `https://<backend-host>/api/v1/...`, with no doubled `/api/v1/api/v1`.

### G.3 Exact CORS and origins

Correct the backend environment:

| Variable | Required value |
|---|---|
| `FRONTEND_URL` | `https://<frontend-host>` |
| `BACKEND_URL` | `https://<backend-host>` |
| `ALLOWED_ORIGINS` | empty |
| `CORS_ORIGIN_REGEX` | `^$` |

Rules:

- no `http://localhost`, `http://127.0.0.1`, LAN origin, wildcard, or broad Vercel preview regex;
- no trailing slash or path in either origin;
- `CORS_ORIGIN_REGEX=^$` matches only the empty string, which a browser never sends as `Origin`;
- exact origins come only from `FRONTEND_URL` and `ALLOWED_ORIGINS`;
- changing CORS requires a backend restart/redeploy, because the middleware policy is built at application creation.

Run a preflight from the exact frontend origin:

```powershell
$env:FRONTEND_URL = "https://<frontend-host>"
$env:BACKEND_URL = "https://<backend-host>"

$preflight = Invoke-WebRequest -UseBasicParsing -Method Options `
  -Uri "$($env:BACKEND_URL)/api/v1/auth/login" `
  -Headers @{
    Origin = $env:FRONTEND_URL
    "Access-Control-Request-Method" = "POST"
    "Access-Control-Request-Headers" = "content-type"
  }

"PREFLIGHT_HTTP=$($preflight.StatusCode)"
"ACAO=$($preflight.Headers['Access-Control-Allow-Origin'])"
```

Expected: `ACAO` equals `https://<frontend-host>`.

Negative checks:

```powershell
foreach ($origin in @("http://localhost:3000", "https://unlisted.example.invalid")) {
  try {
    $negative = Invoke-WebRequest -UseBasicParsing -Method Options `
      -Uri "$($env:BACKEND_URL)/api/v1/auth/login" `
      -Headers @{
        Origin = $origin
        "Access-Control-Request-Method" = "POST"
        "Access-Control-Request-Headers" = "content-type"
      }
    "$origin HTTP=$($negative.StatusCode) ACAO=$($negative.Headers['Access-Control-Allow-Origin'])"
  } catch {
    "$origin HTTP=$([int]$_.Exception.Response.StatusCode)"
  }
}
```

Expected: no `Access-Control-Allow-Origin` for either origin. A 200 without the header is still blocked by the browser; any ACAO for localhost or an unlisted origin is a failure. If PowerShell restricts the `Origin` header, use `curl.exe -sS -i -X OPTIONS ...` with the same headers and record the raw response.

### G.4 Login and invite-only verification

1. `/login` loads; no demo credentials, seeded password, or default account are shown.
2. A valid operator-provisioned owner can sign in and see the workspace.
3. A wrong password shows an inline error and stores no token.
4. `POST /api/v1/auth/register` returns 403, as checked in Phase F.
5. Invitations are issued only by the operator to named testers; invitation tokens are delivered out of band.
6. The current frontend has no `/accept-invite` page. Use `POST /api/v1/auth/accept-invite` with the token and a synthetic password, or record the cohort as blocked. Do not enable registration.

Reuse the Phase F `/health` and `/ready` commands if a final backend check is needed. Do not poll `/ready`.

**Gate G1 output:** `/login` loads; browser API calls target the exact backend origin with one `/api/v1`; exact-origin preflight passes; localhost and unlisted origins receive no ACAO; registration is denied; only invite-based onboarding is used.

---

## Phase H — Synthetic storage validation (B2 12-step plan)

**Gate H1.** Execute the synthetic storage drill only after the backend, bucket, and database are configured. No real data may be uploaded until Steps 1-12 pass and the evidence is signed.

### H.1 Source plan and B2 specifics

Execute the 12-step plan in [M12 Storage Validation Runbook](../m12/M12_STORAGE_VALIDATION_RUNBOOK.md), using the B2 private-bucket configuration in [M13 Database and Storage Setup](M13_DATABASE_AND_STORAGE_SETUP.md), Section 3.

The 12 steps are:

| Step | Required synthetic check |
|---:|---|
| 1 | Create or designate the private test bucket; verify reachability and listing |
| 2 | Upload synthetic documents through the application/API |
| 3 | Verify the tenant-prefixed object exists in B2 |
| 4 | Download the object and compare SHA-256 |
| 5 | Verify the tenant-scoped key and listing |
| 6 | Delete one document through the API and verify object removal from the current view |
| 7 | Simulate a failed deletion and prove there is no false success |
| 8 | Verify B2 versioning and object versions |
| 9 | Take a paired database and object backup with a manifest |
| 10 | Restore into an isolated database and bucket/prefix |
| 11 | Verify restored metadata and object checksums |
| 12 | Verify cross-tenant authorization denial through the application |

B2-specific cautions:

- the bucket must remain **Private**;
- versioning is always on; deleting an object hides the current version, and old bytes remain until lifecycle deletion;
- all versions count toward the 10 GB allowance;
- lifecycle deletion is permanent and is not a backup;
- use a separate backup bucket/prefix for Step 9; do not use the live bucket as its only backup;
- keep the application key bucket-scoped; do not broaden it or make the bucket public to make a step pass;
- use only synthetic files and synthetic tenants;
- do not upload real or customer data before all steps pass.

### H.2 Reconciliation — dry-run only, never `--fix`

A reconciliation dry run may be used after the storage steps. It reports only; it must not modify rows or objects.

Preflight the target without printing the password:

```powershell
Set-Location -LiteralPath "E:\MM Office\Multi-Tanant-CaaS\backend"
& ".venv\Scripts\python.exe" -c "from sqlalchemy.engine.url import make_url; import os; u=make_url(os.environ['DATABASE_URL']); print(f'host={u.host} port={u.port} db={u.database}')"
```

Confirm the host/database are the staging Neon target, not local or production. Then run, scoped to a synthetic tenant:

```powershell
& ".venv\Scripts\python.exe" -m app.commands.reconcile_storage --dry-run --tenant "<tenant-uuid>"
```

Rules:

- `--dry-run` only.
- **Never use `--fix`** during this runbook.
- Do not use `--delete-orphans`; it is meaningless without `--fix`, and this runbook does not authorize mutation.
- Do not run reconciliation while credentials, endpoint, region, or connectivity are in doubt. The S3 `exists()` path can mask an access/network error as "missing"; a mutation could mass-mark healthy documents as failed.
- Record only the report summary and redacted findings, never object contents or credentials.

### H.3 Pass criteria and failure handling

The storage drill passes only when:

- Steps 1-12 have been executed in order with synthetic data;
- the bucket is private and the key is bucket-scoped;
- object keys use the tenant-prefixed layout;
- SHA-256 matches for uploaded and restored objects;
- deletion from the API removes the current object view, and version/lifecycle behavior is recorded honestly;
- the isolated restore verifies metadata and checksums;
- cross-tenant application access returns 403/404 and never exposes Tenant B data;
- the reconciliation dry run completes with no mutation;
- the evidence bundle contains no secrets or real data.

On failure: stop, keep the environment private, do not run `--fix`, do not make the bucket public, do not broaden the key, and escalate to the data and security owners. A failed synthetic drill blocks the cohort.

**Gate H1 output:** signed 12-step evidence, private-bucket verification, checksum/versioning/restore evidence, cross-tenant denial evidence, and a dry-run-only reconciliation report. No real data exists in the environment.

---

## Phase I — Manual UI acceptance

**Gate I1.** Manual UI acceptance is an operator activity. The agent must not drive a browser, Playwright, Selenium, or any automation against staging. The operator clicks through the checklist and records what actually happened.

### I.1 Checklist and scope

Use [M12 Manual UI Acceptance Checklist](../m12/M12_MANUAL_UI_ACCEPTANCE_CHECKLIST.md). It contains 13 areas and 69 sub-checks. Do not mark an area PASS from source inspection, screenshots supplied by someone else, or a successful API call.

Run acceptance against the synthetic staging environment with operator-provisioned accounts. Do not enable public registration, public publishing, developer API, or custom provider endpoints to make a check pass.

Known expected gaps that must be recorded honestly:

- **Area 2, UI-02.3:** there is no frontend `/accept-invite` route. Record `BLOCKED` for the UI path and use the API acceptance path, or record the cohort as blocked. Do not enable registration.
- **Area 4.10:** image document parsing is not implemented. Record the expected `FAIL`/`BLOCKED`; do not substitute a scanned PDF.
- **Public publishing success paths:** `/p/{id}` and embed success are out of scope while publishing is disabled. Record `BLOCKED/WAIVED`; do not create a PUBLIC publication.
- Source-risk checks (session handling, silent wizard errors, error-state masking, responsive layout) may fail. Record the actual behavior; do not explain it away.

### I.2 Result values and evidence

Each check is `PASS`, `FAIL`, `BLOCKED`, or `PENDING`.

- `PASS`: all sub-checks in the area pass.
- `FAIL`: at least one sub-check fails.
- `BLOCKED`: environment, seed, or missing capability prevented execution. `BLOCKED` is not a pass.
- `PENDING`: not executed.

Evidence rules:

- Name files as `M13_UI-XX.Y_<slug>.png` or `.mp4`.
- Show the URL and tenant context.
- Crop or redact tokens, keys, passwords, invitation tokens, personal data, and object keys.
- Store evidence outside the repository unless an approved artifact location exists.
- Do not record a secret in a screenshot, console log, or network capture.

### I.3 Sign-off

| Item | Result |
|---|---|
| Areas passed / failed / blocked | `___ / ___ / ___` |
| Critical failures or stop conditions | `___` |
| Evidence reference | `___` |
| Product owner | `<product-owner>` |
| UTC timestamp | `___` |

**Gate I1 output:** signed manual acceptance, or a written waiver limited to the closed synthetic cohort. A critical cross-tenant, secret-exposure, auth-bypass, or public-exposure failure blocks Phase J.

---

## Phase J — Invite-only synthetic cohort

**Gate J1.** Open the cohort only after Phase H and Phase I pass, or after a written waiver limited to the closed synthetic cohort.

### J.1 Named testers

Record names and contact details outside this document. The table below is a template; use synthetic identities only.

| Tester | Synthetic email | Tenant / role | Invite date | Accepted | Removed |
|---|---|---|---|---|---|
| `<tester-1>` | `<tester-email-1>` | Tenant A / `employee` or `viewer` | `___` | `___` | `___` |
| `<tester-2>` | `<tester-email-2>` | Tenant B / `employee` or `viewer` | `___` | `___` | `___` |

Rules:

- Invite named testers only; no public link, open registration, or shared account.
- Deliver invitation tokens out of band; never post them in a shared channel.
- Testers must not hold `TENANT_UPDATE` or any admin role unless separately approved.
- Testers must not configure custom `base_url` values or private/loopback endpoints.
- Testers must not create public publications or developer API keys.
- Use synthetic data only. No customer, production, personal, regulated, or real credential data.

### J.2 Onboarding path

1. Operator provisions the owner and tenants by the approved bootstrap method.
2. Operator invites each tester from `/dashboard/employees` or the members API.
3. Because the frontend has no `/accept-invite` page, the operator delivers the token out of band and the tester accepts through `POST /api/v1/auth/accept-invite` with a synthetic password, or the cohort is recorded as blocked.
4. Confirm the tester can sign in and sees only the assigned tenant.
5. Confirm a tester cannot access an unassigned tenant, publish publicly, create a developer key, or configure a custom endpoint.
6. Remove or disable testers at the end of the cohort.

### J.3 Keep the closed posture

Before and during the cohort, verify:

- `ALLOW_PUBLIC_REGISTRATION=false`; `POST /api/v1/auth/register` returns 403;
- `PUBLIC_PUBLISHING_ENABLED=false`; no active PUBLIC publication;
- `DEVELOPER_API_ENABLED=false`; no active developer key;
- `CUSTOM_PROVIDER_ENDPOINTS_ENABLED=false`;
- `ENABLE_API_DOCS=false`; `/docs`, `/redoc`, `/openapi.json` return 404;
- `OPENAI_API_KEY` and `OMNIROUTE_API_KEY` are empty;
- `LLM_BASE_URL` is empty;
- the bucket remains private;
- exact CORS only; no localhost or unlisted origin receives ACAO;
- no card or paid plan was added.

Do not enable a feature to unblock a tester. If a tester needs a capability that is disabled, record the request and defer it to a separately approved change.

### J.4 Monitor usage, cost, logs, and access

Monitor at least daily while the cohort is open, and after any long test session:

| Area | What to check | Threshold / action |
|---|---|---|
| Render | Workspace Free instance-hours, bandwidth, build minutes; service restarts; 5xx and OOM logs | Warn at 80% of 750 hours or 5 GB bandwidth; stop traffic before exhaustion. No card, no paid upgrade. |
| Neon | CU-hours, storage, egress, connection errors, compute suspension | Warn at 80% of 100 CU-hours, 1 GB storage, or 5 GB egress; stop traffic and investigate. |
| Backblaze B2 | Storage including all versions, egress, Class D calls, lifecycle state | Warn at 80% of 10 GB; keep synthetic dataset and versions small; no public bucket. |
| Application logs | 5xx, tracebacks, migration errors, auth failures, cross-tenant 403/404 patterns, secret-like strings | Stop on any secret exposure, cross-tenant success, or repeated 5xx. |
| Access | Tester list, active sessions, active API keys, publications | Remove departed testers; expected active developer keys = 0; expected active PUBLIC publications = 0. |
| Health | `/health` only for liveness; `/ready` sparingly, never on a schedule | Persistent `/ready` 503 is a failure; do not poll. |

Do not use `/ready` as an uptime monitor. Each call performs a database round trip and can wake Neon.

### J.5 Stop conditions and immediate actions

Stop the cohort immediately if any of the following occurs:

- a provider asks for a card, payment method, paid plan, or paid add-on;
- Render, Neon, or B2 approaches or exceeds its approved allowance;
- `/docs`, `/redoc`, or `/openapi.json` returns 200;
- registration succeeds, or a public publication or developer key becomes active;
- publishing, developer API, or custom provider endpoints are enabled without approval;
- a platform-paid LLM call occurs, or a platform provider key is present;
- any cross-tenant data is returned, any auth bypass occurs, or a tester accesses an unassigned tenant;
- a secret appears in a log, response, audit payload, screenshot, or evidence bundle;
- the bucket becomes public, the key scope is broadened, or real data appears;
- the migration head changes unexpectedly, or a destructive database action is proposed;
- cost, traffic, or error rate is anomalous, or monitoring is lost.

Immediate actions:

1. Stop inviting and disable tester access.
2. Preserve logs and evidence with secrets redacted.
3. Revoke exposed tokens/keys and rotate affected secrets.
4. Keep the bucket private; do not delete data or run destructive migrations.
5. Notify the deployment owner, security/risk owner, and account owner.
6. Record the timeline, affected scope, and decision.
7. Do not add a card or upgrade a plan to resolve the incident.

**Gate J1 output:** named testers, signed closed-posture checks, daily usage/log records, and a stop/close record. No real data or paid fallback was introduced.

---

## Rollback, stop, and escalation

### R.1 Principles

- Prefer rollback/redeploy over destructive repair.
- Preserve failure state before changing anything.
- Do not run destructive Alembic down-migrations, `DROP DATABASE`, `DROP TABLE`, `TRUNCATE`, or a restore over a live database without explicit approval.
- Reverting application code does not revert the schema or B2 objects. Verify compatibility before redeploying an older build.
- A rollback does not restore secrets, environment overrides, or deleted object versions automatically.

### R.2 Backend rollback

1. Identify the previous successful Render deploy or the previous reviewed commit SHA.
2. Use Render's deploy history to roll back/redeploy the previous commit. Do not use `autoDeploy` to bypass review.
3. Re-check `/health` after the rollback. Check `/ready` once if database compatibility is in question.
4. Compare the environment with the failed deployment; rollback does not revert Dashboard variables.
5. If the previous code expects an older schema, do not point it at a newer schema without verification. Escalate to the database owner.

### R.3 Frontend rollback

1. Roll back to the previous successful frontend deploy/commit.
2. If `NEXT_PUBLIC_API_BASE_URL` changed, rebuild; a restart does not replace the inlined value.
3. Verify `/login` loads and browser requests target the exact backend origin with one `/api/v1`.
4. Re-check CORS from the exact frontend origin and confirm localhost/unlisted origins receive no ACAO.

### R.4 Database rollback and snapshots

- Do not run `alembic downgrade` as a release rollback. The downgrade path is not the release gate and can drop columns or data.
- Before the first migration, record the Neon restore window and any manual snapshot. Neon Free provides up to 6-hour instant restore limited to 1 GB of changes and one manual snapshot; confirm what is actually available before relying on it.
- If a migration fails partway, preserve the failure state. Restore into a new Neon branch or isolated database, verify the schema and data, then repoint the application after approval.
- Do not restore over the live database without explicit approval. Do not drop the database to "start over."
- After any restore, verify `alembic_version` is `0010_m10_remediation_schema_alignment` (or the approved release head), pgvector exists, and `/ready` succeeds. Do not treat a successful restore as proof of storage consistency.
- Record the restore point, branch/snapshot ID, timestamp, operator, and verification result.

### R.5 Object storage rollback and lifecycle caution

- B2 versioning is always on. Deleting the current object hides it; older versions remain until lifecycle deletion.
- Lifecycle deletion is permanent. Do not shorten retention during an incident without approval.
- Do not treat versioning or lifecycle as a backup. Use the separate backup bucket/prefix and paired manifest from the M12 storage runbook.
- Restore into an isolated bucket/prefix first; verify keys, metadata, and SHA-256 before any cutover.
- Never make the bucket public, broaden the application key, or disable lifecycle controls to recover data.
- All versions count toward the 10 GB allowance; a restore can temporarily increase usage.

### R.6 Secret rollback and rotation

- If a secret is exposed, rotate it; do not simply restore the old value.
- `SECRET_ENCRYPTION_KEY`: restore from escrow only if the key is not compromised and the escrow integrity is confirmed. A lost key makes BYOK data unrecoverable.
- `JWT_SECRET`: rotation invalidates existing access/refresh tokens; communicate re-login.
- `SECRET_KEY`: rotate independently; do not rely on it as a replacement for a dedicated encryption key.
- `PREVIOUS_SECRET_KEYS`: keep only rotation-era keys, remove after re-encryption and verification, and retain the escrow copy until retention permits destruction.
- Update the deployed environment, redeploy, and verify one BYOK decrypt and one login path.
- Record fingerprints and rotation timestamps, never values.

### R.7 Escalation

Escalate immediately to:

- `<security-owner>` for secret exposure, cross-tenant access, auth bypass, public bucket, or docs exposure;
- `<deployment-owner>` for failed deploys, rollback coordination, or environment drift;
- `<database-owner>` for migration failure, identity mismatch, or restore;
- `<account-owner>` for provider suspension, billing prompts, or account compromise;
- `<cost-owner>` for allowance exhaustion or anomalous usage;
- `<rollback-approver>` before any destructive or irreversible action.

If a provider asks for a card or paid plan during an incident, stop and escalate. Do not add payment details to restore service.

---

## Evidence ledger

Use one row per gate/check. Do not record secret values.

| Gate / check | Expected | Observed | Result | Evidence reference | Reviewer | UTC |
|---|---|---|---|---|---|---|
| A1 release identity | Reviewed commit; clean/excluded tree |  |  |  |  |  |
| D1 commit/push | Local and remote SHA match |  |  |  |  |  |
| D2 Blueprint sync | 2 Free web services; no DB |  |  |  |  |  |
| D2 environment | All sync:false values corrected |  |  |  |  |  |
| E1 database identity | `mmaip_staging` / `mmaip_user` / direct host |  |  |  |  |  |
| E1 pgvector | `vector` present |  |  |  |  |  |
| E2 migration | Head `0010_m10_remediation_schema_alignment` |  |  |  |  |  |
| F1 logs | Alembic then Uvicorn; `exec`; no secrets |  |  |  |  |  |
| F1 `/health` | 200, `healthy` |  |  |  |  |  |
| F1 `/ready` | 200, `connected` (sparingly) |  |  |  |  |  |
| F1 docs | 404 on `/docs`, `/redoc`, `/openapi.json` |  |  |  |  |  |
| F1 registration | 403 |  |  |  |  |  |
| F1 flags/publications | Flags false; 0 active PUBLIC publications; 0 active developer keys |  |  |  |  |  |
| G1 frontend | `/login` 200; exact backend origin |  |  |  |  |  |
| G1 CORS | Exact origin ACAO; localhost/unlisted no ACAO |  |  |  |  |  |
| H1 storage | 12 steps pass; private bucket; dry run only |  |  |  |  |  |
| I1 UI acceptance | Signed 13-area checklist |  |  |  |  |  |
| J1 cohort | Named testers; flags remain off; usage within limits |  |  |  |  |  |

Required evidence bundle:

- release commit SHA and reviewed diff reference;
- service list, plans, and regions;
- environment variable names and non-secret values;
- secret fingerprints and escrow references only;
- database identity, pgvector version, migration head, public table count;
- Render build/start logs with secrets redacted;
- `/health` and `/ready` status/body;
- docs/registration/publishing/developer/custom-endpoint checks;
- CORS positive/negative results;
- 12-step storage evidence, checksums, versioning/lifecycle verdict, dry-run report;
- signed manual UI acceptance;
- cohort roster (stored outside this document), usage snapshots, stop/rollback record.

---

## Source references

| Document | Use |
|---|---|
| [M12 Manual UI Acceptance Checklist](../m12/M12_MANUAL_UI_ACCEPTANCE_CHECKLIST.md) | Phase I manual UI acceptance (13 areas / 69 sub-checks) |
| [M12 Storage Validation Runbook](../m12/M12_STORAGE_VALIDATION_RUNBOOK.md) | Phase H 12-step synthetic storage plan |
| [M13 Database and Storage Setup](M13_DATABASE_AND_STORAGE_SETUP.md) | Neon identity/TLS/migration, B2 private bucket/key/lifecycle, verification SQL |
| [M13 Secret and Environment Inventory](M13_SECRET_AND_ENVIRONMENT_INVENTORY.md) | Secret generation, escrow, environment value rules |
| [M13 Free-Tier Cost and Limits](M13_FREE_TIER_COST_AND_LIMITS.md) | Render/Neon/B2 allowances, suspension behavior, card policy |
| [M13 Deployment Configuration](M13_DEPLOYMENT_CONFIGURATION.md) | Frontend build/runtime, backend envelope, CORS/health behavior |
| [M13.3 Render Blueprint Review](M13_3_RENDER_BLUEPRINT_REVIEW.md) | `exec`, `^$`, schema guard, two-service/no-database topology |
| [M13.3 Baseline and Git Reconciliation](M13_3_BASELINE_AND_GIT_RECONCILIATION.md) | Baseline identity, uncommitted-state cautions, blueprint corrections |
| [M13.3 Application Remediation Audit](M13_3_APPLICATION_REMEDIATION_AUDIT.md) | Residual risks (SEC-4, OPS-2, REL-1/2/3, OPS-5, OPS-1) |
| [M13 Manual Acceptance Handoff](M13_MANUAL_ACCEPTANCE_HANDOFF.md) | Manual acceptance prerequisites and known gaps |
| [M13 Deployment Execution Report](M13_DEPLOYMENT_EXECUTION_REPORT.md) | Ordered deployment sequence and rollback rules |

---

## Final status

```text
RUNBOOK_EXECUTED = NO
DEPLOYMENT_AUTHORIZED = NO
EXTERNAL_RESOURCES_CREATED = NONE (by this document)
SECRETS_GENERATED = NONE (by this document)
DATABASE_MIGRATION = NOT RUN
STORAGE_VALIDATION = NOT RUN
MANUAL_UI_ACCEPTANCE = PENDING
COHORT_INVITED = NO
PAYMENT_METHOD_ADDED = NO
```

Deployment is **not authorized** by this document. Each gate requires a separate recorded approval. The environment is a public-URL, application-authenticated, invite-only synthetic staging environment — not a network-private or production environment.

**Phase count: 10 (A-J). Approval gates: 12.**
