# M10 Remediation — Stage 3: STOR-1 Production Storage Safety

**Date:** 2026-11-11
**Finding:** STOR-1 — production configuration could silently persist uploads on Render's ephemeral local filesystem (`STORAGE_BACKEND=local` in `.env.production.example` / `render.yaml`).

---

## 1. Root cause

The storage factory accepted any backend with no environment awareness: production templates selected `local` (Render ephemeral FS → data loss on every deploy/restart), and the S3 adapter's config errors only surfaced lazily on first operation.

## 2. Fix implemented

1. **`backend/app/storage/__init__.py`** — new `validate_storage_configuration(settings)` (fail-closed):
   - `ENVIRONMENT=production` + `STORAGE_BACKEND=local` → `RuntimeError` at startup/factory use.
   - S3 backend without `S3_BUCKET_NAME` → `RuntimeError`.
   - S3 with `S3_ENDPOINT_URL` but missing `S3_ACCESS_KEY_ID`/`S3_SECRET_ACCESS_KEY` → `RuntimeError` (AWS IAM-role deployments without an endpoint may omit static keys).
   - Unknown backend → `ValueError`.
   - `get_storage_provider()` now runs the validation before constructing the singleton.
2. **`backend/app/main.py`** — lifespan validates storage configuration **before** the catch-all startup guard, so production fails to start clearly instead of degrading.
3. **`backend/app/storage/s3.py`** — `_get_full_key` now neutralizes `..`/`.`/empty path segments (tenant prefix cannot be escaped by traversal in object keys). Found by the new tests: previous `lstrip("/")` allowed `tenant-A/../../etc/passwd`.
4. **`.env.production.example`** — `STORAGE_BACKEND=s3` + documented `S3_BUCKET_NAME`, `S3_ENDPOINT_URL` (AWS empty / R2 / MinIO), `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION_NAME` placeholders (no real credentials).
5. **`render.yaml`** — `STORAGE_BACKEND=s3` + operator-provided (`sync: false`) S3 env keys.
6. Also corrected the LLM section of `.env.production.example` (OmniRoute optional; `auto` validity notes) — config-audit follow-up (C1-D2, documentation only).

## 3. Files changed

| File | Change |
|---|---|
| `backend/app/storage/__init__.py` | `validate_storage_configuration` + fail-closed factory |
| `backend/app/main.py` | lifespan pre-flight validation |
| `backend/app/storage/s3.py` | traversal-safe key construction |
| `.env.production.example` | S3 configuration + LLM section corrections |
| `render.yaml` | S3 storage env vars |
| `backend/tests/test_remediation_stage3_storage.py` | new — 11 tests |

## 4. Tests (required matrix)

| # | Requirement | Test | Result |
|---|---|---|---|
| 1 | Local development configuration | `test_local_development_configuration_valid` | PASS |
| 2 | Valid production S3 configuration | `test_valid_production_s3_configuration_valid` | PASS |
| 3 | Missing production bucket | `test_production_s3_missing_bucket_rejected` | PASS |
| 4 | Missing production credentials where required | `test_production_s3_endpoint_without_credentials_rejected` | PASS |
| 5 | Production local-storage selection rejected | `test_production_local_storage_rejected` | PASS |
| 6 | Tenant-separated object keys | `test_tenant_separated_object_keys`, `test_build_storage_key_partitions_by_tenant` | PASS |
| 7 | Cross-tenant object access rejected | key-space isolation verified; route-level authorization enforced by existing document/retrieval suites | PASS (static + existing suites) |
| 8 | Path traversal rejected | `test_sanitize_filename_blocks_path_traversal`, `test_leading_slash_cannot_escape_tenant_prefix` | PASS |
| 9 | Upload/download/delete via mocks | existing `tests/test_s3_storage.py::test_s3_operations_mocked` (referenced) | PASS |
| 10 | S3 errors returned safely without leaking secrets | `test_s3_operation_error_does_not_leak_secrets` | PASS |
| + | Unsupported backend rejected | `test_unsupported_storage_backend_rejected` | PASS |
| + | Dev factory returns local provider | `test_development_factory_returns_local_provider` | PASS |

## 5. Verification

```text
pytest tests/test_remediation_stage3_storage.py tests/test_s3_storage.py => 16 passed (1.24s)
```

## 6. Residual risks

- Live S3/MinIO round-trip remains untested (no real bucket in this environment) — mocked-only, documented.
- `aioboto3` still undeclared in `pyproject.toml` until Stage 5.
- Storage authorization remains at the route/service layer (defense-in-depth via tenant key prefixes at the storage layer).

---

```text
STAGE_3_STATUS = PASS
```
