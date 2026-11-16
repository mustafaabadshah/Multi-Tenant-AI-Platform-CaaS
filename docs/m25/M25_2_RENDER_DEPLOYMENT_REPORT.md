# M25.2 — Render Deployment Report

## 1. Deployed Services Summary

| Service Name | Render Service ID | Service Type | Release Commit | Deploy ID | Status |
|---|---|---|---|---|---|
| `mmaip-backend` | `srv-dbrk57gn74is73fqo4k0` | Docker Web Service (Oregon, Free) | `c907594e3a53a7d1487109ecd8cc3f8f5de57e38` | `dep-dbtg71jm8hqs73are0gg` | **Live** |
| `mmaip-frontend` | `srv-dbrkthcipgvc739d6oh0` | Static / Web Service (Free) | `08f4505526ea1c20115fc7d041056d65a6c3b9a3` | `dep-dbtg1jetlv9c73f96gf0` | **Live** |

## 2. Health & Readiness Verification
- `GET https://mmaip-backend.onrender.com/health` -> HTTP 200 `{"status":"healthy","version":"0.1.0"}`
- `GET https://mmaip-backend.onrender.com/ready` -> HTTP 200 `{"status":"ready","database":"connected"}`
- Database connection pool verified active against Neon staging.
