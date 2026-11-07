# Phase Zero: Baseline Test Results

**Date:** 2026-11-07  
**Test Suite:** Pytest 9.2.0, Python 3.12.3  
**Lint Tool:** Ruff 0.3.0  
**Frontend Tools:** ESLint 9, Next.js 16.4.5 (Turbopack)  

---

## 1. Backend Pytest Baseline

**Command:**
```powershell
cd backend
.\.venv\Scripts\pytest -v
```

**Results:**
- **Total Tests Collected:** 61
- **Passed:** 61 (100%)
- **Failed:** 0
- **Duration:** 74.66s

### Test Suite Breakdown:
- `tests/test_auth.py`: 5 passed
- `tests/test_chunking.py`: 6 passed
- `tests/test_document_tenant_isolation.py`: 2 passed
- `tests/test_embedding_providers.py`: 5 passed
- `tests/test_health.py`: 2 passed
- `tests/test_hybrid_retrieval.py`: 3 passed
- `tests/test_ingestion_pipeline.py`: 3 passed
- `tests/test_ingestion_to_embedding.py`: 2 passed
- `tests/test_ocr.py`: 4 passed
- `tests/test_organizations_and_departments.py`: 2 passed
- `tests/test_parsers.py`: 11 passed
- `tests/test_password_hashing.py`: 2 passed
- `tests/test_rbac_permissions.py`: 1 passed
- `tests/test_retrieval_security.py`: 5 passed
- `tests/test_tenant_isolation_security.py`: 5 passed
- `tests/test_tenants.py`: 2 passed
- `tests/test_vector_stores.py`: 3 passed

---

## 2. Backend Linter (Ruff)

**Command:**
```powershell
cd backend
.\.venv\Scripts\ruff check app tests
```

**Result:**
- `All checks passed!`
- 0 errors, 0 warnings.

---

## 3. Frontend Linter (ESLint)

**Command:**
```powershell
cd frontend
npm run lint
```

**Result:**
- 0 errors, 21 informational warnings (unused variables in template pages).
- Exit Code: 0.

---

## 4. Frontend Production Build (Next.js)

**Command:**
```powershell
cd frontend
npm run build
```

**Result:**
- `✓ Compiled successfully in 3.3s`
- `✓ Generating static pages using 3 workers (15/15) in 1898ms`
- All 15 routes generated cleanly as static artifacts.
- Exit Code: 0.

---

## 5. Environment & External Daemons Status

| Daemon / Service | Port | Host Status | Test Handling |
|---|---|---|---|
| Docker Daemon | Pipe / API | Stopped | Documented as offline; docker compose profiles ready |
| PostgreSQL / pgvector | 5432 | Stopped | In-engine SQL tests with SQLite unit simulation fallback |
| Qdrant Vector DB | 6333 | Stopped | Qdrant adapter unit tests pass; daemon marked `NOT RUN` |
| OmniRoute AI Gateway | 20128 | Stopped | Graceful offline warning; defaults to mock/local/BYOK |
