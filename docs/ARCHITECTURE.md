# MM AI Platform — System Architecture

## 1. Architectural Philosophy

The **MM AI Platform** is designed as a **Modular Monolith** prioritizing:
1. **Security-First Multi-Tenancy:** Hard tenant isolation at every layer (database constraints, repository filters, middleware validation, and RBAC).
2. **Local-First & Resource Efficient:** Designed to operate smoothly on resource-constrained development environments (~8GB RAM, no dedicated GPU) without sacrificing enterprise production-readiness.
3. **Pluggable & Provider-Agnostic Extensibility:** Clean abstractions for vector stores (pgvector, Qdrant), LLMs (OmniRoute Gateway, OpenAI-compatible APIs), embeddings, and document parsers/OCR (Badho OCR, local parsers).

---

## 2. High-Level Component Topology

```mermaid
graph TD
    Client[Next.js Enterprise Frontend<br/>Tailwind CSS + App Router]
    
    subgraph Backend [FastAPI Modular Monolith]
        AuthMid[Auth & JWT Layer]
        TenantMid[Tenant Context & Membership Resolver]
        RBAC[RBAC & Permission Evaluator]
        
        subgraph Domains [Domain Modules]
            Identity[Identity & Users]
            Tenants[Tenants & Workspaces]
            Orgs[Organizations & Departments]
            Assistants[Assistants & Versions]
            Knowledge[Knowledge Bases & Documents]
            Audit[Audit Logs & Metrics]
        end
        
        Repo[Tenant-Scoped Repositories]
    end
    
    subgraph Storage [Persistent Storage & Data]
        Postgres[(PostgreSQL 16+<br/>Relational + FTS + RLS)]
        LocalFS[(Local File Storage)]
        QdrantOpt[(Optional Qdrant Vector DB)]
        RedisOpt[(Optional Redis Cache / Queue)]
    end
    
    subgraph AI [AI Routing & Gateways]
        OmniRoute[OmniRoute Local AI Gateway<br/>http://localhost:20128/v1]
        ExtLLM[External / Local LLM Providers]
    end

    Client -->|REST API + Bearer Token| AuthMid
    AuthMid --> TenantMid
    TenantMid --> RBAC
    RBAC --> Domains
    Domains --> Repo
    Repo --> Postgres
    Domains --> LocalFS
    Domains -.-> QdrantOpt
    Domains -.-> RedisOpt
    Domains -.-> OmniRoute
    OmniRoute -.-> ExtLLM
```

---

## 3. Backend Module Hierarchy

The backend is partitioned into cleanly bounded domains inside `backend/app/`:

```text
backend/app/
├── api/v1/                 # HTTP Transport layer (routers, parameter validation)
│   ├── auth.py             # /api/v1/auth
│   ├── users.py            # /api/v1/users
│   ├── tenants.py          # /api/v1/tenants
│   ├── organizations.py    # /api/v1/organizations
│   ├── members.py          # /api/v1/members
│   ├── departments.py      # /api/v1/departments
│   ├── groups.py           # /api/v1/groups
│   ├── roles.py            # /api/v1/roles
│   ├── permissions.py      # /api/v1/permissions
│   ├── assistants.py       # /api/v1/assistants
│   ├── knowledge.py        # /api/v1/knowledge
│   └── audit.py            # /api/v1/audit
├── core/                   # Cross-cutting foundational utilities
│   ├── config.py           # Pydantic v2 BaseSettings
│   ├── security.py         # Argon2id hashing, JWT creation & verification
│   └── constants.py        # System roles, default permissions, error codes
├── database/               # Database connectivity & session handling
│   ├── base.py             # SQLAlchemy DeclarativeBase
│   └── session.py          # Async engine, sessionmaker, dependency injection
├── middleware/             # Request lifecycle middleware
│   ├── tenant_context.py   # Extracts and validates X-Tenant-ID header
│   └── error_handler.py    # Standardized API error responses
├── models/                 # SQLAlchemy 2.0 ORM entities
│   ├── user.py
│   ├── tenant.py
│   ├── membership.py
│   ├── organization.py
│   ├── department.py
│   ├── group.py
│   ├── role.py
│   ├── permission.py
│   ├── assistant.py
│   ├── knowledge.py
│   ├── config.py
│   ├── conversation.py
│   └── administration.py
├── schemas/                # Pydantic v2 DTOs (Request / Response validation)
└── repositories/           # Encapsulated data-access layer with tenant filtering
```

---

## 4. Tenancy & Identity Architecture

Every workspace is represented by a `Tenant` entity of type:
1. `INDIVIDUAL`: Personal sandbox workspace tied to a single user.
2. `ORGANIZATION`: Enterprise workspace supporting hierarchical departments, employee groups, role assignments, and team collaboration.

A user may belong to multiple tenants. When calling tenant-scoped APIs:
1. The client supplies the desired workspace ID via the `X-Tenant-ID` header (or route parameter).
2. The authentication layer resolves the user from the `Authorization: Bearer <JWT>` token.
3. The tenancy resolver queries `tenant_memberships` ensuring the user has an `ACTIVE` membership in that tenant.
4. The user's role and granular permissions in that specific tenant are attached to the request context.
5. All downstream repository queries are scoped strictly by `tenant_id`.

---

---

## 5. Document Ingestion, Parsing, OCR & Chunking Architecture (Milestone 02)

### Storage Abstraction (`app.storage`)
Tenant-partitioned storage engine adhering to strict path containment.
- `StorageProvider` (Interface): defines `save`, `get`, `delete`, `exists`, `get_size`, `build_storage_key`.
- `LocalStorageProvider`: saves files under `./data/storage/tenants/{tenant_id}/kbs/{kb_id}/docs/{doc_id}/v{version_num}/{safe_filename}`. Detects and blocks directory traversal attempts.
- `S3StorageProvider`: Cloud-ready S3 / MinIO integration boundary.

### Parser Registry (`app.parsers`)
Independent parser implementations registered in `ParserRegistry` with magic byte / signature validation via `filetype`:
- **PDF (`PyMuPDF`)**: Page text, page numbers, metadata, scanned page heuristic.
- **DOCX (`python-docx`)**: Headings (h1..h4), paragraphs, table headers and rows.
- **XLSX (`openpyxl`)**: Sheet names, rows, columns, markdown tables.
- **PPTX (`python-pptx`)**: Slide text, titles, notes, slide tables.
- **CSV (`python csv`)**: Automatic delimiter sniffing (comma, semicolon, tab, pipe), header detection, rows.
- **JSON (`python json`)**: Nested JSON, JSON Lines (JSONL), flattened key-path traversal.
- **SQL (`sqlglot`)**: Static AST parsing of table definitions, columns, data types, primary keys, and views. Strictly ZERO execution against live databases.
- **TXT (`python stdlib`)**: UTF-8 and legacy encodings, paragraph grouping.
- **Markdown (`python stdlib`)**: Heading hierarchy (`#`, `##`, `###`), sections, code blocks.

### OCR Subsystem (`app.ocr`)
Provider-independent OCR abstraction:
- `TesseractOCRProvider`: CPU-based local OCR using `pytesseract` and PyMuPDF rendering (200 DPI). Detects missing binaries gracefully without crashing.
- `BadhoOCRProvider`: Honest integration placeholder documenting missing official API endpoint specification and authentication tokens; prevents sending documents to unverified endpoints.

### Chunking Engine (`app.chunking`)
Configurable strategies preserving source metadata:
1. **Recursive Character Chunking (`recursive`)**: Splitting along paragraph, sentence, and word boundaries with configurable chunk size and overlap.
2. **Markdown Header-Aware Chunking (`markdown`)**: Preserves heading hierarchy and attaches contextual heading paths (`Doc > Section > Subsection`) to chunks.
3. **Token-Bounded Chunking (`token`)**: Strictly limits chunks by token estimation without downloading heavy tokenizer models.
4. **Structured Document Chunking (`structured`)**: Keeps spreadsheet and table rows associated with their table headers on every chunk; preserves slide numbers and titles on presentation chunks.

Every generated chunk records: `tenant_id`, `knowledge_base_id`, `document_id`, `document_version_id`, `chunk_index`, `page_number`, `heading_path`, `source_filename`, `source_type`, `parser_version`, `chunking_strategy`, `chunk_hash`, `character_count`, and `token_count`.

### Background Processing & Ingestion Service (`app.services.ingestion`)
- State machine: `PENDING` -> `QUEUED` -> `PROCESSING` -> `OCR_REQUIRED` -> `CHUNKING` -> `COMPLETED` / `FAILED` / `CANCELLED`.
- Standalone polling worker (`app.services.ingestion.worker`) and asynchronous background tasks.
- Automatic retry with exponential backoff and max retry limits.
- Duplicate file upload detection using SHA-256 checksums within knowledge bases.

---

## 6. Extensibility Boundaries for Future Milestones

- **Vector Storage (Milestone 03):** An abstract `VectorStoreRepository` interface allows switching between PostgreSQL (FTS / pgvector), Qdrant, or in-memory vectors without altering application business logic.
- **LLM Gateway (Milestone 04):** Integrated via OmniRoute Gateway (`http://localhost:20128/v1`) using standard OpenAI client abstractions with dynamic model fallback (`model="auto"`).
