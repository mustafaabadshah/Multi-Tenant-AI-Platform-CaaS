# M10 Remediation — Stage 1: D11 Development-Only CORS Configuration

**Date:** 2026-11-11
**Finding:** D11 — dev CORS regex enabled by default (`DEBUG or ENVIRONMENT=="development"`), shipping permissive LAN CORS to any deployment that keeps default flags.

---

## 1. Root cause

`backend/app/main.py` built the CORS regex at import time: the private-network regex (`localhost|127.0.0.1|172.*|192.168.*|10.*`) replaced the production regex whenever `DEBUG=true` **or** `ENVIRONMENT=development` — both defaulting to dev values. Additionally the old code had no way to test production behavior without reloading the module, and no failure when production origins were missing.

## 2. Fix implemented

1. **New centralized policy module** `backend/app/core/cors.py`:
   - `build_cors_policy(settings) -> (origins, regex)` — single source of truth.
   - **Development** (`ENVIRONMENT=="development"`): localhost dev origins allowed; LAN regex applied **only when `ALLOW_DEV_LAN_ORIGINS=true`** (new explicit opt-in).
   - **Production/staging:** explicit `FRONTEND_URL` + `ALLOWED_ORIGINS` + `CORS_ORIGIN_REGEX` only; localhost/LAN origins **rejected with a clear startup error**; wildcard `*` with credentials **rejected**; missing configuration **raises `RuntimeError`** (fail-closed).
2. **`backend/app/main.py`** refactored to an app factory `create_app(app_settings: Settings = settings)` using the policy; module-level `app = create_app()` preserved for uvicorn/imports.
3. **`backend/app/core/config.py`**: added `ALLOW_DEV_LAN_ORIGINS: bool = False`.
4. **`.env.example` / `.env.production.example`**: documented CORS section (ALLOWED_ORIGINS, ALLOW_DEV_LAN_ORIGINS, CORS_ORIGIN_REGEX).

## 3. Files changed

| File | Change |
|---|---|
| `backend/app/core/cors.py` | new — centralized policy |
| `backend/app/main.py` | app factory + policy integration |
| `backend/app/core/config.py` | `ALLOW_DEV_LAN_ORIGINS` setting |
| `backend/tests/test_remediation_stage1_cors.py` | new — 10 tests |
| `backend/tests/test_m05_staging_readiness.py` | `test_cors_origin_resolution` updated to assert the production policy (one of the 6 failing tests — see Stage 6) |
| `.env.example`, `.env.production.example` | CORS documentation entries |

## 4. Tests (required matrix)

| # | Requirement | Test | Result |
|---|---|---|---|
| 1 | Dev localhost accepted | `test_dev_localhost_origin_accepted` | PASS |
| 2 | Explicitly configured LAN dev origin accepted | `test_dev_explicitly_configured_lan_origin_accepted` | PASS |
| 3 | Unconfigured LAN origin rejected | `test_dev_unconfigured_lan_origin_rejected` | PASS |
| 4 | Production trusted origin accepted | `test_prod_trusted_origin_accepted` | PASS |
| 5 | Untrusted production origin rejected | `test_prod_untrusted_origin_rejected` | PASS |
| 6 | Dev regex not applied in production | `test_dev_regex_not_applied_in_production` | PASS |
| 7 | Credentialed CORS never with wildcard | `test_wildcard_origin_with_credentials_rejected` | PASS |
| 8 | Missing prod config → clear startup failure | `test_missing_production_origin_configuration_fails_clearly` | PASS |
| + | Local origin rejected in production config | `test_local_origin_rejected_in_production_configuration` | PASS |
| + | LAN regex active when explicitly opted in | `test_dev_lan_regex_active_when_explicitly_opted_in` | PASS |

All tests exercise the **actual CORSMiddleware preflight behavior** via `TestClient(create_app(Settings(...)))`, not string checks.

## 5. Verification

```text
pytest tests/test_remediation_stage1_cors.py tests/test_m05_staging_readiness.py
=> 16 passed (7.49s)
```

## 6. Deployment notes

- Render (`render.yaml`) already sets `ENVIRONMENT=staging` + `DEBUG=false` → production policy applies automatically.
- Local dev on LAN: set `ALLOW_DEV_LAN_ORIGINS=true` (or list the machine explicitly in `ALLOWED_ORIGINS`).
- Behavior change: previously the LAN regex auto-activated with default flags; now it requires the explicit opt-in.

## 7. Residual risks

None known for this finding. CORS remains a transport-level control only; authentication is JWT/API-key based (unchanged).

---

```text
STAGE_1_STATUS = PASS
```
