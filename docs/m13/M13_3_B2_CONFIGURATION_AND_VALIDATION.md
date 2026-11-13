# M13.3 Stage 3 - Backblaze B2 Configuration and Synthetic Validation

| Field | Value |
|---|---|
| Milestone | M13.3 Stage 3 - B2 S3-compatible storage configuration and validation planning |
| Repository | `E:\MM Office\Multi-Tanant-CaaS` |
| Baseline | `main` @ `9c27e1b8d3e6aeec00dcf6ddb84cd849b9a607e8`; worktree has modified `render.yaml`, `backend/app/core/config.py`, and `.env.example` |
| Date | 2026-11-13 |
| Mode | **READ-ONLY.** No Backblaze account, bucket, key, upload, download, lifecycle change, deletion, install, or Git mutation was performed. |
| Live validation | `LIVE_B2_VALIDATION = NOT RUN` |
| Scope | Explain the B2 endpoint and region contract, checksum compatibility, private-bucket and least-privilege setup, the exact adapter behavior, versioning/lifecycle semantics, and a 12-step synthetic validation plan. Any command is an outline for a separately authorized operator. |
| Inputs | `backend/app/storage/s3.py`, `backend/app/storage/base.py`, `backend/app/storage/__init__.py`, `backend/app/core/config.py`, `render.yaml`, `backend/requirements.lock`, `docs/m13/M13_DATABASE_AND_STORAGE_SETUP.md`, `docs/m13/M13_DEPLOYMENT_CONFIGURATION.md`, `docs/m13/M13_2_IMPLEMENTATION_REPORT.md`, `docs/m13/M13_2_RESIDUAL_RISKS.md`, `docs/m13/M13_FREE_TIER_COST_AND_LIMITS.md` |
| Evidence convention | `path:line` is repository source. Provider behavior described as "expected" is a hypothesis to validate, not a measured result. |

> **`LIVE_B2_VALIDATION = NOT RUN.`** No B2 request was made. Do not treat any expected result in this document as observed. Do not paste a real key ID, application key, bucket credential, or presigned URL into this document, a chat, a ticket, a screenshot, or a commit.

---

## 1. Current code facts

| Area | Evidence | Fact |
|---|---|---|
| Storage backend selection | `backend/app/core/config.py:69`; `render.yaml:128-129` | `STORAGE_BACKEND` defaults to `local`; the staging blueprint sets `s3`. |
| Bucket/endpoint/keys | `backend/app/core/config.py:71-74` | `S3_BUCKET_NAME`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`. |
| Region default | `backend/app/core/config.py:75` | `S3_REGION_NAME` defaults to `us-east-1`. This is a code default, not a B2 region discovery mechanism. |
| Blueprint B2 block | `render.yaml:125-144` | `STORAGE_BACKEND=s3`; bucket/endpoint/keys/region are `sync: false`; both checksum variables are `when_required`. |
| Provider construction | `backend/app/storage/s3.py:189-207` | Explicit arguments win; otherwise settings/env; region falls back to `us-east-1`. |
| Client construction | `backend/app/storage/s3.py:225-242` | New `aioboto3.Session()` and S3 client per operation; passes endpoint, static keys, and region; no `botocore.config.Config`. |
| Tenant key prefix | `backend/app/storage/s3.py:209-216` | `_get_full_key` removes empty/`.`/`..` segments and returns `{tenant_id}/{clean_key}`. |
| Default key builder | `backend/app/storage/base.py:85-95` | `build_storage_key` already returns `tenants/{tenant_id}/kbs/{kb}/docs/{doc}/v{n}/{safe_name}`. |
| Save | `backend/app/storage/s3.py:244-256` | One `put_object` with the full body; no `ContentType`, metadata, multipart, or explicit checksum. |
| Get | `backend/app/storage/s3.py:258-269` | One `get_object`; reads the entire body into memory. |
| Delete | `backend/app/storage/s3.py:271-282` | One `delete_object`; `True` on success; `False` only for a typed not-found. |
| Exists | `backend/app/storage/s3.py:284-295` | One `head_object`; `True` if present; `False` only for a typed not-found; other errors raise. |
| Size | `backend/app/storage/s3.py:297-305` | `head_object`; returns `ContentLength`. |
| Listing | `backend/app/storage/s3.py:307-331` | Paginated `list_objects_v2` under `{tenant_id}/`; strips that one prefix; returns sorted relative keys. |
| Error hierarchy | `backend/app/storage/base.py:8-26` | `StorageError`, `StorageNotFoundError`, `StorageUnavailableError`. |
| Error classifier | `backend/app/storage/s3.py:125-176` | Not-found codes versus auth/network/throttle/bucket/other-provider failures. |
| Fail-closed validation | `backend/app/storage/__init__.py:17-53` | S3 requires a bucket; an endpoint requires static access/secret keys; production rejects `local`. Staging alone does not reject `local`. |
| Pinned libraries | `backend/requirements.lock` | `aioboto3==15.5.0`, `aiobotocore==2.25.1`, `botocore==1.40.61`. |

The adapter is intentionally small: single PUT, full GET, delete by key, head, and paginated listing. It has no multipart upload, no presigned URL, no public-bucket support, and no per-object content type.

---

## 2. Endpoint and region

### 2.1 The endpoint shape

```text
https://s3.<actual-region>.backblazeb2.com
```

Examples of the **shape** only (the real value must come from the bucket's console page):

```text
https://s3.us-west-004.backblazeb2.com
https://s3.<actual-region>.backblazeb2.com   # replace with the bucket's real code
```

Rules:

1. `S3_ENDPOINT_URL` is the service endpoint. Do **not** append the bucket name. The adapter passes `Bucket=` to each API call.
2. `S3_REGION_NAME` must be the bucket's **actual** region code, for example `us-west-004`. It is not a generic cloud region and it is not `auto`.
3. Do not leave the code default `us-east-1` unless the bucket is genuinely in that region. A wrong region changes the SigV4 credential scope and can produce signature, authorization-header, or redirect errors.
4. Do not use `auto`; that is a Cloudflare R2 convention, not a B2 S3 endpoint region.
5. The endpoint is HTTPS only. Do not disable TLS verification, add a public custom domain, or use an HTTP endpoint to work around a certificate problem.

The bucket's region is shown in the Backblaze B2 console on the bucket page. Record the exact code in the evidence ledger. If the endpoint host and `S3_REGION_NAME` disagree, stop before uploading; a request may look like an authentication failure or a missing bucket rather than an obvious region error.

### 2.2 SigV4 and the endpoint/region pair

The adapter uses static B2 application-key credentials (`S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`) and passes them to aioboto3. Botocore signs each request with Signature Version 4. The signature includes the region, service (`s3`), host, and request details.

A mismatch can surface as:

| Symptom | Likely cause | Action |
|---|---|---|
| `SignatureDoesNotMatch` | Wrong secret, wrong region in the signature, or a key/secret mix-up. | Recheck the key pair and region; do not broaden the key. |
| `AuthorizationHeaderMalformed` | Region in the credential scope does not match the endpoint. | Set `S3_REGION_NAME` to the bucket's actual code. |
| `PermanentRedirect` / 301 / 307 | Endpoint is for a different region. | Fix the endpoint and region together. |
| `InvalidAccessKeyId` | Wrong key ID or a key that was deleted/rotated. | Reissue a bucket-scoped key; do not use the master key. |
| `RequestTimeTooSkewed` | Container clock skew. | Treat as a platform/runtime clock problem, not a key problem. |

The adapter does not use temporary STS credentials, session tokens, or presigned URLs. B2 application keys are static key ID/secret pairs. Do not add an `AWS_SESSION_TOKEN` expectation to this path.

### 2.3 Virtual-hosted versus path-style addressing

The adapter does not set `s3={"addressing_style": ...}`. Botocore's default is `auto`, which chooses an addressing style from the endpoint and bucket name. B2 supports both virtual-hosted-style and path-style S3 requests, but the exact choice is botocore's, not an application setting.

Consequences:

- Use a DNS-safe bucket name. A name containing dots can break virtual-hosted-style TLS because the certificate wildcard does not match the extra label. Prefer lowercase letters, digits, and hyphens; avoid dots.
- If virtual-hosted style fails against B2, forcing path style requires a code change (`Config(s3={"addressing_style": "path"})`), not a Render environment variable. Do not claim this is config-only.
- The endpoint must not include the bucket. A path-style request still uses the bucket in the request path, not in `S3_ENDPOINT_URL`.
- A private bucket does not need public CORS or a website configuration. The backend is the only client.

---

## 3. Flexible checksums and botocore 1.40.61

Botocore 1.40.x enables flexible checksums. The defaults are `when_supported` for both request checksum calculation and response checksum validation. That can add `x-amz-checksum-*` headers or expect checksum trailers that an S3-compatible provider may not implement identically.

The blueprint sets both compatibility variables (`render.yaml:140-144`):

```text
AWS_REQUEST_CHECKSUM_CALCULATION=when_required
AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
```

What they do:

| Variable | Botocore setting | Effect |
|---|---|---|
| `AWS_REQUEST_CHECKSUM_CALCULATION` | `request_checksum_calculation` | `when_required` calculates a request checksum only when the operation requires it, instead of adding one whenever supported. |
| `AWS_RESPONSE_CHECKSUM_VALIDATION` | `response_checksum_validation` | `when_required` validates a response checksum only when required, instead of whenever the response advertises one. |

Important details:

1. The adapter does not pass a `botocore.config.Config` (`s3.py:225-242`). These environment variables are the only checksum control in the current code path.
2. Botocore reads the variables when it builds the client. Set them before the Python process starts. Setting them after a client exists does not change that client.
3. `render.yaml` sets them for the Render service. A local shell, CI job, or one-off probe must set them explicitly; otherwise botocore uses its `when_supported` default.
4. `when_required` is a compatibility fallback, not a claim that B2 rejects the default headers. Prove the behavior with a synthetic PUT/GET before removing the variables.
5. Do not disable TLS verification, make the bucket public, or broaden the key to work around a checksum or signature error. Capture the provider error code and request ID, then stop.

If a put fails with a checksum-related provider error, the adapter's classifier maps a structured provider response to `StorageUnavailableError` (Section 5). That is a storage failure, not a missing object. Do not let a retry loop or reconciliation treat it as absence.

---

## 4. Private bucket and least-privilege application key

### 4.1 Bucket requirements

| Requirement | Why |
|---|---|
| Bucket type **Private** | The application serves objects through authenticated backend routes; no object is public. |
| No public bucket URL, website configuration, or public custom domain | B2 has no R2-style development URL; a public bucket would bypass tenant authorization. |
| No wildcard CORS rule | The backend is server-side; browser CORS is not needed. |
| Server-side encryption at the provider default | Keep SSE-B2 unless a separate security decision requires SSE-C. Do not store a customer key in the repository. |
| Object Lock disabled unless separately approved | Object Lock can block legitimate deletes and complicate lifecycle cleanup. |
| A lifecycle rule for old versions and unfinished uploads | B2 versioning is always on; without lifecycle, deleted objects keep consuming the 10 GB allowance. |

### 4.2 Application key

Backblaze's master key is not the application credential for this integration. Create a dedicated application key:

| Setting | Value |
|---|---|
| Name | `mmaip-staging-app` (or an approved equivalent) |
| Bucket access | Only the private staging bucket |
| Capabilities | `listFiles`, `readFiles`, `writeFiles`, `deleteFiles` |
| Optional | `listAllBucketNames` only if the SDK/console requires it for a bucket-restricted key |
| Prohibited | `writeBuckets`, `deleteBuckets`, bucket-retention administration, account-wide access |

Notes:

- Grant both `writeFiles` and `deleteFiles`. The M13 runbook records that delete-by-name and specific-version deletion can require different B2 capabilities; confirm the exact split in the B2 console and do not narrow the key until the live delete test passes.
- In S3 terms, the B2 **keyID** is `S3_ACCESS_KEY_ID` and the **applicationKey** is `S3_SECRET_ACCESS_KEY`.
- The application needs PutObject, GetObject, HeadObject, DeleteObject, and ListObjectsV2 on this bucket only.
- Do not create an account-level or all-bucket key for the application. Do not use the master key.
- Record the key ID, scope, capabilities, creation date, rotation owner, and expiry. Store the secret only in the provider secret manager and the Render secret environment.

### 4.3 Configuration checklist

Set these only in the Render secret environment or the provider secret manager:

```text
STORAGE_BACKEND=s3
S3_BUCKET_NAME=<private-bucket>
S3_ENDPOINT_URL=https://s3.<region>.backblazeb2.com
S3_ACCESS_KEY_ID=<key-id>
S3_SECRET_ACCESS_KEY=<application-key>
S3_REGION_NAME=<actual-b2-region>
AWS_REQUEST_CHECKSUM_CALCULATION=when_required
AWS_RESPONSE_CHECKSUM_VALIDATION=when_required
```

- Leave `STORAGE_PATH` unset; the S3 backend does not use it.
- Do not append the bucket name to the endpoint.
- Do not use `auto`, `us-east-1` by default, or an endpoint from a different region.
- The fail-closed validator rejects `s3` without a bucket and an endpoint without static keys (`storage/__init__.py:41-53`). It rejects `local` in production (`:29-36`), but `staging` plus `local` is not rejected. The blueprint sets `s3` explicitly; verify the dashboard did not override it.
- `S3_ENDPOINT_URL` must be set explicitly. The validator does not require an endpoint for `STORAGE_BACKEND=s3`; without it, aioboto3 can fall back to the AWS S3 default endpoint instead of B2. The blueprint marks the value `sync: false`, so a missed dashboard value is a runtime failure, not a startup validation error.
- No secret value belongs in `render.yaml`, this document, a screenshot, or a commit.

---

## 5. Adapter behavior

### 5.1 Operation matrix

| Operation | Code path | Behavior | Important limit |
|---|---|---|---|
| `save(tenant_id, relative_key, data)` | `s3.py:244-256` | One `put_object` with the full `data` bytes. Returns the physical key `{tenant_id}/{clean_key}`. | No `ContentType`, no metadata, no multipart, no explicit checksum. Memory equals the full object plus client copies. |
| `get(tenant_id, relative_key)` | `s3.py:258-269` | One `get_object`; reads the whole `Body` into memory. | No range requests, no streaming to the caller. |
| `delete(tenant_id, relative_key)` | `s3.py:271-282` | One `delete_object`. Returns `True` on a successful API call; `False` only for a typed not-found. | On a versioned bucket this hides the current version; it does not necessarily reclaim bytes. |
| `exists(tenant_id, relative_key)` | `s3.py:284-295` | One `head_object`. Returns `True` if present; `False` only for a typed not-found. | Auth, region, network, TLS, throttling, and 5xx errors raise `StorageUnavailableError`. |
| `get_size(...)` | `s3.py:297-305` | `head_object` and `ContentLength`. | Same error semantics as `exists`. |
| `list_keys(tenant_id, prefix="")` | `s3.py:307-331` | Paginated `list_objects_v2` under `{tenant_id}/`; strips that one prefix; filters by optional relative prefix; returns sorted keys. | Requires `listFiles`; does not list object versions. |

There is no separate public `head` method: `exists()` and `get_size()` both call `head_object`.

The application upload cap is 10 MiB per file and 2 files per request (`config.py:76-77`, M13.2 defaults). A single PUT is therefore sufficient for the current envelope; the absence of multipart is not a functional blocker at 10 MiB. It is a scalability limitation if the cap is ever raised.

The adapter creates a new `aioboto3.Session()` and client for every operation. That is a latency/TLS-handshake cost, not a correctness incompatibility. It also means environment variables must be correct at each client construction.

### 5.2 Tenant key layout and the double tenant segment

There are two layers of tenant prefixing:

1. `build_storage_key` returns a **relative** key that already begins with `tenants/{tenant_id}/...` (`base.py:85-95`).
2. `_get_full_key` prepends the tenant again: `{tenant_id}/{clean_key}` (`s3.py:209-216`).

So a document whose `Document.file_path` is:

```text
tenants/<tenant-id>/kbs/<kb-id>/docs/<doc-id>/v1/<filename>
```

is stored physically as:

```text
<tenant-id>/tenants/<tenant-id>/kbs/<kb-id>/docs/<doc-id>/v1/<filename>
```

This is consistent across `save`, `get`, `delete`, `exists`, and `get_size`, because each calls `_get_full_key`. `list_keys` strips exactly the first `{tenant_id}/` and returns the remaining `tenants/{tenant_id}/...` key, which matches `Document.file_path`; reconciliation's orphan check then uses the `tenants/{tenant_id}/` relative prefix (`storage_reconciliation.py:205-210`).

The double segment is redundant but not a correctness defect in the current code. Do not "fix" it by removing one prefix without a migration and a reconciliation plan: existing objects would become unreachable and the database keys would no longer match the physical layout.

### 5.3 Typed error semantics

`backend/app/storage/base.py:8-26` defines three classes:

| Class | Meaning | Caller obligation |
|---|---|---|
| `StorageError` | Base storage failure. | Treat as a storage failure, not absence. |
| `StorageNotFoundError` | The requested object does not exist. | `exists`/`delete` may return `False`; reconciliation may treat it as definitive absence. |
| `StorageUnavailableError` | Storage could not be used safely (auth, network, TLS, timeout, throttling, provider 5xx, bucket unavailable, other provider response). | Do not treat as absence; mark inventory incomplete or fail the operation. |

The classifier (`s3.py:125-176`) maps:

- Genuine not-found codes (`NoSuchKey`, `NotFound`, `404`, `NoSuchVersion`) or HTTP 404 to `StorageNotFoundError`.
- Credential/signature/access-denied codes and HTTP 401/403 to `StorageUnavailableError`.
- Network/timeout/connection/endpoint exception classes to `StorageUnavailableError`.
- Missing-bucket codes, throttling codes, and HTTP 429/500/502/503/504 to `StorageUnavailableError`.
- Any other structured provider response to `StorageUnavailableError`.
- A non-provider exception to the base `StorageError`.

This is the M13.2 fix for the old `exists()` behavior that returned `False` for every exception. The mapping is tested against provider-shaped exceptions, not live B2 (Section 9).

### 5.4 Content type and access path

`put_object` does not set `ContentType`. B2 will apply its default content type. This is acceptable for the current application because:

- The bucket is private.
- Objects are served by the backend, not by a public object URL.
- The application stores the original/detected MIME type in the database (`Document.mime_type`), not in the object metadata.

If a future feature serves objects directly from B2 or uses presigned URLs, the missing `ContentType` becomes a user-visible issue and requires a code change. Do not add public access to compensate.

---

## 6. Versioning, lifecycle, and quota

### 6.1 Versioning is always on

B2 buckets are versioned by default, and the application does not disable versioning. Consequences:

- `DeleteObject` hides the current version rather than necessarily erasing the bytes.
- A `head_object` 404 after delete proves only that the current view is gone. It does not prove that storage was reclaimed.
- Older versions count toward the 10 GB free storage allowance.
- Repeated uploads of the same key create new versions; the app's keys are normally unique per document version, but cleanup still matters.
- Versioning is **not** a backup. A lifecycle deletion is permanent and a bucket-level accident can propagate.

### 6.2 Lifecycle is mandatory operationally, but is not backup

Configure a lifecycle rule in the B2 web console (or the B2 Native API/CLI):

1. Recommended rule: **Keep only the last version of the file**. This hides the previous version for one day and then deletes it.
2. Alternative: keep prior versions for an approved retention period, for example 30 days.
3. Leave `fileNamePrefix` blank only if the rule should apply to the whole bucket. Verify the selection; an empty prefix can delete every file in the bucket.
4. Set `daysFromStartingToCancelingUnfinishedLargeFiles` to a small positive value, for example 3, to cancel interrupted multipart uploads. The current adapter does not create multipart uploads, but the rule is still useful for bucket hygiene.
5. Save the rule and confirm the console shows it.
6. Record the rule name, prefix, retention period, unfinished-upload setting, and the date/time applied.

Lifecycle behavior:

- Rules run about once per day; the minimum interval is one day. A version hidden now is not necessarily deleted today.
- B2 lifecycle is managed through the B2 console and Native API/CLI. Do not assume full S3 `PutBucketLifecycleConfiguration` parity; verify the rule in the console.
- Lifecycle deletion is permanent. It is not a backup and it does not provide point-in-time recovery.
- Keep the synthetic staging dataset and version count small; millions of versions can degrade listing/deletion and trigger account restrictions.

**Never use lifecycle as backup.** The application has no B2 backup/PITR feature; M13.2 records this as deferred risk RR-13. A backup requires a separate, independently controlled copy (Section 7, Step 12).

### 6.3 Free allowance and overage

| Item | Free allowance | Implication |
|---|---|---|
| Storage | First 10 GB account-wide, including all versions | Deleted-but-noncurrent versions still count. |
| Egress | Free up to 3x average monthly stored data | Large restores can exceed it. |
| Class A/B/C operations | Free | Normal uploads/downloads/lists are not the first cost. |
| Class D operations | First 2,500/day free | Heavy listing/version inspection can hit the Class D allowance. |
| Hard cap | None by default | Above the allowance, usage is billable; without a payment method, B2 may restrict or suspend the account. |

Confirm current terms in the B2 console before relying on them. The application has no storage retry queue; a quota, auth, endpoint, or checksum failure surfaces as an upload or ingestion failure.

---

## 7. Synthetic validation plan (12 steps)

### 7.0 Status and hard rules

> **`LIVE_B2_VALIDATION = NOT RUN`.** Every step below is a plan. No bucket, key, object, lifecycle rule, reconciliation run, or backup was created or executed by this document.

Hard rules:

1. Synthetic data only. Use a fixed marker body and a unique nonce. Do not upload a real document, customer data, or a production file.
2. Use the private staging bucket and a bucket-scoped application key. Do not use a master key or an account-wide key.
3. Do not make the bucket public, add a public custom domain, add a wildcard CORS rule, or disable TLS verification to make a test pass.
4. Do not create, change, or delete a lifecycle rule without approval gate A4.
5. **Never run `reconcile_storage --fix` against live B2.** Step 11 is dry-run only. `--fix` requires a separate approval after all 12 steps pass, and even then only with `inventory_complete=true`.
6. **Never treat lifecycle or versioning as a backup.** Step 12 is a manual paired backup/restore rehearsal, not an automated backup.
7. Keep secrets in the secret manager or a hidden prompt. Do not echo them, put them in command history, or write them to a temp script. Use a child-process environment only when necessary.
8. Save probe scripts outside the repository (`%TEMP%`). Do not commit them.
9. Stop on any unexpected provider error. Capture the error code and request ID with secrets redacted; do not broaden the key or weaken the bucket.

### 7.1 Approval gates

| Gate | Scope | Status |
|---|---|---|
| A1 | Read/write/delete synthetic objects in the approved private bucket using the approved app key. | **NOT REQUESTED / NOT EXECUTED** |
| A2 | One negative authentication test with a deliberately invalid or disposable key. | **NOT REQUESTED / NOT EXECUTED** |
| A3 | One isolated network-failure test with an invalid endpoint; no app environment change. | **NOT REQUESTED / NOT EXECUTED** |
| A4 | Create or change the bucket lifecycle rule. | **NOT REQUESTED / NOT EXECUTED** |
| A5 | Run reconciliation in dry-run against the staging database and B2 bucket. | **NOT REQUESTED / NOT EXECUTED** |
| A6 | Create/use a separate backup target and perform a restore rehearsal. | **NOT REQUESTED / NOT EXECUTED** |

### 7.2 Probe harness contract

The steps below assume a small probe saved as `%TEMP%\m13_b2_probe.py`, outside the repository. The probe must:

- Read `S3_BUCKET_NAME`, `S3_ENDPOINT_URL`, `S3_REGION_NAME`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY` from the process environment.
- Use the repository's `S3StorageProvider` for adapter-level steps, with explicit constructor arguments so a developer-local `.env` cannot silently override the target.
- Print only synthetic keys, byte counts, SHA-256 hashes, booleans, exception class names, provider error codes, and request IDs. Never print a secret or a full signed URL.
- Use a unique nonce (`m13-validation/<uuid>/...`) and a fixed body such as `M13 synthetic B2 validation - no real data\n`.
- Refuse to run `--fix`, `--delete-orphans`, or any lifecycle mutation.
- Set the checksum environment variables before the process starts, or pass an explicit botocore `Config` for the raw-client steps.

The probe is an outline contract, not a committed script. A local operator must review it before execution.

### 7.3 Common setup (placeholders only)

```powershell
$py = "E:\MM Office\Multi-Tanant-CaaS\backend\.venv\Scripts\python.exe"
$env:S3_BUCKET_NAME = "<private-bucket>"
$env:S3_ENDPOINT_URL = "https://s3.<actual-region>.backblazeb2.com"
$env:S3_REGION_NAME = "<actual-b2-region>"
$env:STORAGE_BACKEND = "s3"
$env:AWS_REQUEST_CHECKSUM_CALCULATION = "when_required"
$env:AWS_RESPONSE_CHECKSUM_VALIDATION = "when_required"

# Inject the key ID and application key from the secret manager or a hidden prompt.
# Do not type them into a command that is logged, and do not print them.
```

The key ID is not a secret in the same sense as the application key, but both are credentials. Treat the pair as sensitive.

### 7.4 Step 1 - Connectivity and configuration

| Field | Detail |
|---|---|
| Objective | Prove the endpoint, region, bucket, and key can reach B2 and list under a synthetic prefix. |
| Command outline | `& $py "$env:TEMP\m13_b2_probe.py" connectivity --prefix "m13-validation/<nonce>/"` |
| Expected | A successful `list_objects_v2` response (HTTP 200), zero or more synthetic keys, no `SignatureDoesNotMatch`, `AuthorizationHeaderMalformed`, `PermanentRedirect`, or `InvalidAccessKeyId`. |
| Evidence | Timestamp; endpoint host; `S3_REGION_NAME`; bucket name; HTTP status; provider request ID; exception class/code if any. No secret. |
| Approval gate | **A1.** |
| Stop condition | Any auth/signature/region/redirect error. Do not retry with broader credentials. |

A listing failure can also mean the key lacks `listFiles`. That is a key-scope problem, not a reason to use an account key.

### 7.5 Step 2 - Put a synthetic object

| Field | Detail |
|---|---|
| Objective | Prove a single-PUT write through the adapter, including the tenant prefix and returned key. |
| Command outline | Create a local synthetic body, then `& $py "$env:TEMP\m13_b2_probe.py" put --tenant "<tenant-a-uuid>" --key "tenants/<tenant-a-uuid>/kbs/m13-validation/docs/<doc-uuid>/v1/payload.txt" --body-file "$env:TEMP\m13_b2_payload.txt"` |
| Expected | `put_object` succeeds; the adapter returns the physical key `<tenant-a-uuid>/tenants/<tenant-a-uuid>/kbs/m13-validation/docs/<doc-uuid>/v1/payload.txt`; byte count equals the body; an ETag/request ID is recorded. |
| Evidence | Synthetic key; byte count; SHA-256 of the body; HTTP status; ETag; provider request ID. |
| Approval gate | **A1.** |
| Stop condition | Auth, signature, checksum, or region error. Do not make the bucket public or remove checksum variables as a first response. |

The double tenant segment in the returned key is expected in the current code (Section 5.2). Record it; do not "correct" it during validation.

### 7.6 Step 3 - Full GET and hash comparison

| Field | Detail |
|---|---|
| Objective | Prove the adapter returns the exact bytes written. |
| Command outline | `& $py "$env:TEMP\m13_b2_probe.py" get --tenant "<tenant-a-uuid>" --key "tenants/<tenant-a-uuid>/kbs/m13-validation/docs/<doc-uuid>/v1/payload.txt" --expect-sha256 "<sha256>"` |
| Expected | Returned byte count equals the PUT byte count; SHA-256 matches exactly. |
| Evidence | Byte count; expected and actual SHA-256; elapsed time; request ID. |
| Approval gate | **A1.** |
| Stop condition | Any hash mismatch. Do not accept the bucket for ingestion until the bytes are proven identical. |

### 7.7 Step 4 - Exists true

| Field | Detail |
|---|---|
| Objective | Prove `head_object` returns true for the written key. |
| Command outline | `& $py "$env:TEMP\m13_b2_probe.py" exists --tenant "<tenant-a-uuid>" --key "tenants/<tenant-a-uuid>/kbs/m13-validation/docs/<doc-uuid>/v1/payload.txt"` |
| Expected | `True`; no exception. |
| Evidence | Boolean; request ID; elapsed time. |
| Approval gate | **A1.** |
| Stop condition | `False` or `StorageUnavailableError`. A false result here is not a successful "missing" test. |

### 7.8 Step 5 - Missing object returns false

| Field | Detail |
|---|---|
| Objective | Prove a genuinely absent key maps to a typed not-found and `exists()` returns `False`, not an availability error. |
| Command outline | `& $py "$env:TEMP\m13_b2_probe.py" exists --tenant "<tenant-a-uuid>" --key "tenants/<tenant-a-uuid>/kbs/m13-validation/docs/<missing-doc-uuid>/v1/missing.txt"` |
| Expected | `False`; the probe records `StorageNotFoundError` (or an equivalent typed not-found) and does not record `StorageUnavailableError`. |
| Evidence | Boolean; exception class; provider error code/status; request ID. |
| Approval gate | **A1.** |
| Stop condition | `StorageUnavailableError`, `StorageError`, or an unexpected provider response. Treat the object state as unknown; do not run reconciliation `--fix`. |

### 7.9 Step 6 - Authentication failure is typed

| Field | Detail |
|---|---|
| Objective | Prove an auth failure is `StorageUnavailableError`, never a not-found and never a silent `False`. |
| Command outline | `& $py "$env:TEMP\m13_b2_probe.py" auth-failure --access-key-id "<disposable-invalid-key-id>" --secret-access-key "<disposable-invalid-secret>" --bucket "<private-bucket>"` |
| Expected | `StorageUnavailableError` with an access-denied/invalid-credentials provider code (for example `AccessDenied`, `InvalidAccessKeyId`, or a 403); no `StorageNotFoundError`; no object mutation. |
| Evidence | Exception class; provider code; HTTP status; request ID; timestamp. Never the key or secret. |
| Approval gate | **A2.** |
| Stop condition | Repeated auth failures, account lockout, or unexpected provider behavior. Stop after one attempt; do not use the real application key with a wrong secret. |

Prefer a deliberately invalid/disposable key over corrupting the real secret. If no disposable key is available, mark the step **NOT RUN** rather than risk the staging key.

### 7.10 Step 7 - Network failure is typed

| Field | Detail |
|---|---|
| Objective | Prove a transport/DNS failure is `StorageUnavailableError`, not a not-found and not a silent `False`. |
| Command outline | `& $py "$env:TEMP\m13_b2_probe.py" network-failure --endpoint "https://s3.m13-invalid.invalid" --connect-timeout 3 --read-timeout 3` |
| Expected | `StorageUnavailableError` with an endpoint/connection/DNS/timeout class; no B2 mutation. The `.invalid` top-level domain is reserved and does not resolve, so the failure is deterministic and does not depend on a real region. |
| Evidence | Exception class; endpoint string; elapsed time; timestamp. No secret. |
| Approval gate | **A3.** |
| Stop condition | A successful connection or an unexpected provider response. Do not change the staging app's `S3_ENDPOINT_URL`; run the fault test in an isolated process. |

### 7.11 Step 8 - Tenant-prefix isolation

| Field | Detail |
|---|---|
| Objective | Prove two synthetic tenants with the same relative key do not collide and cannot read each other's object. |
| Command outline | `& $py "$env:TEMP\m13_b2_probe.py" isolation --tenant-a "<tenant-a-uuid>" --tenant-b "<tenant-b-uuid>" --relative-key "kbs/m13-validation/docs/<doc-uuid>/v1/payload.txt"` (the probe writes the same relative key for both tenants) |
| Expected | The two physical keys differ: `<tenant-a>/kbs/m13-validation/docs/<doc-uuid>/v1/payload.txt` and `<tenant-b>/kbs/m13-validation/docs/<doc-uuid>/v1/payload.txt`. Each `get` returns its own body. `list_keys(tenant-a)` contains only A's relative key and does not contain B's. |
| Evidence | Both physical keys; both body hashes; list counts and synthetic keys; request IDs. |
| Approval gate | **A1.** |
| Stop condition | Any cross-read, identical physical key, or listing that returns the other tenant's key. |

Use synthetic UUIDs only. Do not use a real tenant ID from staging.

### 7.12 Step 9 - Delete behavior

| Field | Detail |
|---|---|
| Objective | Prove delete succeeds for the current version and that `exists` sees the current view as absent; record versioning side effects. |
| Command outline | `& $py "$env:TEMP\m13_b2_probe.py" delete --tenant "<tenant-a-uuid>" --key "tenants/<tenant-a-uuid>/kbs/m13-validation/docs/<doc-uuid>/v1/payload.txt"` then repeat `exists` for the same key. Optionally repeat `delete` to record idempotency. |
| Expected | First delete returns `True`; `exists` returns `False` or a typed not-found for the current view. A second delete may return `True` (S3 `DeleteObject` is idempotent) or `False` if B2 raises a typed not-found. Record the observed behavior. |
| Evidence | Delete return values; `exists` result; optional version list showing a noncurrent version/delete marker; request IDs. |
| Approval gate | **A1.** |
| Stop condition | Delete raises `StorageUnavailableError` or reports false success while the object remains readable. Do not purge versions manually unless separately approved. |

Do **not** interpret `delete=True` as proof that the object existed or that the bytes were reclaimed. On a versioned bucket, the current version is hidden and older versions can remain.

### 7.13 Step 10 - Versioning and lifecycle inspection

| Field | Detail |
|---|---|
| Objective | Record the bucket's actual versioning and lifecycle state; confirm that the lifecycle rule exists and that deleted objects can leave noncurrent versions. |
| Command outline | Primary: B2 console -> bucket -> **Lifecycle Settings** and the bucket's version history. Optional native/S3 read-only listing if an approved CLI is available: `aws s3api list-object-versions --bucket "<private-bucket>" --prefix "m13-validation/<nonce>/" --endpoint-url "https://s3.<actual-region>.backblazeb2.com" --region "<actual-b2-region>"` (do not print credentials). |
| Expected | Versioning is always on. The lifecycle rule is present with the approved prefix, retention, and unfinished-large-file cancellation. The deleted key has a noncurrent version/delete marker, or the console explains why it does not. |
| Evidence | Rule name/prefix/retention; console excerpt or API response; version IDs (not secrets); timestamp. |
| Approval gate | **A1** for inspection; **A4** for any lifecycle creation or change. |
| Stop condition | No lifecycle rule, an unexpected whole-bucket rule, Object Lock enabled without approval, or a version listing that cannot be explained. |

Lifecycle rules run about daily. Do not wait for deletion during this step; record the configured intent and the observed version state.

### 7.14 Step 11 - Reconciliation dry-run

| Field | Detail |
|---|---|
| Objective | Prove the adapter can inventory the bucket and compare it with the staging database without mutating either side. |
| Command outline | From `backend`, with the staging direct database URLs and B2 env set only in this shell: `& $py -m app.commands.reconcile_storage --dry-run --tenant "<synthetic-tenant-uuid>"` |
| Expected | JSON report with `dry_run=true`, `fix=false`, `inventory_complete=true`, `documents_checked` equal to the expected synthetic count, and `missing_objects_count` / `orphan_objects_count` equal to the fixture expectations (typically `0` for a freshly uploaded fixture); exit code `0`; no DB row or object mutation. |
| Evidence | Redacted JSON report; `tenant_scope`; `inventory_status`; counts; exit code; timestamp. No DSN, key, or secret. |
| Approval gate | **A5.** |
| Stop condition | `inventory_complete=false`, a listing `StorageError`, any auth/region/checksum error, or a non-zero exit. Stop; do not run `--fix`. |

The CLI's dry-run is the default, but pass `--dry-run` explicitly. Do not add `--fix`, `--delete-orphans`, or `--allow-incomplete-inventory`. The command must connect only to the approved staging database and bucket; verify the parsed `DATABASE_URL` host/database/user first, as in the Neon guide.

**Never run `reconcile_storage --fix` against live B2.** The M13.2 service refuses an incomplete inventory, but `--fix` can still mark healthy documents FAILED if the operator uses `--allow-incomplete-inventory` or mis-scopes the tenant. A separate approval and a complete dry-run are prerequisites.

### 7.15 Step 12 - Paired backup and restore rehearsal

| Field | Detail |
|---|---|
| Objective | Prove a backup copy independent of the app bucket's lifecycle can be restored and verified. This is a manual rehearsal, not an automated backup feature. |
| Command outline | 1. Export a read-only manifest for the synthetic tenant: `file_path`, `file_hash`, `file_size`. 2. Copy each object to an approved backup target (`m13-backup/<date>/...`) using server-side `copy_object` or download/upload. 3. Restore to a separate approved restore prefix/bucket. 4. Verify SHA-256 and byte count for every object; read one restored object through a client configured for the restore target. |
| Expected | Manifest counts match; every hash matches; the restored object is readable; no live key is overwritten; the backup target is outside the lifecycle rule that manages the app bucket (preferably a separate bucket). |
| Evidence | Manifest; per-object hash table; copy/restore request IDs; RPO/RTO assumptions; timestamp; confirmation that this is manual. |
| Approval gate | **A6.** |
| Stop condition | A hash mismatch, a missing object, a restore that writes over live data, or a backup that depends on the same lifecycle rule as the source. |

A same-bucket backup prefix shares fate with the source bucket and its lifecycle. Prefer a separate bucket. B2 versioning is not a backup and lifecycle deletion is permanent. M13.2 records the absence of B2 backup/PITR as deferred risk RR-13; this rehearsal does not close that risk.

---

## 8. Findings and incompatibilities

| ID | Finding | Evidence | Disposition |
|---|---|---|---|
| B-1 | `S3_REGION_NAME` defaults to `us-east-1` if the dashboard value is missing. | `config.py:75`; `render.yaml:138-139` is `sync: false`. | Set the bucket's actual B2 region explicitly. A missing value can produce signature or redirect failures. |
| B-2 | The endpoint is region-specific and must not include the bucket. | `s3.py:235-241`; B2 endpoint contract. | `https://s3.<actual-region>.backblazeb2.com`; verify the host and region together. |
| B-3 | Checksum behavior is controlled only by process environment variables; the adapter passes no `Config`. | `s3.py:225-242`; `render.yaml:140-144`. | Keep `when_required` in Render and set both variables in every local probe shell. B2 acceptance is still unverified. |
| B-4 | Addressing style is not configurable in the adapter. | `s3.py:225-242`; no `addressing_style`. | Use a DNS-safe bucket name. Forcing path style is a code change, not an env change. |
| B-5 | `delete=True` is not proof of prior existence or byte reclamation. | `s3.py:271-282`; B2 versioning. | Record the actual `DeleteObject` behavior; use `exists`/version inspection, not the delete return value, as the state check. |
| B-6 | The physical key contains a redundant tenant segment. | `base.py:85-95`; `s3.py:209-216`. | Consistent but redundant. Do not remove a prefix without a migration/reconciliation plan. |
| B-7 | No `ContentType`, metadata, multipart upload, or presigned URL. | `s3.py:244-256`. | Acceptable for a private bucket and a 10 MiB single-PUT envelope. A future direct-download or larger-file feature needs a code change. |
| B-8 | Versioning is always on; lifecycle is mandatory but is not backup. | B2 bucket semantics; `docs/m13/M13_2_RESIDUAL_RISKS.md` RR-13. | Configure lifecycle for old versions/unfinished uploads; maintain a separate backup target if backup is required. |
| B-9 | The typed-error mapping is tested against provider-shaped exceptions, not live B2. | `s3.py:125-176`; M13.2 test report. | Steps 5-7 are the live confirmation. Do not run `--fix` before they pass. |
| B-10 | The 10 GB allowance includes all versions. | B2 free-tier terms. | Keep the synthetic dataset and version count small; monitor the console. |
| B-11 | The adapter has no storage retry queue. | `s3.py` operation paths. | A quota/auth/checksum failure surfaces as an upload or ingestion failure. Do not mask it as a missing object. |
| B-12 | Staging plus `local` storage is not rejected by the fail-closed validator. | `storage/__init__.py:29-36` checks only `production`. | Keep `STORAGE_BACKEND=s3` in the dashboard and verify no local file appears after an upload. |
| B-13 | `STORAGE_BACKEND=s3` does not require `S3_ENDPOINT_URL` at validation time. | `storage/__init__.py:41-53` checks a bucket, and checks keys only when an endpoint is present. | Set `S3_ENDPOINT_URL` explicitly; otherwise aioboto3 can target the AWS S3 default endpoint. |

No blocking **code** incompatibility was found in the reviewed adapter path. The material risks are configuration hazards (region/endpoint/checksums), B2-specific semantics that must be measured (delete/versioning/lifecycle/error codes), and the absence of backup/PITR.

---

## 9. What remains unverified

`LIVE_B2_VALIDATION = NOT RUN`. None of the following was proven by this document:

1. A real B2 `list_objects_v2`, `put_object`, `get_object`, `head_object`, or `delete_object` through the adapter.
2. The actual bucket region and the matching `https://s3.<region>.backblazeb2.com` endpoint.
3. SigV4 acceptance with the selected key ID/application key and bucket scope.
4. B2 acceptance of botocore 1.40.61's checksum behavior with `when_required`.
5. Exact B2 error codes and HTTP statuses for missing objects, auth failures, wrong region, and network failures.
6. `DeleteObject` behavior on a versioned bucket, including whether a second delete is idempotent and whether a noncurrent version remains visible.
7. Lifecycle S3 parity, the actual rule retention, and the daily execution behavior.
8. The 10 GB allowance accounting with versions and the provider's overage/suspension behavior.
9. Adapter performance: per-operation session/client creation and full-object memory copies.
10. A reconciliation dry-run against the staging database and B2 bucket.
11. A paired backup/restore rehearsal and any RPO/RTO claim.
12. Any real document, tenant data, or production path. This plan is synthetic staging only.

---

## 10. Conclusion

The adapter is a single-PUT, full-GET, delete/head/list S3 client with typed storage errors and a `{tenant_id}/...` physical prefix. It is suitable for the 10 MiB synthetic staging envelope, provided the operator supplies the bucket's real B2 region, an endpoint without the bucket name, a private bucket, a bucket-scoped key, and the two `when_required` checksum variables. B2 versioning is always on, so delete hides the current version and old versions consume the 10 GB allowance; lifecycle is operationally mandatory but is not a backup. The 12-step plan is the live gate, and every step remains **NOT RUN**. Do not run reconciliation `--fix` against live B2, and do not treat lifecycle or versioning as backup.
