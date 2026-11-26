# Milestone M10 Stage 5 — Deployment Readiness & Infrastructure Blueprint

## 1. Executive Summary

Milestone M10 Stage 5 establishes production deployment blueprints for the **Multi-Tenant AI Platform (CaaS)**. The platform is designed for cloud-native deployment with horizontal scaling across **Vercel** (Next.js Frontend) and **Render** (FastAPI Backend, Managed PostgreSQL, and Redis).

---

## 2. Target Deployment Topologies

```
┌─────────────────────────────────┐        ┌───────────────────────────────────┐
│        Vercel Edge Network      │        │       Render Cloud Infrastructure │
│                                 │        │                                   │
│  Next.js 16 App Router Frontend ├───────>│  FastAPI Async Backend Replicas  │
│  - Static Asset Optimization    │  HTTPS │  - Uvicorn 4x Worker Process      │
│  - Partial Prerender (PPR)      │        │  - Modular Monolith (app.main)    │
│  - Embed Widget Host            │        │  - SSE Streaming Inference        │
└─────────────────────────────────┘        └─────────────────┬─────────────────┘
                                                             │
                              ┌──────────────────────────────┼──────────────────────────────┐
                              ▼                              ▼                              ▼
               ┌──────────────────────────────┐┌──────────────────────────────┐┌──────────────────────────────┐
               │    Managed PostgreSQL 16     ││         Managed Redis        ││      Qdrant Vector Cloud     │
               │  - Source of Truth Schemas   ││  - Distributed Quota Leases  ││  - HNSW Dense Vectors (1536) │
               │  - Composite Tenant Isolation││  - Rate Limiting Tokens      ││  - Multi-Tenant Payload Filters│
               │  - Encrypted Fernet Secrets  ││  - Real-Time Ephemeral State ││  - Hybrid FTS + Dense RRF    │
               └──────────────────────────────┘└──────────────────────────────┘└──────────────────────────────┘
```

---

## 3. Frontend Deployment Blueprint (Vercel)

### 3.1 Project Settings
- **Framework Preset**: Next.js
- **Root Directory**: `frontend`
- **Build Command**: `next build`
- **Output Directory**: `.next`
- **Node.js Version**: 20.x

### 3.2 Environment Variables (Vercel Production)
| Variable Name | Required | Example / Description |
|---------------|----------|-----------------------|
| `NEXT_PUBLIC_API_URL` | Yes | `https://api.platform.yourdomain.com` (Target backend API) |
| `NODE_ENV` | Yes | `production` |

### 3.3 CDN & Caching Strategy
- Static routes (`/`, `/login`, `/register`, `/dashboard/*`) are pre-rendered at build time with edge cache invalidation on code pushes.
- Dynamic assistant endpoints (`/p/[publicId]`, `/embed/[publicId]`) utilize partial prerendering with dynamic streaming for real-time SSE token delivery.

---

## 4. Backend Deployment Blueprint (Render)

### 4.1 Web Service Configuration
- **Environment**: Python 3.12
- **Build Command**:
  ```bash
  pip install --upgrade pip && pip install -r backend/requirements.txt && alembic upgrade head
  ```
- **Start Command**:
  ```bash
  uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --workers 4 --proxy-headers
  ```
- **Health Check Path**: `/health` (Expects HTTP 200 with JSON status indicators)
- **Auto-Deploy**: Enabled on branch `main`

### 4.2 Environment Variables (Render Production)
| Variable Name | Required | Example / Description |
|---------------|----------|-----------------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user:pass@dpg-xxx.render.com:5432/mmaip_prod` |
| `JWT_SECRET_KEY` | Yes | Cryptographically random 64-character hex string |
| `FERNET_SECRET_KEY` | Yes | URL-safe base64-encoded 32-byte key for BYOK encryption |
| `LLM_BASE_URL` | Yes | `http://localhost:20128/v1` (or production gateway URL) |
| `OMNIROUTE_API_KEY` | Yes | Secure API key for local or cloud OmniRoute gateway |
| `QDRANT_URL` | Yes | `https://xxx.cloud.qdrant.io:6333` |
| `QDRANT_API_KEY` | Yes | Cloud vector engine access token |
| `REDIS_URL` | Optional | `rediss://default:pass@redis.render.com:6379` |
| `CORS_ORIGINS` | Yes | `https://app.yourdomain.com,https://yourdomain.com` |

---

## 5. Network, SSL/TLS & CORS Security

### 5.1 Strict CORS Configuration
- Public endpoints (`/api/v1/public/*`, `/embed/*`) allow CORS access (`*`) with preflight caching (`max_age=86400`) to enable drop-in website widget embedding.
- Internal administrative and workspace endpoints (`/api/v1/dashboard/*`, `/api/v1/workspaces/*`, `/api/v1/providers/*`) restrict origins strictly to authenticated dashboard domains.

### 5.2 Security Headers (HTTP Response)
Render and Vercel edge proxies inject:
- `Strict-Transport-Security`: `max-age=63072000; includeSubDomains; preload`
- `X-Content-Type-Options`: `nosniff`
- `X-Frame-Options`: `DENY` (except `/embed/*` which sets `Content-Security-Policy: frame-ancestors *` to allow widget inclusion).
- `Referrer-Policy`: `strict-origin-when-cross-origin`

---

## 6. Preflight Checklist for Production Cutover

- [x] All 20 frontend routes compile cleanly in production build (`npm run build`).
- [x] Zero TypeScript errors in frontend (`tsc --noEmit`).
- [x] Zero TypeScript errors in SDK (`sdk/typescript/tsconfig.json`).
- [x] Full backend regression suite passes without failure.
- [x] Database migrations verified with composite tenant isolation constraints.
- [x] Environment variable templates documented in `.env.example`.
- [x] Health check endpoint operational on `/health`.
