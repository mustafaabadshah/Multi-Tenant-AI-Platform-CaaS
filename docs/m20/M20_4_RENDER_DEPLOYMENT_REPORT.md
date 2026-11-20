# M20.4 — Render Staging Deployment Report

| Service | Render Service ID | Plan / Runtime | Deployed Commit SHA | Deploy ID | Deploy Status |
|---|---|---|---|---|---|
| `mmaip-backend` | `srv-dbrk57gn74is73fqo4k0` | Free Docker Web Service (Oregon) | `a0cd98c039c43a5f7e191bdf279c01874a820ce9` | `dep-dbtaqf6i0phs73f6sl1g` | **LIVE (succeeded)** |
| `mmaip-frontend` | `srv-dbrkthcipgvc739d6oh0` | Free Node / Next.js 16 Web Service (Oregon) | `a0cd98c039c43a5f7e191bdf279c01874a820ce9` | `dep-dbtasnl6e07s73buk9ag` | **LIVE (succeeded)** |

---

## 1. Backend Service Verification (`mmaip-backend`)

- **Deployed SHA:** `a0cd98c039c43a5f7e191bdf279c01874a820ce9`
- **Deploy Trigger:** Manual CLI trigger with `--commit $M20_RELEASE_SHA --confirm --wait`
- **Startup Command:** `exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1` (no startup migration race condition)
- **Auto-Deploy Status:** `autoDeploy: false`

### Live Probes:
1. `GET https://mmaip-backend.onrender.com/health`
   ```http
   HTTP/1.1 200 OK
   {"status":"healthy","timestamp":"2026-11-16T07:17:07.220215Z","version":"0.1.0"}
   ```
2. `GET https://mmaip-backend.onrender.com/ready`
   ```http
   HTTP/1.1 200 OK
   {"status":"ready","database":"connected","timestamp":"2026-11-16T07:17:07.533671Z"}
   ```

---

## 2. Frontend Service Verification (`mmaip-frontend`)

- **Deployed SHA:** `a0cd98c039c43a5f7e191bdf279c01874a820ce9`
- **Deploy Trigger:** Manual CLI trigger with `--commit $M20_RELEASE_SHA --confirm --wait`
- **Auto-Deploy Status:** `autoDeploy: false`

### Live Route Probes:
- `GET https://mmaip-frontend.onrender.com/login` → `200 OK` (Content length: 11,382)
- `GET https://mmaip-frontend.onrender.com/dashboard/integrations` → `200 OK` (Content length: 8,367)
- `GET https://mmaip-frontend.onrender.com/dashboard/tools` → `200 OK` (Content length: 8,352)
- `GET https://mmaip-frontend.onrender.com/dashboard/assistants` → `200 OK` (Content length: 8,611)
- `GET https://mmaip-frontend.onrender.com/dashboard/conversations` → `200 OK` (Content length: 8,368)
- `GET https://mmaip-frontend.onrender.com/dashboard/observability` → `200 OK` (Content length: 8,369)

---

## 3. Coordinated Rollout State

Both frontend and backend services are synchronously deployed to identical commit `a0cd98c039c43a5f7e191bdf279c01874a820ce9`, fully integrated with Neon PostgreSQL 16 schema revision `0016_m20_2_assistant_tools_config`.
