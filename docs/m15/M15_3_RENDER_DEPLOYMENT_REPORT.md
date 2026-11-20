# M15.3 — Render Staging Deployment Report

## 1. Backend Deployment (`mmaip-backend`)

- **Service ID:** `srv-dbrk57gn74is73fqo4k0`
- **Plan:** Free Docker Web Service (Oregon)
- **Deployed Commit:** `089b632bb7d7e256f48c1280cfef881c3b6f38fd`
- **Deploy Trigger:** Render CLI manual deploy (`--commit 089b632bb7d7e256f48c1280cfef881c3b6f38fd --wait`)
- **Deploy ID:** `dep-dbsc4s56e07s739edo80`
- **Status:** **LIVE** (`succeeded`)

### Live Health and Readiness Probes:
1. `GET https://mmaip-backend.onrender.com/health`
   ```http
   HTTP/1.1 200 OK
   {"status":"healthy","timestamp":"2026-11-14T20:22:22.901209Z","version":"0.1.0"}
   ```
2. `GET https://mmaip-backend.onrender.com/ready`
   ```http
   HTTP/1.1 200 OK
   {"status":"ready","database":"connected","timestamp":"2026-11-14T20:22:31.148646Z"}
   ```

---

## 2. Frontend Deployment (`mmaip-frontend`)

- **Service ID:** `srv-dbrkthcipgvc739d6oh0`
- **Plan:** Free Node Web Service (Oregon)
- **Deployed Commit:** `089b632bb7d7e256f48c1280cfef881c3b6f38fd`
- **Deploy Trigger:** Render CLI manual deploy (`--commit 089b632bb7d7e256f48c1280cfef881c3b6f38fd --confirm --wait`)
- **Deploy ID:** `dep-dbsc878ae00c73d61ve0`
- **Status:** **LIVE** (`succeeded`)

### Live Route Probes:
1. `GET https://mmaip-frontend.onrender.com/login`
   ```http
   HTTP/1.1 200 OK
   ```
2. `GET https://mmaip-frontend.onrender.com/dashboard/observability`
   ```http
   HTTP/1.1 200 OK
   ```

---

## 3. Deployment Safety Verification

- **Auto-Deploy Status:** Both services remain configured with `autoDeploy: no` / `autoDeployTrigger: off`.
- **Instance Count:** 1 instance each on Free plan.
- **Secrets:** No secrets committed to Git, bundled into frontend client chunks, or exposed in deployment logs.
- **Topology:** Single coordinated release commit deployed to both backend and frontend.
