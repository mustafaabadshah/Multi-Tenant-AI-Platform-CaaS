# M11 Stage 7 — Backend Dependency Lockfile

**Status:** `LOCKFILE_STATUS = GENERATED_AND_VALIDATED`

- **Date:** 2026-11-12
- **Scope:** `backend/` Python dependencies, Docker image build, Render build command
- **No git mutations, no cloud deploys, no real secrets, no project dependency upgrades**
- **Python:** CPython 3.12.3 (local Windows venv), deployment target `python:3.12-slim`

---

## 1. Starting Point

`backend/pyproject.toml`:

| Item | Value |
| --- | --- |
| Build backend | `setuptools.build_meta` |
| Build requires | `setuptools>=68.0`, `wheel` |
| Project | `mmaip-backend==0.1.0`, editable package `app*` |
| `requires-python` | `>=3.12` |
| Runtime dependencies | 28 requirement lines (transitively 102 locked entries) |
| Optional group | `dev` = `pytest`, `pytest-asyncio`, `ruff`, `mypy` (transitively 113 locked entries) |
| Pytest config | `asyncio_mode = "auto"`, session-scoped loops, `testpaths = ["tests"]`, `postgres_integration` / `qdrant_integration` markers |

Deployment paths before this change:

- `infrastructure/docker/backend.Dockerfile`: `COPY pyproject.toml` then `pip install -e .` — every build re-resolved unpinned ranges and fetched build isolation tooling.
- `render.yaml`: `rootDir: backend`, `buildCommand: "pip install -e ."` — same unpinned resolution on every deploy.
- Docker build context is `./backend` (`docker-compose.yml`), so a lock at `backend/requirements.lock` is available at the context root. `backend/.dockerignore` does not exclude it.

---

## 2. Tool Selection

| Tool | Version | Decision |
| --- | --- | --- |
| `uv` | 0.12.15 | **Chosen** — available on PATH, `uv pip compile` provides pip-compatible output |
| pip | 26.3 (venv) | Used only for validation (`--dry-run`, `pip check`) |
| pip-tools | not installed | Not needed; no tooling was installed |

No packages were installed or upgraded in `backend/.venv`. No pip-tools installation was necessary.

---

## 3. Lock Files Generated

| File | Package entries | Lines | SHA-256 lines | Size | SHA-256 (file) |
| --- | ---: | ---: | ---: | ---: | --- |
| `backend/requirements.lock` | 102 (97 unconditional + 5 marker-conditional) | 3,300 | 2,991 | 260,957 B | `78FA081C0DD01B00DBBE20F644558A32C0449D730684890D1BD54C4829B5164D` |
| `backend/requirements-dev.lock` | 113 | 3,606 | 3,269 | 285,240 B | `ACC666C68FB303028D4ED5605F8AB1D5825FB9C10F3C76E333507175010C0E55` |

Generation commands (run from the repository root):

```powershell
uv pip compile backend/pyproject.toml --universal --python-version 3.12 --generate-hashes --output-file backend/requirements.lock
uv pip compile backend/pyproject.toml --extra dev --universal --python-version 3.12 --generate-hashes --output-file backend/requirements-dev.lock
```

Key properties:

- **Runtime lock:** `pyproject.toml` runtime dependencies only. No dev/test tools.
- **Dev lock:** runtime dependencies **plus** the `dev` optional group (standard `--extra dev` semantics). It is a superset intended for developer/CI environments, not used by the deployment image.
- **Self-exclusion:** `uv pip compile pyproject.toml` compiles the project's *dependencies* and does not emit the local `mmaip-backend` project itself. The only self-reference is the annotation `# via mmaip-backend (backend/pyproject.toml)`. Verified: no line starts with `mmaip-backend==`.
- **Deterministic pins:** every entry is `name==version` with SHA-256 hashes for all artifacts; `--require-hashes` is therefore enforceable.
- **Universal resolution:** `--universal` + `--python-version 3.12` produces one lock that covers Windows and Linux. Platform-specific entries carry markers (`colorama`/`win32-setctime` → Windows only, `uvloop` → non-Windows, plus `hf-xet` architecture and `pycparser` implementation markers). No `python_version` markers are present because the lock targets the supported CPython 3.12 runtime.

Resolution drift versus the current venv (resolver selected the newest versions allowed by `pyproject.toml`; nothing was installed):

| Package | Installed | Lock |
| --- | --- | --- |
| `fastapi` | 0.162.0 | 0.162.5 |
| `annotated-doc` | 0.0.5 | 0.0.6 |
| `click` | 8.5.0 | 8.5.1 |
| `filelock` | 4.2.9 | 4.2.10 |
| `sqlglot` | 30.30.0 | 30.31.0 |

All other runtime pins match the installed venv exactly (97 of 102), including `sqlalchemy==2.1.8`, `aioboto3==15.5.0`, `fastembed==0.9.1`, `alembic==1.20.1`, `qdrant-client==1.20.0`.

---

## 4. Deployment Build Changes

### `infrastructure/docker/backend.Dockerfile`

```dockerfile
COPY pyproject.toml requirements.lock /app/
RUN pip install --require-hashes -r requirements.lock

COPY . /app/
RUN pip install --no-deps -e .
```

- Dependencies are installed from the hashed lock **before** application source is copied, preserving layer caching.
- `--require-hashes` rejects any artifact not pinned in the lock.
- `pip install --no-deps -e .` installs only the local `app` package and cannot re-resolve or upgrade the locked set.
- The previous `pip install --upgrade pip` was removed: upgrading pip on every build is a non-deterministic network step. The base image's pip is used.
- Build context remains `./backend`; `.dockerignore` does not exclude `requirements.lock`.

### `render.yaml`

```yaml
buildCommand: "pip install --require-hashes -r requirements.lock && pip install --no-deps -e ."
```

`rootDir: backend` is unchanged, so `requirements.lock` resolves to `backend/requirements.lock`. YAML was parsed successfully after the edit (`services: 1`).

### Local development (unchanged)

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

This remains the supported developer workflow. Developers may optionally reproduce the locked environment with `pip install --require-hashes -r requirements.lock` and/or `pip install --require-hashes -r requirements-dev.lock`, but the deployment lock is not required for local development.

---

## 5. Validation Results

All commands were run against the existing venv; **no package was installed, removed, or upgraded**.

### 5.1 Hash-verified dry-run (Windows)

```powershell
backend\.venv\Scripts\python.exe -m pip install --dry-run --require-hashes -r backend/requirements.lock
```

- **Exit code: 0**
- All 102 entries resolved; hashes accepted; 97 already satisfied.
- Planned changes only: `Would install annotated-doc-0.0.6 click-8.5.1 fastapi-0.162.5 filelock-4.2.10 sqlglot-30.31.0`
- No hash mismatch, no missing-hash error.

### 5.2 Environment consistency

```powershell
backend\.venv\Scripts\python.exe -m pip check
```

Exact output:

```
No broken requirements found.
```

Exit code: `0`.

### 5.3 Import smoke test

```powershell
backend\.venv\Scripts\python.exe -c "import fastapi, sqlalchemy, aioboto3, fastembed, alembic; print('imports OK', fastapi.__version__, sqlalchemy.__version__, alembic.__version__)"
```

Exact output:

```
imports OK 0.162.0 2.1.8 1.20.1
```

Exit code: `0` (versions shown are the current venv, which the dry-run left untouched).

### 5.4 Byte-compilation

```powershell
cd backend
.\.venv\Scripts\python.exe -m compileall -q app
```

Exit code: `0` (no output).

### 5.5 Python 3.12 and cross-platform

- `python --version` → `Python 3.12.3`; lock generated with `--python-version 3.12`, matching `requires-python = ">=3.12"` and `python:3.12-slim`.
- Universal lock contains Windows and Linux artifacts with environment markers; no platform-exclusive pin is unconditional.
- Linux installability check (uv, foreign platform, no container started):

  ```powershell
  uv pip install --dry-run --python backend\.venv\Scripts\python.exe --python-platform x86_64-manylinux_2_28 --python-version 3.12 --require-hashes -r backend/requirements.lock
  ```

  **Exit code: 0** — every locked requirement resolved to a compatible Linux artifact, including `uvloop`, `onnxruntime`, `tokenizers`, `pymupdf`, `greenlet`, and `asyncpg`.

### 5.6 Dockerfile validation

`docker buildx build --check` and `docker build --check` are **NOT SUPPORTED** by the installed `docker buildx v0.12.1-desktop.4` (`unknown flag: --check`; the flag requires buildx >= 0.15). The Dockerfile was reviewed manually.

**Full image build: NOT RUN** (intentionally out of scope for this stage).

---

## 6. Residual Risk

1. **Lock vs tested venv drift:** the lock intentionally pins 5 patch-level versions newer than the current venv (table above). The deployment will install those, while local validation exercised the venv versions. A full test-suite run against a freshly locked environment is recommended before production promotion.
2. **Build isolation is not locked:** `pip install -e . --no-deps` still bootstraps `setuptools>=68.0` and `wheel` from the index in an isolated environment. These build requirements are not covered by `requirements.lock`. A future improvement is a build-requirements lock or `--no-build-isolation` with preinstalled pinned build tools.
3. **Regeneration is an update:** running `uv pip compile` again re-resolves the newest versions allowed by `pyproject.toml`. Treat lock regeneration as a dependency change: review the diff, run the test suite, then rebuild.
4. **Linux-only transitive pins:** entries such as `uvloop` are not exercised on the Windows venv. Universal resolution plus the `x86_64-manylinux_2_28` dry-run mitigate, but not fully replace, a Linux CI run.
5. **Hash strictness:** a deploy fails closed if the index cannot serve an artifact whose SHA-256 is in the lock. This is the intended supply-chain behavior.
6. **Python upper bound:** `pyproject.toml` allows any Python `>=3.12`, but the lock was compiled for 3.12. Do not deploy the lock on 3.13+ without regenerating it.

### Regeneration procedure

```powershell
# from the repository root
uv pip compile backend/pyproject.toml --universal --python-version 3.12 --generate-hashes --output-file backend/requirements.lock
uv pip compile backend/pyproject.toml --extra dev --universal --python-version 3.12 --generate-hashes --output-file backend/requirements-dev.lock

# review
git diff -- backend/requirements.lock backend/requirements-dev.lock
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Only run this as a deliberate dependency update. Then rebuild the Docker image (`docker compose build backend`) and redeploy.

---

## 7. Files Changed

| File | Change |
| --- | --- |
| `backend/requirements.lock` | **New** — runtime lock, 3,300 lines, hashed |
| `backend/requirements-dev.lock` | **New** — runtime + dev lock, 3,606 lines, hashed |
| `infrastructure/docker/backend.Dockerfile` | Lock-first install; editable install with `--no-deps` |
| `render.yaml` | `buildCommand` uses the hashed lock |
| `docs/m11/M11_BACKEND_DEPENDENCY_LOCKFILE.md` | **New** — this document |

No git add/commit/push was performed. No cloud deployment, no secret access, no project dependency upgrade.