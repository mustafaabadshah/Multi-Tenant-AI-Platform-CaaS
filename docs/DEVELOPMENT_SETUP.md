# MM AI Platform — Local Development Setup Guide

This guide describes how to configure, run, and test the MM AI Platform in a local development environment.

---

## 1. Prerequisites

- **Operating System:** Windows 10/11, macOS, or Linux
- **Python:** 3.12+ installed and available on PATH
- **Node.js:** Node.js 20+ (Node.js 24 recommended) and npm
- **Docker & Docker Compose:** Optional for local PostgreSQL, Qdrant, and Redis services
- **System Resources:** Designed to run smoothly on machines with 8 GB RAM and no dedicated GPU

---

## 2. Environment Configuration

Copy the example environment template into a local `.env` file at the root of the repository:

```bash
cp .env.example .env
```

Review and adjust any values as necessary:
- `SECRET_KEY`: Secret key used for cryptographic signing.
- `JWT_SECRET`: Secret key used for signing JWT tokens.
- `DATABASE_URL`: Defaults to `postgresql+asyncpg://postgres:postgres@localhost:5432/mmaip_dev` (or SQLite `sqlite+aiosqlite:///./data/mmaip_dev.db` for rapid local prototyping without Docker).
- `LLM_BASE_URL`: Defaults to `http://localhost:20128/v1` for the OmniRoute Gateway.

---

## 3. Backend Setup

### 3.1 Create and Activate Virtual Environment

**Windows (PowerShell):**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS (Bash):**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### 3.2 Install Dependencies

```bash
pip install -e .
```

### 3.3 Apply Database Migrations

```bash
alembic upgrade head
```

### 3.4 Start FastAPI Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API Base: `http://localhost:8000/api/v1`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/health`
- Readiness Endpoint: `http://localhost:8000/ready`

---

## 4. Frontend Setup

### 4.1 Install Dependencies

```bash
cd frontend
npm install
```

### 4.2 Run Next.js Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the SaaS dashboard.

---

## 5. Docker Compose Infrastructure

For containerized workflows, Docker Compose orchestrates the platform services:

### 5.1 Core Services (PostgreSQL, Backend, Frontend)
```bash
docker compose up -d
```

### 5.2 Optional Profiles (Worker, Qdrant, Redis, Phoenix)
```bash
# Start background ingestion worker
docker compose --profile worker up -d

# Start with Qdrant vector store and Redis
docker compose --profile qdrant --profile redis up -d

# Start with Phoenix LLM observability
docker compose --profile phoenix up -d
```

---

## 6. Background Ingestion Worker (Local Development)

To run the background ingestion worker standalone on Windows PowerShell:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.services.ingestion.worker
```

The worker continuously polls for `QUEUED` ingestion jobs, coordinates parser selection, handles OCR if required, executes chunking, and persists structured extraction results.

---

## 7. Running Tests

### 7.1 Backend Tests (Pytest)

Windows PowerShell:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v
```

This runs all 43 tests across both Milestone 01 and Milestone 02:
- **`test_auth.py`**: Identity, JWT token generation, refresh tokens, and session handling.
- **`test_password_hashing.py`**: Argon2id password security.
- **`test_tenants.py`**: Multi-tenant workspace lifecycle.
- **`test_organizations_and_departments.py`**: Department, employee group, and membership tests.
- **`test_rbac_permissions.py`**: Granular role permissions enforcement.
- **`test_tenant_isolation_security.py`**: Negative cross-tenant security regression suite.
- **`test_parsers.py`**: All 9 file formats (PDF, DOCX, XLSX, PPTX, CSV, JSON, SQL with zero execution, TXT, Markdown).
- **`test_chunking.py`**: Recursive, Markdown Header-Aware, Token-Bounded, and Structured chunking strategies.
- **`test_ocr.py`**: Tesseract fallback, Badho OCR honest placeholder, and scanned PDF detection.
- **`test_ingestion_pipeline.py`**: End-to-end document upload, parsing, chunking, and content inspection.
- **`test_document_tenant_isolation.py`**: Negative tenant security tests for documents, chunks, and jobs.

### 7.2 Frontend Verification
```powershell
cd frontend
npm run lint
npm run build
```
