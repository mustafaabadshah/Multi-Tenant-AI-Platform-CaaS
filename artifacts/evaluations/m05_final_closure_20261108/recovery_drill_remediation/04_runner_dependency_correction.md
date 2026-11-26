# Milestone 05 — Runner Dependency & Packaging Instructions Correction

**Audit Phase:** Defect C Remediation  
**Date:** 2026-11-08  
**Target Document:** `README_RUNNER.md`  
**Configuration File:** `backend/pyproject.toml`  

---

## 1. Analysis of Dependency Specification

In `backend/pyproject.toml`:
```toml
[project]
dependencies = [
    "fastapi>=0.110.0",
    "sqlalchemy[asyncio]>=2.0.28",
    "asyncpg>=0.29.0",
    "qdrant-client>=1.9.0",
    "cryptography>=42.0.0",
    ...
]

[project.optional-dependencies]
dev = [
    "pytest>=8.1.0",
    "pytest-asyncio>=0.23.5",
    "ruff>=0.3.0",
    "mypy>=1.9.0",
]
```

### The Issue
Previous versions of `README_RUNNER.md` instructed the operator to execute:
```bash
pip install -e .
```
Because `pytest` and `pytest-asyncio` are located under `[project.optional-dependencies] dev`, installing without `[dev]` omits `pytest`. When the operator attempted to run `./infrastructure/scripts/run-live-integration-tests.sh`, python exited immediately with `ModuleNotFoundError: No module named pytest`.

---

## 2. Corrections Applied

1. **Updated Command:**
   ```bash
   pip install -e ".[dev]"
   ```
   This ensures `pytest`, `pytest-asyncio`, `ruff`, and `mypy` are installed in the runner virtual environment.

2. **System Prerequisites Documented:**
   Documented Ubuntu 22.04 / 24.04 LTS host package requirements:
   ```bash
   sudo apt-get update && sudo apt-get install -y python3-venv python3-pip unzip curl tar
   ```

3. **Packaging Sync:**
   The updated `README_RUNNER.md` was copied directly into `artifacts/evaluations/m05_final_closure_20261108/portable_runner_v2/README_RUNNER.md` and included inside `m05_live_test_snapshot_v2.zip`.
