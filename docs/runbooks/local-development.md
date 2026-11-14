# Local Development Runbook

**Environment:** Windows 11 (PowerShell) / Linux / macOS  
**Prerequisites:** Python 3.12+, Node.js 20+, Git

---

## 1. Backend Setup

1. **Navigate to backend and create virtual environment:**
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```powershell
   pip install -e ".[dev]"
   ```

3. **Configure environment:**
   Create `backend/.env` from `.env.example`:
   ```dotenv
   SECRET_KEY=local-dev-secret-key-32-bytes-minimum
   JWT_SECRET=local-dev-jwt-secret-32-bytes-minimum
   SECRET_ENCRYPTION_KEY=AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA=
   DATABASE_URL=sqlite+aiosqlite:///./test.db
   LLM_BASE_URL=http://localhost:20128/v1
   OMNIROUTE_API_KEY=mock-key
   ```

4. **Run database migrations:**
   ```powershell
   alembic upgrade head
   ```

5. **Start backend development server:**
   ```powershell
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   * Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`
   * Health Check: `http://127.0.0.1:8000/health`

---

## 2. Frontend Setup

1. **Navigate to frontend and install packages:**
   ```powershell
   cd frontend
   npm install
   ```

2. **Configure environment:**
   Create `frontend/.env.local`:
   ```dotenv
   NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1
   ```

3. **Start frontend development server:**
   ```powershell
   npm run dev
   ```
   * Web Application: `http://localhost:3000`

---

## 3. Running Automated Tests

* **Run all offline backend tests:**
  ```powershell
  cd backend
  pytest tests -m "not postgres_integration and not qdrant_integration" -v
  ```

* **Run frontend build and lint:**
  ```powershell
  cd frontend
  npm run lint
  npm run build
  ```
