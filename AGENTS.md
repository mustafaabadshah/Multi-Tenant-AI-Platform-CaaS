# AGENTS.md — MM AI Platform Engineering Guidelines

This document outlines the strict architectural rules, security boundaries, and coding standards for all human and AI contributors working on the MM AI Platform.

---

## 1. Prime Directive: Multi-Tenant Isolation

1. **Never trust frontend tenant IDs:** Every request requiring tenant access MUST validate that the authenticated user possesses active membership in that tenant.
2. **Always scope repository queries:** Never execute `SELECT * FROM table WHERE id = :id` for tenant-owned entities. Queries must explicitly specify: `WHERE id = :id AND tenant_id = :active_tenant_id`.
3. **No cross-tenant relationships:** Departments, employee groups, assistants, knowledge bases, documents, and conversations must belong strictly to one tenant.
4. **Enforce composite integrity:** Where relational integrity is critical, use foreign keys that include `tenant_id` to prevent cross-tenant referencing at the database level.
5. **No administrative shortcuts:** Do not bypass tenant scoping in application code using raw queries or unauthenticated endpoints.

---

## 2. LLM Integration — OmniRoute Gateway

Per the platform architecture standard:
- Whenever AI/LLM functionality is added or configured, point to **OmniRoute** local gateway:
  - Base URL: `http://localhost:20128/v1` (via `LLM_BASE_URL` or default fallback)
  - Default Model: `auto`
  - Environment variable: `OMNIROUTE_API_KEY` (with fallback to `OPENAI_API_KEY`)
- Do not hardcode vendor-specific single provider URLs (OpenAI, Anthropic) directly in business logic. Always use the OpenAI-compatible standard client pointing to OmniRoute.
- Prefer streaming (`stream: true`) for chat interactions.

---

## 3. Technology Stack Boundaries

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (Async), Pydantic v2, Alembic, Pytest.
- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, Lucide icons, React Hook Form, Zod.
- **Database:** PostgreSQL is the source of truth. SQLite is supported for fast local test suites.
- **Password Security:** Use Argon2id for password hashing. Never store or log plaintext passwords or API keys.
- **Modular Monolith:** Keep modules encapsulated within `backend/app/`. Do not introduce microservices or distributed RPC until enterprise scale demands it.

---

## 4. Coding Standards

### Backend (Python)
- Use standard asynchronous style (`async def`) for I/O operations (database, network, file storage).
- Validate all inputs using Pydantic v2 models with strict type annotations.
- Keep business logic in services/repositories; controllers (routers) must only handle HTTP mapping, authentication dependencies, and validation.
- All entities must have UUID primary keys and UTC timestamps (`created_at`, `updated_at`).

### Frontend (TypeScript / Next.js)
- Use the Next.js App Router paradigm (`app/` directory).
- Separate server and client components cleanly (`"use client"` only when interactive state is required).
- Maintain responsive, enterprise-grade SaaS styling using Tailwind CSS.
- Provide descriptive empty states and clear error boundaries for all data-fetching views.

---

## 5. Security Testing Standard

Every new entity and endpoint must have:
- Positive tests (authorized user performs action successfully).
- Negative cross-tenant tests (user in Tenant A attempts to read/update/delete resource in Tenant B).
- Unauthorized role escalation tests (member without permission attempts admin action).
- Unauthenticated tests (401 response).

Never mark an architectural phase complete without passing the negative security regression suite.
