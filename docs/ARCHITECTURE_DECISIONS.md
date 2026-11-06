# MM AI Platform — Architecture Decision Records (ADR)

This document tracks significant architectural decisions made during the design and implementation of the MM AI Platform.

---

## ADR-001: Adoption of Modular Monolith Architecture
- **Status:** Accepted
- **Context:** An enterprise AI platform requires strong domain boundaries between identity, tenancy, knowledge ingestion, vector search, and chat orchestration. Microservices introduce premature operational complexity, distributed transaction overhead, and deployment friction for local development.
- **Decision:** Build the platform as a modular monolith in FastAPI. Internal domain modules maintain strict encapsulation through well-defined repositories and schemas.
- **Consequences:** Low latency in-process calls, single-command local development, simplified transaction boundaries, and a clean future extraction path into microservices if scaling necessitates it.

---

## ADR-002: Unified Dual-Mode Tenancy Model
- **Status:** Accepted
- **Context:** The platform serves individual power users (students, solo researchers) as well as complex enterprise organizations (universities, enterprises with departments and groups). Creating two separate database models creates schema duplication and migration headaches.
- **Decision:** Use a single `tenants` table with a `type` discriminator (`INDIVIDUAL` vs `ORGANIZATION`). When `type = 'ORGANIZATION'`, an associated `organizations` row holds enterprise-specific metadata. Individual workspaces automatically bind the owner without requiring department configuration.
- **Consequences:** Common authorization, assistant management, and knowledge indexing logic across all workspace types, while cleanly isolating organization hierarchies.

---

## ADR-003: Argon2id for Password Hashing
- **Status:** Accepted
- **Context:** Secure credential storage requires memory-hard and time-hard hashing resistant to GPU-accelerated brute force attacks.
- **Decision:** Standardize on **Argon2id** (via `pwdlib[argon2]` / `passlib`) as the primary password hashing mechanism.
- **Consequences:** Top-tier security meeting OWASP guidelines. Negligible overhead for authentication endpoints.

---

## ADR-004: OmniRoute Local AI Gateway Standard
- **Status:** Accepted
- **Context:** Directly hardcoding vendor SDKs (OpenAI, Anthropic, Google) locks the platform into specific cloud providers, creates key management hazards, and complicates local development without internet or cloud credentials.
- **Decision:** Adopt **OmniRoute Gateway** (`http://localhost:20128/v1`) using standard OpenAI client wire protocols with `model="auto"` as default.
- **Consequences:** Transparent dynamic model routing, local provider fallback, unified token tracking, and consistent environment variable configuration (`LLM_BASE_URL`, `OMNIROUTE_API_KEY`).

---

## ADR-005: Defense-in-Depth Tenant Isolation
- **Status:** Accepted
- **Context:** Multi-tenant SaaS platforms face catastrophic risk if cross-tenant data leaks occur.
- **Decision:** Enforce isolation at 4 distinct layers:
  1. API dependency: Verifies user membership in requested tenant header.
  2. RBAC service: Validates role permissions within tenant.
  3. Repositories: Mandates `WHERE tenant_id = :active_tenant_id` on all queries.
  4. Database: Composite unique keys and PostgreSQL Row Level Security (RLS) policies.
- **Consequences:** Eliminates Single Point of Failure (SPOF) for security. Even if an engineer omits a query filter, RLS and DB constraints prevent cross-tenant exposure.

---

## ADR-006: Asynchronous SQLAlchemy 2.0 with Pluggable Drivers
- **Status:** Accepted
- **Context:** High-concurrency AI workloads benefit from non-blocking I/O. Furthermore, local test runners on machines with limited RAM benefit from in-memory/file-based drivers.
- **Decision:** Utilize async SQLAlchemy 2.0 syntax (`select()`, `AsyncSession`). Production uses `asyncpg` with PostgreSQL; unit tests and local lightweight prototyping can seamlessly use `aiosqlite`.
- **Consequences:** Maximum concurrency for async API endpoints, ultra-fast test execution (~sub-second), and full relational compatibility.
