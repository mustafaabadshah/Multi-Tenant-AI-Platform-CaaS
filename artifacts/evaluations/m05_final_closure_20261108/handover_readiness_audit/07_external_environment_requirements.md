# Milestone 05 External Execution — Linux Environment & Dependency Requirements

**Project:** Multi-Tenant AI Platform / CaaS  
**Audit Phase:** Phase 8 — External Environment & Dependencies Audit  
**Auditor:** Senior DevOps / SRE Auditor  

---

## 1. Operating System & Infrastructure Prerequisites

The external runner must satisfy the following baseline specifications:

| Requirement | Minimum | Recommended | Rationale |
|---|---|---|---|
| **OS Distribution** | Ubuntu 22.04 LTS / Debian 12 | Ubuntu 24.04 LTS | Standard kernel support for cgroups v2 |
| **Available RAM** | **4,096 MB** | **7,168 MB+** | Guarantees $\ge 2,048$ MB runner preflight threshold |
| **Available Disk** | **5,120 MB** (5 GB) | **10 GB+ SSD** | Space for container images, venv, and logs |
| **Docker Engine** | Docker 24.0+ | Docker 26.0+ | Required for compose healthchecks |
| **Docker Compose** | Compose v2.20+ | Compose v2.27+ | Supports Compose v2 specification |
| **Python** | Python 3.12.0+ | Python 3.12.3+ | Required by `pyproject.toml` (`requires-python = ">=3.12"`) |

---

## 2. Package Dependency Audit (`pyproject.toml`)

### 2.1 The Installation Pitfall
In `README_RUNNER.md`, Step 2 recommends:
```bash
pip install -e .
```
In `backend/pyproject.toml`:
- Core runtime dependencies (`fastapi`, `sqlalchemy`, `asyncpg`, `qdrant-client`, `pgvector`, etc.) are under `[project.dependencies]`.
- **`pytest` and `pytest-asyncio` are declared exclusively under `[project.optional-dependencies] dev` (lines 40–46).**

### 2.2 Corrected Command
If the operator runs `pip install -e .`, Pytest will **not** be installed, and running `python -m pytest` will crash with:  
`No module named pytest`.

The operator **MUST** install the development dependencies:
```bash
pip install -e ".[dev]"
```

---

## 3. Host System Packages & User Permissions

On minimal or fresh Ubuntu server installations, the following packages must be present before executing the runner:

```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip unzip curl tar
```

### Docker Socket Group Permission:
The user running the tests must have permission to access `/var/run/docker.sock`:
```bash
# Verify user is in docker group
groups | grep -q docker || {
    sudo usermod -aG docker $USER
    newgrp docker
}
docker info >/dev/null || { echo "Docker socket permission error"; exit 1; }
```
