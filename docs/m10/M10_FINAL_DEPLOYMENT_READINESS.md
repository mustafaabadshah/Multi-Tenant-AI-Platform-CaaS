# M10 Final Integration — Stage H: Deployment Configuration Readiness

**Date:** 2026-11-11
**No deployments performed. No paid resources created.**

---

## 1. Render (`render.yaml`)

| Requirement | Status | Notes |
|---|---|---|
| Backend start command | PASS | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2` |
| Python version | PASS | env: python (defaults ≥3.12 compatible with `pyproject.toml` `>=3.12`) |
| Build command | PASS | `pip install -e .` |
| DB URL mapping | PASS | `fromDatabase` connectionString for both URLs (async normalizer converts `postgres://`) |
| Alembic strategy | PASS (plan) | `preDeployCommand: alembic upgrade head` — correct for PostgreSQL; note MIG-1 means SQLite never appears in this flow |
| Persistent storage | **PARTIAL** | `STORAGE_BACKEND=local`, `STORAGE_PATH=/app/data/storage` → **Render ephemeral filesystem = data loss on restart/deploy**. Must be S3-backed (adapter exists) before staging with real data. |
| CORS production allowlist | PASS (config) | `ENVIRONMENT=staging`, `DEBUG=false` → production regex + explicit origins apply. Residual D11: these flags are the only guard. |
| Secret env vars | PASS | `SECRET_KEY`, `JWT_SECRET`, `SECRET_ENCRYPTION_KEY` auto-generated; provider keys `sync: false` |
| Health checks | PASS | `healthCheckPath: /health` (process-level; `/ready` also available) |
| Worker configuration | PARTIAL | No Render worker service defined; in-process background tasks serve ingestion. Fine for staging, revisit at scale. |
| Restart behavior / logging | PARTIAL | autoDeploy true; no logging/monitoring add-ons declared (Phoenix profile exists in compose only) |

**render.yaml embedding risk:** `DEFAULT_EMBEDDING_PROVIDER=sentence-transformers` + MiniLM, but `fastembed`/`sentence-transformers` are absent from `pyproject.toml` → first embedding call fails at runtime in staging. Also `LLM_BASE_URL=https://api.openai.com/v1` + `LLM_DEFAULT_MODEL=auto` (dead/confusing pair — see configuration audit).

## 2. Vercel (`vercel.json`, frontend)

| Requirement | Status | Notes |
|---|---|---|
| Next.js build | PASS | `buildCommand: next build`; verified 20/20 routes locally |
| Node version | PASS | Next 16 + React 19 run on Node 20 (compose/Dockerfile use node:20) |
| `NEXT_PUBLIC_API_URL` | PASS (doc) | documented in templates; client resolver falls back gracefully in dev, fail-closed in prod client code |
| HTTPS | PASS | Render + Vercel both HTTPS; mixed-content avoided by using `NEXT_PUBLIC_API_URL` |
| No hardcoded localhost in prod paths | **PARTIAL** | `lib/api.ts` public-endpoint SSR fallback `http://127.0.0.1:8000`; `dashboard/layout.tsx` docs link hardcodes `http://localhost:8000/docs` |
| No secrets in public env | PASS | only `NEXT_PUBLIC_API_URL` is public; no keys |
| SSE compatibility | PASS (dev) | direct backend URL works locally (verified live); Render/Vercel cross-origin SSE requires proper CORS + keep-alive tuning (documented risk, not tested live) |
| Public/embed routes | PASS | `/p/[publicId]` and `/embed/[publicId]` build and serve (Partial Prerender) |
| Security headers | PASS | nosniff, DENY frames, Referrer-Policy, Permissions-Policy configured |

## 3. Docker Compose

- Core services (postgres/pgvector, backend, frontend) + profiles (`worker`, `qdrant`, `redis`, `phoenix`) verified structurally.
- Frontend container runs `npm run dev` (development server) — acceptable for compose dev profile, not production.
- **Fixed this audit:** `.dockerignore` files added for backend (`.env`, `*.db`, `.venv`, `data/`) and frontend (`node_modules`, `.next`) to prevent secret/local-data bake-in via `COPY . /app/`.
- Postgres init: `infrastructure/scripts/init-db.sql` mounted into `/docker-entrypoint-initdb.d`.

## 4. CI (`.github/workflows/ci.yml`)

| Job | Steps | Verdict |
|---|---|---|
| backend-quality | pip install + `pip install -e .` → `ruff check .` → `ruff format --check .` → `pytest -v` with live Postgres service | **Known-red**: ruff steps fail on the current tree (pre-existing, confirmed at HEAD). Pytest on Postgres service would exercise the 12 integration tests (no skip) — **unverified in CI, no alembic step**. |
| frontend-quality | `npm ci` → `npm run lint` → `npm run build` | Unverified in CI (locally lint not run; build passes). |

## 5. Production API URL rules — compliance

- HTTPS frontend → HTTPS backend: enforced by config choice; **no silent HTTP fallback in production client path** (throws instead). ✓
- Local HTTP fallback only in dev. ✓ (but see SSR `127.0.0.1` fallback and layout docs link — PARTIAL)
- No `window` during SSR: `typeof`-guarded. ✓
- Shared API resolver: `getApiBase()` used for all authenticated paths; **two public-endpoint exceptions** remain. PARTIAL

---

## Declaration

```text
DEPLOYMENT_CONFIGURATION = PARTIAL
```
Required before staging: (1) S3-backed storage in staging config, (2) `fastembed`/`aioboto3` added to dependencies, (3) remove the two localhost fallbacks, (4) decide CI ruff strategy (fix or gate the lint step), (5) run `alembic upgrade head` against the managed Postgres once provisioned.
