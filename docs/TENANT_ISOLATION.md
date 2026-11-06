# MM AI Platform — Tenant Isolation Specification & Verification Standard

## 1. Zero-Leakage Tenant Isolation Mandate

In the MM AI Platform, tenant isolation is the highest-priority architectural requirement. A multi-tenant platform must guarantee under all circumstances that one customer's private data, organizational structure, employees, assistants, and documents are inaccessible to another customer.

### The 8 Non-Negotiable Isolation Rules:
1. **Never trust frontend tenant IDs:** Any tenant ID supplied via URL, query parameter, or `X-Tenant-ID` header must be validated against `tenant_memberships` for the authenticated user.
2. **Never query without tenant scoping:** Every query for tenant-owned entities must include `tenant_id = :active_tenant_id`.
3. **Zero cross-tenant employee/department access:** Users in Tenant A can never view, list, or alter departments or members in Tenant B.
4. **No cross-tenant foreign key relationships:** A resource (e.g., knowledge base or assistant) belonging to Tenant A cannot link to a department or user belonging to Tenant B.
5. **Never expose storage paths:** File system paths (e.g. `/data/storage/tenant_a/...`) are strictly internal and never returned in API payloads.
6. **No cross-tenant setting modifications:** Tenant configuration, quotas, and provider keys can only be altered by authenticated members with `tenant.update` permission within that specific tenant.
7. **No unrestricted DB connections for user requests:** Database sessions for ordinary user requests enforce tenant parameters and cannot bypass authorization filters.
8. **Explicit background worker scoping:** Asynchronous tasks (ingestion jobs, OCR tasks) must store and re-bind the explicit `tenant_id` context upon execution.

---

## 2. Multi-Layer Enforcement Architecture

```mermaid
graph TD
    subgraph Layer1 [1. Transport & Authentication Layer]
        L1A[FastAPI Dependency Injection]
        L1B[Tenant Resolution Middleware]
        L1A -->|Validate JWT| L1B
        L1B -->|Validate (user_id, tenant_id)| L1OK[TenantContext Established]
    end

    subgraph Layer2 [2. Business & Service Layer]
        L2A[RBAC Permission Validator]
        L2B[Domain Service Boundaries]
        L1OK --> L2A
        L2A --> L2B
    end

    subgraph Layer3 [3. Data Access Layer]
        L3A[TenantScopedRepository Base Class]
        L3B[Mandatory tenant_id filter injection]
        L2B --> L3A
        L3A --> L3B
    end

    subgraph Layer4 [4. Database Integrity Layer]
        L4A[Composite Unique Constraints]
        L4B[PostgreSQL Row Level Security - RLS]
        L3B --> L4A
        L3B --> L4B
    end
```

---

## 3. Implementation Details

### 3.1 TenantScopedRepository Pattern
Every repository handling tenant-scoped entities inherits from `TenantScopedRepository[ModelType]`:
```python
class TenantScopedRepository(Generic[T]):
    def __init__(self, model: type[T], session: AsyncSession, tenant_id: UUID):
        self.model = model
        self.session = session
        self.tenant_id = tenant_id

    async def get_by_id(self, entity_id: UUID) -> T | None:
        query = select(self.model).where(
            self.model.id == entity_id,
            self.model.tenant_id == self.tenant_id
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def list(self, limit: int = 50, offset: int = 0) -> list[T]:
        query = select(self.model).where(
            self.model.tenant_id == self.tenant_id
        ).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())
```

### 3.2 Tenant Isolation Database Constraints
Composite unique constraints prevent cross-tenant naming collisions while locking each resource uniquely to its tenant:
```sql
ALTER TABLE departments 
ADD CONSTRAINT uq_departments_tenant_name UNIQUE (tenant_id, name);

ALTER TABLE assistants 
ADD CONSTRAINT uq_assistants_tenant_slug UNIQUE (tenant_id, slug);

ALTER TABLE knowledge_bases 
ADD CONSTRAINT uq_knowledge_bases_tenant_name UNIQUE (tenant_id, name);
```

---

## 4. Negative Security Regression Matrix

To ensure that tenant boundaries cannot be breached, the automated test suite (`backend/tests/test_tenant_isolation_security.py`) executes the following negative test matrix on every CI run:

| Attack Vector | Test Case | Expected Response | Result Verification |
|---|---|---|---|
| **Cross-Tenant Read** | User B attempts `GET /api/v1/departments/{dept_a_id}` with `X-Tenant-ID: Tenant_A` | `403 Forbidden` | No membership in Tenant A |
| **Forged Header Read** | User B attempts `GET /api/v1/departments/{dept_a_id}` with `X-Tenant-ID: Tenant_B` | `404 Not Found` | Department does not exist in Tenant B |
| **Cross-Tenant Update** | User B attempts `PATCH /api/v1/departments/{dept_a_id}` with `X-Tenant-ID: Tenant_B` | `404 Not Found` | Target record not updated |
| **Cross-Tenant Delete** | User B attempts `DELETE /api/v1/departments/{dept_a_id}` | `404 Not Found` / `403 Forbidden` | Target record remains intact |
| **Cross-Tenant Member Alter** | User B attempts to change role of Tenant A employee | `403 Forbidden` / `404 Not Found` | Role unchanged |
| **Guessed Resource UUID** | User B calls API with valid UUID of Tenant A assistant | `404 Not Found` | No metadata or existence leaked |
| **Privilege Escalation** | Employee in Tenant A attempts `POST /api/v1/departments` | `403 Forbidden` | Insufficient permissions (`department.create`) |
| **Spoofed Tenant Creation** | User attempts to insert record with arbitrary `tenant_id` | `403 Forbidden` | Backend overrides `tenant_id` from verified session |
