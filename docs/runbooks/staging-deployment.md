# Staging Deployment Runbook — Render & Vercel

**Status:** CONFIGURATION READY (DEPLOYMENT PENDING AUTHORIZATION)  
**Target Infrastructure:** Render (Backend + PostgreSQL 16) & Vercel (Frontend Next.js)

---

## 1. Secrets Generation Procedure

Prior to staging deployment, generate cryptographically secure tokens:

```powershell
# 1. Application Secret Key (32 bytes hex)
python -c "import secrets; print(secrets.token_hex(32))"

# 2. JWT Signing Secret (32 bytes hex)
python -c "import secrets; print(secrets.token_hex(32))"

# 3. Fernet Encryption Key (32 url-safe base64 bytes)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 2. Backend Deployment on Render

1. **Connect Repository to Render:**
   * Select Blueprint deployment using `render.yaml`.
2. **Declared Services in `render.yaml`:**
   * `mmaip-postgres`: Managed PostgreSQL 16 database.
   * `mmaip-backend`: Python Web Service.
     * Build Command: `pip install -e .`
     * Pre-Deploy Command: `alembic upgrade head` (automatically applies schema migrations)
     * Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`
     * Health Check: `/health`
3. **Set Environment Variables in Render Dashboard:**
   * `SECRET_KEY`: `<generated-secret-key>`
   * `JWT_SECRET`: `<generated-jwt-secret>`
   * `SECRET_ENCRYPTION_KEY`: `<generated-fernet-key>`
   * `CORS_ORIGINS`: `https://mmaip-frontend.vercel.app`

---

## 3. Frontend Deployment on Vercel

1. **Connect Repository to Vercel:**
   * Root Directory: `frontend`
   * Framework Preset: `Next.js`
2. **Environment Variables:**
   * `NEXT_PUBLIC_API_URL`: `https://mmaip-backend.onrender.com/api/v1`
3. **Security Headers (`frontend/vercel.json`):**
   * Automatically enforces `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.

---

## 4. Rollback Strategy

* **Application Rollback:** Revert commit in Git or roll back to previous deployment in Render/Vercel dashboard.
* **Database Rollback:** If migration rollback is required:
  ```bash
  alembic downgrade -1
  ```
