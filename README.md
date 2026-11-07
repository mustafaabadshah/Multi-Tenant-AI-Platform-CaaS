# Multi-Tenant AI Platform-CaaS — Enterprise Multi-Tenant AI Knowledge & Chatbot Platform

A production-oriented, multi-tenant AI chatbot SaaS platform foundation built for individuals, educational institutions, enterprises, and research organizations.

## Overview

The **Multi-Tenant AI Platform-CaaS** is architected as a security-first modular monolith supporting:
- Dual-mode tenancy (Individual Workspaces & Enterprise Organization Workspaces).
- Fine-grained Role-Based Access Control (RBAC) and tenant isolation.
- Organization hierarchy: Departments, Employee Groups, Memberships, Invitations.
- Knowledge base foundation with multi-format ingestion (PDF, DOCX, TXT, CSV, XLSX, PPTX, JSON, SQL, Images/OCR).
- **Pluggable Vector Stores:** Native PostgreSQL `pgvector`, standalone `Qdrant`, and vectorless `PostgreSQL FTS`.
- **Extensible Embedding System:** `omniroute` (Local AI Gateway), `openai` (BYOK), `local` (CPU feature projection), and `mock` (deterministic test provider).
- **Hybrid Retrieval Engine:** Reciprocal Rank Fusion (RRF) combining dense semantic search and lexical full-text keyword ranking with citation provenance and secondary security authorization.
- Modern Enterprise Next.js App Router frontend with real-time workspace switching, document inspection, retrieval configuration, search preview sandbox, and index telemetry.

---

## Architecture Stack

| Layer | Technology | Key Details |
|---|---|---|
| **Frontend** | Next.js 16+ (App Router), TypeScript | Tailwind CSS, Lucide icons, Linear × Apple Notes design, React Hook Form, Zod |
| **Backend** | Python 3.12+, FastAPI | Asynchronous endpoints, Pydantic v2 schemas, Dependency Injection |
| **Database** | PostgreSQL 16+ | SQLAlchemy 2.0 (Async), Alembic migrations, composite foreign keys |
| **Vector Storage** | pgvector / Qdrant / FTS | Three configurable storage adapters with payload isolation |
| **Retrieval Engine** | Hybrid RRF / FTS / Semantic | Reciprocal Rank Fusion, provenance citations, secondary security authorizer |
| **Embeddings** | OmniRoute / OpenAI / Local CPU | SHA-256 chunk hashing, idempotency, Fernet secret encryption |
| **Auth & Security** | Argon2id / JWT | Provider-agnostic auth, tenant context middleware, cross-tenant security suite |
| **AI Gateway** | OmniRoute Gateway | Local AI router at `http://localhost:20128/v1` with dynamic model fallback |
| **Infrastructure** | Docker Compose | Multi-container setup with profiles for `vector`, `workers`, `observability`, `full` |

---

## Directory Structure

```text
.
├── frontend/                   # Next.js App Router TypeScript frontend
│   ├── app/                    # App routes: (auth), dashboard, workspace, knowledge, etc.
│   │   └── dashboard/knowledge # Document ingestion, retrieval settings, preview sandbox, index status
│   ├── components/             # Reusable UI components & layouts
│   ├── lib/api.ts              # Typed API client with Milestone 01, 02, 03 endpoints
│   └── types/                  # Shared TypeScript interfaces
├── backend/                    # FastAPI asynchronous modular monolith
│   ├── app/
│   │   ├── api/v1/             # Versioned REST API routers (/retrieval, /embedding-providers, /vector-stores)
│   │   ├── core/               # Configuration, security, AES/Fernet encryption, hashing, constants
│   │   ├── database/           # Async SQLAlchemy session and Base
│   │   ├── models/             # Relational domain models (KnowledgeBase, Document, ChunkEmbedding, RetrievalConfig)
│   │   ├── schemas/            # Pydantic v2 request/response schemas
│   │   ├── embeddings/         # Base provider interface, registry, and OmniRoute/OpenAI/Local/Mock providers
│   │   ├── vectorstores/       # pgvector, Qdrant, and PostgreSQL FTS vector adapters
│   │   ├── retrieval/          # Lexical, semantic, and hybrid RRF retrieval engine, citations, authorization
│   │   ├── repositories/       # Tenant-isolated repository pattern
│   │   ├── middleware/         # Tenant context & audit middleware
│   │   └── services/           # Ingestion pipeline, OCR registry, chunking, and worker lifecycle
│   ├── tests/                  # 61+ Pytest test suite (auth, rbac, tenant isolation, hybrid retrieval, security)
│   ├── alembic/                # Database migrations (0001_initial, 0002_ingestion, 0003_embeddings_and_vector_stores)
│   └── pyproject.toml          # Poetry / pip project dependencies
├── infrastructure/             # Dockerfiles and initialization scripts
├── docs/                       # Comprehensive architectural documentation
├── docker-compose.yml          # Container orchestration with profiles: core, vector, workers, observability, full
├── .env.example                # Environment variables template
└── AGENTS.md                   # Agent developer and engineering guidelines
```

---

## Operating Configurations & Modes

The platform can run in four primary retrieval modes:

### 1. Vectorless Mode (PostgreSQL FTS Only)
Zero vector database or embedding provider required. Document chunks are parsed, chunked, and indexed directly with PostgreSQL full-text search (`to_tsvector`, `plainto_tsquery`, and `ts_rank_cd`).
```powershell
# Set environment in backend/.env:
DEFAULT_RETRIEVAL_MODE="lexical"
DEFAULT_VECTOR_STORE="fts"
```

### 2. Native PostgreSQL + pgvector
Dense vector similarity search directly within PostgreSQL using native cosine distance (`<=>`).
```powershell
# Run with pgvector Docker container:
docker compose up -d postgres backend frontend
# Or with local PostgreSQL:
DEFAULT_RETRIEVAL_MODE="semantic"
DEFAULT_VECTOR_STORE="pgvector"
```

### 3. Dedicated Qdrant Vector Store
Independent vector database engine with payload indexing and strict tenant-scoped filtering (`tenant_id`, `knowledge_base_id`, `embedding_version`).
```powershell
# Launch Qdrant profile:
docker compose --profile vector up -d
# Set configuration:
DEFAULT_VECTOR_STORE="qdrant"
QDRANT_URL="http://localhost:6333"
```

### 4. Hybrid Retrieval (Lexical + Semantic RRF)
Combines PostgreSQL FTS and vector candidates using Reciprocal Rank Fusion ($RRF(d) = \sum \frac{1}{k + rank_r(d)}$).
```powershell
DEFAULT_RETRIEVAL_MODE="hybrid"
DEFAULT_VECTOR_STORE="pgvector"
RRF_K_CONSTANT=60
```

---

## Quick Start (Local Development)

### 1. Prerequisites
- Python 3.12+
- Node.js 20+ (Node.js 24 installed)
- Docker Desktop (optional for containerized PostgreSQL, Qdrant, Redis)

### 2. Environment Setup
```powershell
Copy-Item .env.example .env
```

### 3. Backend Setup
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup
```powershell
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Automated Testing & Security Matrix

The platform includes an extensive automated test suite covering positive flows, negative security isolation, and cross-tenant leakage prevention:

```powershell
cd backend
.\.venv\Scripts\pytest -v
```

**Key Security Verification Suites:**
- `tests/test_retrieval_security.py`:
  - `test_cross_tenant_vector_isolation`: Tenant A cannot search or retrieve Tenant B's vectors.
  - `test_cross_tenant_fts_isolation`: Tenant A cannot search or retrieve Tenant B's FTS chunks.
  - `test_department_isolation_blocks_unauthorized_employee`: Department-restricted documents are invisible to employees outside that department.
  - `test_deleted_documents_excluded_from_retrieval`: Deleted or deactivated documents are excluded immediately.
  - `test_hybrid_retrieval_does_not_reintroduce_unauthorized_candidates`: Hybrid fusion cannot resurrect unauthorized candidates from either channel.
- `tests/test_tenant_isolation_security.py`: Roster, department, role, and storage traversal attacks blocked.

---

## Health & Readiness Verification

- Application Health: `GET http://localhost:8000/health`
- Database & Service Readiness: `GET http://localhost:8000/ready`
- Interactive OpenAPI Docs: `GET http://localhost:8000/docs`
- Embedding Providers Metadata: `GET http://localhost:8000/api/v1/embedding-providers`
- Vector Stores Metadata: `GET http://localhost:8000/api/v1/vector-stores`

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
