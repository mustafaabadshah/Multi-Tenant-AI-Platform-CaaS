# Staging Readiness Operational Checklist

**Milestone:** M05 Staging Gate  
**Target Environments:** Render (Backend API + Managed PostgreSQL 16) & Vercel (Next.js Frontend)

---

## 1. Mandatory Infrastructure & Environment Checks

- [ ] **Physical RAM:** Host / runner has $\ge 2,048$ MB free physical memory for live container tests.
- [ ] **Docker Engine:** Docker daemon verified responsive via `docker info`.
- [ ] **Live Integration Tests:** All 17 tests in `backend/tests/integration/` passed against live PostgreSQL 16 (pgvector) and Qdrant.
- [ ] **Database Migrations:** `alembic upgrade head` verified clean from revision 0001 through 0004.
- [ ] **Environment Secrets:** `SECRET_KEY`, `JWT_SECRET`, and `SECRET_ENCRYPTION_KEY` generated cryptographically and set in Render environment.
- [ ] **Client Secrets Boundary:** Verified that only `NEXT_PUBLIC_API_URL` is exposed in frontend Vercel environment.
- [ ] **Dual Database URLs:** `DATABASE_URL` (asyncpg) and `DATABASE_SYNC_URL` (psycopg2) configured for FastAPI and Alembic respectively.
- [ ] **CORS Configuration:** `CORS_ORIGINS` configured and verified with Vercel frontend URL.

---

## 2. Mandatory Data Persistence & Recovery Checks

- [ ] **Relational Backup Script:** `infrastructure/scripts/backup-postgres.ps1` tested and produces valid `.dump` and `.sha256` checksum files.
- [ ] **Original File Binary Backup:** `STORAGE_PATH` persistent volume snapshotting or S3 bucket replication configured concurrently with database backups.
- [ ] **Encryption Key Recovery:** Encryption keys backed up securely in enterprise vault separate from database dumps.
- [ ] **Qdrant Rebuild Procedure:** Re-indexing pipeline verified idempotent from PostgreSQL source of truth.

---

## 3. Mandatory Security & Code Quality Checks

- [ ] **Full Offline Suite:** All 144 offline backend tests passing (`pytest tests -m "not postgres_integration and not qdrant_integration"`).
- [ ] **Frontend Build:** `npm run build` static compilation passing with 15/15 pages and 0 TypeScript errors.
- [ ] **Static Code Analysis:** `ruff check .` passing with 0 errors.
- [ ] **User Authorization:** Staging deployment authorized by explicit user confirmation.
