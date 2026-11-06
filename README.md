# Multi-Tenant AI Platform-CaaS — Enterprise Multi-Tenant AI Knowledge & Chatbot Platform

A production-oriented, multi-tenant AI chatbot SaaS platform foundation built for individuals, educational institutions, enterprises, and research organizations.

## Overview

The **Multi-Tenant AI Platform-CaaS** is architected as a security-first modular monolith supporting:
- Dual-mode tenancy (Individual Workspaces & Enterprise Organization Workspaces).
- Fine-grained Role-Based Access Control (RBAC) and tenant isolation.
- Organization hierarchy: Departments, Employee Groups, Memberships, Invitations.
- Knowledge base foundation ready for multi-format ingestion (PDF, DOCX, TXT, CSV, XLSX, PPTX, JSON, SQL, Images/OCR).
- Extensible AI routing via **OmniRoute** AI Gateway (`http://localhost:20128/v1`) with pluggable vector storage (PostgreSQL FTS, pgvector, Qdrant).
- Modern Enterprise Next.js App Router frontend with real-time workspace switching and management.

---

## Architecture Stack

| Layer | Technology | Key Details |
|---|---|---|
| **Frontend** | Next.js 14+ (App Router), TypeScript | Tailwind CSS, Lucide icons, React Hook Form, Zod |
| **Backend** | Python 3.12+, FastAPI | Asynchronous endpoints, Pydantic v2 schemas, Dependency Injection |
| **Database** | PostgreSQL 16+ | SQLAlchemy 2.0 (Async), Alembic migrations, composite foreign keys |
| **Auth & Security** | Argon2id / JWT | Provider-agnostic auth, tenant context middleware, negative security test suite |
| **AI Gateway** | OmniRoute Gateway | Local AI router at `http://localhost:20128/v1` with dynamic model fallback |
| **Infrastructure** | Docker Compose | Multi-container setup with profiles for Qdrant, Redis, Phoenix |

---

## Directory Structure

```text
.
├── frontend/                   # Next.js App Router TypeScript frontend
│   ├── app/                    # App routes: (auth), dashboard, workspace, employees, etc.
│   ├── components/             # Reusable UI components & layouts
│   ├── features/               # Domain feature modules (auth, tenants, members, etc.)
│   ├── hooks/                  # Custom React hooks (useAuth, useTenant)
│   ├── lib/                    # API client, tokens, utils
│   └── types/                  # Shared TypeScript interfaces
├── backend/                    # FastAPI asynchronous modular monolith
│   ├── app/
│   │   ├── api/v1/             # Versioned REST API routers
│   │   ├── core/               # Configuration, security, hashing, constants
│   │   ├── database/           # Async SQLAlchemy session and Base
│   │   ├── models/             # Relational domain models
│   │   ├── schemas/            # Pydantic v2 request/response schemas
│   │   ├── repositories/       # Tenant-isolated repository pattern
│   │   ├── middleware/         # Tenant context & audit middleware
│   │   └── [domain modules]/   # auth, tenants, organizations, members, departments, etc.
│   ├── tests/                  # Pytest test suite (auth, rbac, tenant isolation)
│   ├── alembic/                # Database migrations
│   └── pyproject.toml          # Poetry / pip project dependencies
├── infrastructure/             # Dockerfiles and initialization scripts
│   ├── docker/
│   └── scripts/
├── docs/                       # Comprehensive architectural documentation
│   ├── ARCHITECTURE.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_SPECIFICATION.md
│   ├── SECURITY_MODEL.md
│   ├── TENANT_ISOLATION.md
│   ├── IMPLEMENTATION_ROADMAP.md
│   ├── DEVELOPMENT_SETUP.md
│   └── ARCHITECTURE_DECISIONS.md
├── docker-compose.yml          # Container orchestration with optional profiles
├── .env.example                # Environment variables template
└── AGENTS.md                   # Agent developer and engineering guidelines
```

---

## Quick Start (Local Development)

### 1. Prerequisites
- Python 3.12+
- Node.js 20+ (Node.js 24 installed)
- Docker Desktop (optional for containerized PostgreSQL, Qdrant, Redis)

### 2. Environment Setup
```bash
cp .env.example .env
```

### 3. Backend Setup
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -e .
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Health & Readiness Verification

- Application Health: `GET http://localhost:8000/health`
- Database & Service Readiness: `GET http://localhost:8000/ready`
- Interactive OpenAPI Docs: `GET http://localhost:8000/docs`

---

## Automated Testing

```bash
# Run backend unit, RBAC, and tenant isolation tests
cd backend
pytest -v
```

---

## Documentation

Full architectural specifications are located in [`docs/`](./docs/):
- [Architecture Overview](docs/ARCHITECTURE.md)
- [Database Schema & ERD](docs/DATABASE_SCHEMA.md)
- [API Specification](docs/API_SPECIFICATION.md)
- [Security Model & RBAC](docs/SECURITY_MODEL.md)
- [Tenant Isolation Guarantees](docs/TENANT_ISOLATION.md)
- [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP.md)
- [Development Setup Guide](docs/DEVELOPMENT_SETUP.md)
- [Architecture Decisions Record (ADR)](docs/ARCHITECTURE_DECISIONS.md)
