# Docker Environment Audit & Host Resource Preflight

**Project:** Multi-Tenant AI Platform / CaaS  
**Workspace:** `E:\MM Office\Multi-Tanant-CaaS`  
**Execution Date:** 2026-11-08  
**Audit Status:** **NOT RUN — ENVIRONMENT CONSTRAINT**

---

## 1. Host Machine Environment

* **Operating System:** Windows 11 Home / Windows NT 10.0
* **CPU:** Intel Core i3-7100U @ 2.40 GHz (2 cores, 4 logical processors)
* **GPU:** Intel HD Graphics 620 (Integrated, no dedicated VRAM)
* **Total Physical RAM:** 8,102 MB (7.91 GB)
* **Available Physical RAM:** **467.7 MB – 1,057.8 MB** (Actively consumed by OS, browser sessions, and IDE)
* **Memory Safety Rule:** Machine requires $\ge 2,048$ MB free physical RAM to start Docker Desktop and containerized database workloads safely without memory thrashing or system instability.

---

## 2. Docker & WSL2 Diagnostic Findings

1. **Docker CLI & Client Tooling:**
   * Docker Client: `v25.0.3` (API: `1.44`, Go: `go1.21.6`)
   * Docker Compose: `v2.24.6-desktop.1`
   * Executable Location: `C:\Program Files\Docker\Docker\Docker Desktop.exe`
2. **WSL2 Subsystems:**
   * `docker-desktop-data`: Version 2 (State: `Stopped`)
   * `docker-desktop`: Version 2 (State: `Stopped`)
3. **Windows Service Status:**
   * Service Name: `com.docker.service`
   * Current Status: `Stopped`
   * StartType: `Manual`
   * Service Elevation: Direct `Start-Service` invocation without elevated administrator rights is blocked by Windows UAC.
4. **Daemon Pipe Connectivity:**
   * Error: `error during connect: Get "http://%2F%2F.%2Fpipe%2Fdocker_engine/v1.24/info": open //./pipe/docker_engine: The system cannot find the file specified.`
   * Cause: Docker Desktop engine is not running. Launching `Docker Desktop.exe` in user session under $< 1$ GB available RAM fails to initialize the WSL2 VM safely.

---

## 3. Preserved Isolated Compose Profiles

The project includes pre-configured, isolated Docker Compose profiles with conservative resource limits:

### PostgreSQL 16 + pgvector Profile (`docker-compose.m05-postgres.yml`)
* **Image:** `pgvector/pgvector:pg16`
* **Container:** `mmaip-m05-postgres`
* **Port:** `5433` (non-standard to avoid host port conflicts)
* **Memory Limit:** `512M`
* **Verification Command:**
  ```powershell
  docker compose -f docker-compose.m05-postgres.yml up -d
  pytest tests/integration/test_postgres_connection.py tests/integration/test_postgres_migrations.py tests/integration/test_pgvector_operations.py tests/integration/test_postgres_fts.py tests/integration/test_postgres_tenant_isolation.py -v
  docker compose -f docker-compose.m05-postgres.yml down -v
  ```

### Qdrant Vector Database Profile (`docker-compose.m05-qdrant.yml`)
* **Image:** `qdrant/qdrant:v1.9.0`
* **Container:** `mmaip-m05-qdrant`
* **Ports:** `6333` (HTTP), `6334` (gRPC)
* **Memory Limit:** `512M`
* **Verification Command:**
  ```powershell
  docker compose -f docker-compose.m05-qdrant.yml up -d
  pytest tests/integration/test_qdrant_live_integration.py -v
  docker compose -f docker-compose.m05-qdrant.yml down -v
  ```

---

## 4. Closure Requirements Prior to Staging Deployment

To close the live infrastructure gate:
1. Transfer or run this repository on a CI runner or machine with $\ge 4$ GB free RAM.
2. Ensure Docker Desktop is launched with administrator privileges.
3. Execute the preserved commands above sequentially.
