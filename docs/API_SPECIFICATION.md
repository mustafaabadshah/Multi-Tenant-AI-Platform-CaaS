# MM AI Platform — REST API Specification (v1)

## 1. Global Conventions

- **Base URL:** `/api/v1`
- **Wire Format:** JSON (`application/json; charset=utf-8`)
- **Authentication:** HTTP Bearer token (`Authorization: Bearer <JWT_ACCESS_TOKEN>`)
- **Active Tenant Context:** Transmitted via header `X-Tenant-ID: <UUID>` on all tenant-scoped routes.
- **Timestamp Standard:** ISO-8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`)

---

## 2. Global System Endpoints

### 2.1 Health Check
- **`GET /health`**
  - **Auth:** None (Public)
  - **Description:** Verifies application process liveness.
  - **Response (200 OK):**
    ```json
    {
      "status": "healthy",
      "timestamp": "2026-11-06T13:30:00Z",
      "version": "1.0.0"
    }
    ```

### 2.2 Readiness Check
- **`GET /ready`**
  - **Auth:** None (Public)
  - **Description:** Verifies database connectivity and essential dependency readiness.
  - **Response (200 OK):**
    ```json
    {
      "status": "ready",
      "database": "connected",
      "timestamp": "2026-11-06T13:30:00Z"
    }
    ```
  - **Response (503 Service Unavailable):** Returned if database connection fails.

---

## 3. Authentication & Account (`/api/v1/auth`)

| Endpoint | Method | Auth | Permission | Description |
|---|---|---|---|---|
| `/auth/register` | `POST` | None | None | Register a new user account & create default individual workspace |
| `/auth/login` | `POST` | None | None | Authenticate with email/password, return access & refresh tokens |
| `/auth/refresh` | `POST` | Refresh Token | None | Issue a new access token using a valid refresh token |
| `/auth/me` | `GET` | Bearer | None | Get current authenticated user profile & accessible workspaces |
| `/auth/logout` | `POST` | Bearer | None | Invalidate active user session/tokens |

---

## 4. Tenant & Workspace Management (`/api/v1/tenants`)

| Endpoint | Method | Auth | Permission | Description |
|---|---|---|---|---|
| `/tenants` | `GET` | Bearer | None | List all tenants/workspaces the current user belongs to |
| `/tenants` | `POST` | Bearer | None | Create a new workspace (Individual or Organization) |
| `/tenants/{id}` | `GET` | Bearer | `tenant.read` | Get details and settings of the specified workspace |
| `/tenants/{id}` | `PATCH` | Bearer | `tenant.update` | Update workspace settings/name |
| `/tenants/{id}/switch` | `POST` | Bearer | None | Set active workspace context for session |

---

## 5. Organization Management (`/api/v1/organizations`)

| Endpoint | Method | Auth | Permission | Description |
|---|---|---|---|---|
| `/organizations/{id}` | `GET` | Bearer | `tenant.read` | Get organization corporate profile |
| `/organizations/{id}` | `PATCH` | Bearer | `tenant.update` | Update organization corporate details |

---

## 6. Member & Invitation Management (`/api/v1/members`)

*Header required: `X-Tenant-ID: <UUID>`*

| Endpoint | Method | Auth | Permission | Description |
|---|---|---|---|---|
| `/members` | `GET` | Bearer | `member.read` | List active employees and members in the tenant |
| `/members/invite` | `POST` | Bearer | `member.invite` | Send invitation email to new employee |
| `/members/{id}` | `PATCH` | Bearer | `member.update` | Update member role, department, or status |
| `/members/{id}` | `DELETE` | Bearer | `member.remove` | Remove employee from organization tenant |

---

## 7. Department Management (`/api/v1/departments`)

*Header required: `X-Tenant-ID: <UUID>`*

| Endpoint | Method | Auth | Permission | Description |
|---|---|---|---|---|
| `/departments` | `GET` | Bearer | `member.read` | List departments within active organization |
| `/departments` | `POST` | Bearer | `department.create` | Create a new department (e.g. HR, Engineering) |
| `/departments/{id}` | `GET` | Bearer | `member.read` | Get department details and member roster |
| `/departments/{id}` | `PATCH` | Bearer | `department.update` | Update department name or description |
| `/departments/{id}` | `DELETE` | Bearer | `department.delete` | Delete department (reassigns members to unassigned) |

---

## 8. Employee Groups (`/api/v1/groups`)

*Header required: `X-Tenant-ID: <UUID>`*

| Endpoint | Method | Auth | Permission | Description |
|---|---|---|---|---|
| `/groups` | `GET` | Bearer | `member.read` | List employee groups in active tenant |
| `/groups` | `POST` | Bearer | `department.create` | Create an employee group |
| `/groups/{id}/members` | `POST` | Bearer | `member.update` | Add employee to group |
| `/groups/{id}/members/{user_id}` | `DELETE` | Bearer | `member.update` | Remove employee from group |

---

## 9. RBAC & Roles (`/api/v1/roles`, `/api/v1/permissions`)

| Endpoint | Method | Auth | Permission | Description |
|---|---|---|---|---|
| `/roles` | `GET` | Bearer | `member.read` | List all available roles and assigned permissions |
| `/permissions` | `GET` | Bearer | `member.read` | List all system permissions |

---

## 10. Audit Logs (`/api/v1/audit`)

*Header required: `X-Tenant-ID: <UUID>`*

| Endpoint | Method | Auth | Permission | Description |
|---|---|---|---|---|
| `/audit` | `GET` | Bearer | `audit.read` | Query paginated audit log events for active tenant |

---

## 11. Assistant & Knowledge Base Foundations (`/api/v1/assistants`, `/api/v1/knowledge`)

*Header required: `X-Tenant-ID: <UUID>`*

| Endpoint | Method | Auth | Permission | Description |
|---|---|---|---|---|
| `/assistants` | `GET` | Bearer | `assistant.read` | List assistants configured in active tenant |
| `/assistants` | `POST` | Bearer | `assistant.create` | Create a new assistant |
| `/knowledge` | `GET` | Bearer | `knowledge.read` | List knowledge bases in active tenant |
| `/knowledge` | `POST` | Bearer | `knowledge.upload` | Create a knowledge base container |
| `/knowledge/{kb_id}/documents` | `POST` | Bearer | `document.upload` | Multipart upload files into knowledge base |
| `/knowledge/{kb_id}/documents` | `GET` | Bearer | `document.read` | List documents in knowledge base |
| `/knowledge/{kb_id}/ingestion-config` | `GET` | Bearer | `document.read` | Get KB chunking & OCR configuration |
| `/knowledge/{kb_id}/ingestion-config` | `PATCH` | Bearer | `ingestion.configure` | Update KB chunking & OCR configuration |
| `/documents/{doc_id}` | `GET` | Bearer | `document.read` | Get document metadata and status |
| `/documents/{doc_id}` | `DELETE` | Bearer | `document.delete` | Delete document and cascade chunks |
| `/documents/{doc_id}/versions` | `GET` | Bearer | `document.read` | List document version history |
| `/documents/{doc_id}/reprocess` | `POST` | Bearer | `document.reprocess` | Trigger asynchronous reprocessing |
| `/documents/{doc_id}/content` | `GET` | Bearer | `document.read_content` | Preview extracted text and structure |
| `/documents/{doc_id}/chunks` | `GET` | Bearer | `document.read_chunks` | Inspect generated document chunks |
| `/documents/{doc_id}/processing-history` | `GET` | Bearer | `document.read` | View document event audit trail |
| `/ingestion/jobs` | `GET` | Bearer | `ingestion.read` | List ingestion jobs with filters |
| `/ingestion/jobs/{job_id}` | `GET` | Bearer | `ingestion.read` | Get ingestion job status and progress |
| `/ingestion/jobs/{job_id}/retry` | `POST` | Bearer | `ingestion.retry` | Retry failed or cancelled job |
| `/ingestion/jobs/{job_id}/cancel` | `POST` | Bearer | `ingestion.cancel` | Cancel active or queued job |

---

## 12. Standard Error Responses

All error responses strictly follow this RFC 7807-compatible structure:
```json
{
  "error": {
    "code": "TENANT_ACCESS_DENIED",
    "message": "User is not a member of the requested tenant or tenant is inactive.",
    "status": 403,
    "timestamp": "2026-11-06T13:30:00Z"
  }
}
```
Standard HTTP Status Codes:
- `400 Bad Request`: Validation failure or malformed payload.
- `401 Unauthorized`: Missing, expired, or invalid Bearer token.
- `403 Forbidden`: Authenticated user lacks required permission or tenant membership.
- `404 Not Found`: Entity does not exist OR belongs to another tenant (avoids leaking resource existence).
- `409 Conflict`: Unique constraint violation (e.g., duplicate slug or department name).
- `500 Internal Server Error`: Unhandled server exception.
