# M10 Git Integration - Stage 4: Dependency and Reproducibility Review

- **Timestamp (UTC):** 2026-11-12T07:10:54Z (execution window 07:10-07:20 UTC)
- **Host:** Windows 10 (win32), PowerShell 5.1, Node v24.14.1 / npm 11.11.0
- **Repository:** `E:\MM Office\Multi-Tanant-CaaS`
- **Branch / HEAD:** `main` / `9479847b846aaae43cb8f51e81cf18aaf2646d0f`
  (`feat(m08): implement Public Assistant Publishing, Embed Widgets, Developer API, and SDKs`)
- **Backend interpreter:** `backend\.venv\Scripts\python.exe` -> Python **3.12.3**
- **Execution mode:** READ-ONLY. No package installs, no upgrades, no lockfile generation, no model
  downloads, no cloud calls, no network fetches, no git mutations. Exactly one file written:
  this document.
- **What was NOT executed:** `npm ci`, `npm install`, `pip install`, `docker build`, `pip-compile`,
  `uv lock`, any model load. Static analysis only for those paths.

---

## 0. Verdict summary (read this first)

| Question | Answer |
|---|---|
| Do `aioboto3` and `fastembed` import in the backend venv? | **Yes** - `aioboto3` 15.5.0, `fastembed` 0.9.1 (import only; no model download) |
| `pip check` result | **`No broken requirements found.`** |
| Are both declared in `backend/pyproject.toml`? | **Yes**, but with **lower bounds only** (`aioboto3>=12.4.0`, `fastembed>=0.3.0`) |
| Are both imported lazily? | **Yes** - function-scope imports, module import never requires them |
| Backend lockfile? | **None** (no `poetry.lock`, `uv.lock`, `requirements*.txt`) |
| Frontend lockfile? | **`frontend/package-lock.json` present, v3, committed, in sync** -> `npm ci` viable |
| SDK lockfiles? | **None** (Python or TypeScript) |
| Is staging deployment safe without a backend lockfile? | **No - not reproducible.** Builds resolve latest-compatible versions at build time. Treat as explicit risk acceptance or fix before staging. |
| Safest next step | Generate **and commit** a backend lock (hashed requirements or `uv.lock`) in a **dedicated dependency-only change**, then point Render/Docker/CI at it. Not executed in this stage. |

---

## 1. Backend - `backend/pyproject.toml`

### 1.1 Build configuration

| Field | Value |
|---|---|
| `build-system.requires` | `["setuptools>=68.0", "wheel"]` |
| `build-backend` | `setuptools.build_meta` |
| `project.name` / `version` | `mmaip-backend` / `0.1.0` |
| `requires-python` | `>=3.12` |
| `project.readme` | `README.md` (**file does not exist** - see 2.5) |
| Package discovery | `[tool.setuptools.packages.find] where=["."] include=["app*"]` |
| Optional groups | only `dev` = `pytest>=8.1.0`, `pytest-asyncio>=0.23.5`, `ruff>=0.3.0`, `mypy>=1.9.0` |
| Tool config | ruff (py312, line-length 100, select E/F/I), pytest (`asyncio_mode=auto`, `testpaths=["tests"]`) |

There is no `[project.urls]`, no dependency-group/constraints mechanism, and no upper bound anywhere in
the file: **every runtime dependency is `>=` only**.

### 1.2 Declared runtime dependencies vs. installed versions

| Declaration (verbatim) | Installed | Headroom |
|---|---|---|
| `fastapi>=0.110.0` | 0.162.0 | major/minor free |
| `uvicorn[standard]>=0.28.0` | 0.54.0 | major free |
| `pydantic>=2.6.0` | 2.14.3 | major free (Pydantic 3) |
| `pydantic[email]>=2.6.0` | 2.14.3 | duplicate of the line above; harmless |
| `email-validator>=2.0.0` | 2.3.0 | |
| `pydantic-settings>=2.2.0` | 2.16.2 | |
| `sqlalchemy[asyncio]>=2.0.28` | 2.1.8 | |
| `greenlet>=3.0.0` | 3.5.6 | |
| `alembic>=1.13.1` | 1.20.1 | |
| `asyncpg>=0.29.0` | 0.32.0 | |
| `aiosqlite>=0.20.0` | 0.22.1 | |
| `argon2-cffi>=23.1.0` | 25.1.0 | |
| `pyjwt>=2.8.0` | 2.15.1 | |
| `python-multipart>=0.0.9` | 0.0.33 | |
| `httpx>=0.27.0` | 0.28.1 | |
| `PyMuPDF>=2.1.0` | 2.1 | |
| `python-docx>=1.2.0` | 1.2.0 | |
| `openpyxl>=3.1.5` | 3.1.5 | |
| `python-pptx>=1.0.2` | 1.0.2 | |
| `sqlglot>=30.30.0` | 30.30.0 | |
| `pytesseract>=0.3.13` | 0.3.13 | requires host `tesseract-ocr` binary |
| `pillow>=13.0.0` | 13.0.0 | |
| `filetype>=1.2.0` | 1.2.0 | |
| `pgvector>=0.2.5` | 0.5.1 | |
| `qdrant-client>=1.9.0` | 1.20.0 | pulls `grpcio`, `protobuf`, `portalocker`, `urllib3` |
| `cryptography>=42.0.0` | 50.0.2 | |
| **`aioboto3>=12.4.0`** | **15.5.0** | 3 majors of headroom |
| **`fastembed>=0.3.0`** | **0.9.1** | pre-1.0; 6 minor releases of API drift |

### 1.3 Verification commands (exact output)

Command 1 - interpreter:

```
> backend\.venv\Scripts\python.exe -c "import sys; print(sys.version); print(sys.executable)"
3.12.3 (tags/v3.12.3:f6650f9, Apr  9 2024, 14:05:25) [MSC v.1938 64 bit (AMD64)]
E:\MM Office\Multi-Tanant-CaaS\backend\.venv\Scripts\python.exe
```

Command 2 - import only (no model download performed):

```
> backend\.venv\Scripts\python.exe -c "import aioboto3, fastembed; ..."
import aioboto3 OK -> 15.5.0
import fastembed OK -> 0.9.1
```

Command 3 - `python -m pip check`:

```
> backend\.venv\Scripts\python.exe -m pip check
No broken requirements found.
```

Command 4 - `pip show fastembed aioboto3` (verbatim):

```
Name: fastembed
Version: 0.9.1
Summary: Fast, light, accurate library built for retrieval embedding generation
Home-page: https://github.com/qdrant/fastembed
Author: Qdrant Team, NirantK
Author-email: Qdrant Team <info@qdrant.tech>, NirantK <nirant.bits@gmail.com>
License-Expression: Apache-2.0
Location: E:\MM Office\Multi-Tanant-CaaS\backend\.venv\Lib\site-packages
Requires: huggingface-hub, loguru, mmh3, numpy, onnxruntime, pillow, py-rust-stemmers, requests, tokenizers, tqdm
Required-by: mmaip-backend
---
Name: aioboto3
Version: 15.5.0
Summary: Async boto3 wrapper
Home-page: https://github.com/terricain/aioboto3
Author:
Author-email: Terri Cain <terri@dolphincorp.co.uk>
License: Apache-2.0
Location: E:\MM Office\Multi-Tanant-CaaS\backend\.venv\Lib\site-packages
Requires: aiobotocore, aiofiles
Required-by: mmaip-backend
```

Installed package count in the venv (`pip list --format=freeze`): **114**.

Transitive versions that materially affect these two packages:

| Package | Installed | Bound enforced by upstream |
|---|---|---|
| `aiobotocore` | 2.25.1 | **`aioboto3==15.5.0` hard-pins `aiobotocore==2.25.1`** |
| `botocore` | 1.40.61 | via `aiobotocore` |
| `boto3` | 1.40.61 | via `aiobotocore[boto3]` |
| `onnxruntime` | 1.31.1 | `fastembed` 0.9.1: `>=1.17.0,!=1.20.0,!=1.24.0,!=1.24.1` on py3.12 |
| `numpy` | 2.5.4 | `fastembed`: `>=1.26` on py3.12 (no upper bound) |
| `huggingface-hub` | 1.33.0 | `fastembed`: `>=0.20,<2.0` (major 1.x drift inside the allowed window) |
| `tokenizers` | 0.23.3 | `fastembed`: `>=0.15,<1.0` |
| `pillow` | 13.0.0 | `fastembed`: `>=10.3,<14.0`; project pins `>=13.0.0` |

Note: `qdrant-client` 1.20.0 declares its `fastembed` extra as `fastembed>=0.9,<0.10`. The ecosystem's
tested fastembed window is therefore **0.9.x**, while this project allows anything from 0.3.0 upward.

### 1.4 Import strategy - lazy vs. unconditional (cited)

| Package | Import site | Kind | Assessment |
|---|---|---|---|
| `aioboto3` | `backend/app/storage/s3.py:56`, `:81`, `:103`, `:124`, `:148` | **Function-scope lazy** (inside each `save`/`get`/`delete`/`exists`/`get_url` path) | Correct: absent package cannot break app start |
| `fastembed` | `backend/app/embeddings/providers/sentence_transformer_provider.py:57` | **Function-scope lazy** (inside `_get_model`, first inference) | Correct for dependency isolation, but see failure mode below |

Module-level import chain is clean: `backend/app/storage/__init__.py:8` imports `S3StorageProvider`
eagerly, but `s3.py` only imports `aioboto3` inside methods, so `import app.main` succeeds without it.
No other module imports `fastembed`, `boto3`, `onnxruntime` or `TextEmbedding`.

### 1.5 Failure modes when the package is missing

**aioboto3 - clear and actionable.** Each call site raises with an install hint:

```
ImportError: aioboto3 is required for S3StorageProvider. Install it via `pip install aioboto3`.
```
(`backend/app/storage/s3.py:57-60` and the four sibling blocks). Raised at request time, not import time.
`S3StorageProvider._check_configured()` (`s3.py:45-50`) additionally fails fast with
`ValueError: S3 storage backend selected, but S3_BUCKET_NAME is not configured...`.

**fastembed - partially clear, with a silent-degradation hazard.** `_get_model` does:

1. `from fastembed import TextEmbedding` -> on `ImportError`: `pass` (silent) -> try `sentence_transformers`.
2. `sentence_transformers` is **not declared** in `pyproject.toml` and **not installed** in the venv
   (`importlib.util.find_spec` -> not present), so the fallback in practice always misses.
3. Only then:
   `RuntimeError("Neither 'fastembed' nor 'sentence-transformers' is available to run semantic model '<model>'. Please ensure fastembed is installed.")`
   (`sentence_transformer_provider.py:82-85`). The message is clear.
4. **Hazard:** any *non*-`ImportError` failure from fastembed (model not in its registry, download
   blocked, ONNX runtime failure) is caught at `:69-70`, logged at WARNING, and execution silently
   continues into the unavailable `sentence_transformers` path, so the operator sees a generic
   "neither ... available" error that hides the real cause. Backend selection is therefore
   environment-dependent rather than fail-closed.

Also note `fastembed` downloads the ONNX model from Hugging Face on first `TextEmbedding(...)` call
(`sentence_transformer_provider.py:63-64`). Nothing is vendored or pre-warmed, so the first embedding
request in a fresh container requires egress to `huggingface.co` and a writable cache dir
(`MMAIP_MODEL_CACHE_DIR` or the fastembed default).

### 1.6 Packaging observations

- `project.readme = "README.md"` but **`backend/README.md` does not exist** on disk and is **not tracked
  by git** (`git ls-files backend/README.md` -> empty; `Test-Path` -> `False`). Verified non-fatal on
  setuptools 70.2.0:

  ```
  SetuptoolsWarning: File 'E:\MM Office\Multi-Tanant-CaaS\backend\README.md' cannot be found
  ```
  Resolution returns an empty description. Consequence: `pip install -e .` still succeeds, but the
  installed `mmaip_backend-0.1.0.dist-info/METADATA` has `Description-Content-Type: text/markdown`
  with **no body**, and every install emits a warning. Cosmetic today, a blocker for publishing.
- No `requirements.txt`, `requirements-dev.txt`, `poetry.lock`, `uv.lock`, `Pipfile.lock`, or
  constraints file exists anywhere in the repo (full-tree scan, see section 6).
- `psycopg2` / `psycopg` are **not installed and not declared** - this is correct: Alembic online mode
  uses the async engine (`backend/alembic/env.py:47-64`, `async_engine_from_config` on
  `DATABASE_URL`), and offline mode (`env.py:21-33`) only configures a URL literal, so no sync DBAPI is
  required. No missing-driver defect.

---

## 2. Frontend - `frontend/package.json`

### 2.1 Declarations

| Field | Value |
|---|---|
| `name` / `version` / `private` | `frontend` / `0.1.0` / `true` |
| `scripts` | `dev: next dev`, `build: next build`, `start: next start`, `lint: eslint` |
| `dependencies` | `lucide-react ^1.70.0`, **`next 16.4.5` (exact)**, **`react 19.3.0` (exact)**, **`react-dom 19.3.0` (exact)** |
| `devDependencies` | `@tailwindcss/turbopack ^4`, `@types/node ^20`, `@types/react ^19`, `@types/react-dom ^19`, `eslint ^9`, `eslint-config-next 16.4.5` (exact), `tailwindcss ^4`, `typescript ^5` |
| `engines` | **absent** |
| `packageManager` | **absent** |
| `overrides` / `resolutions` | absent |

No `.nvmrc` and no `.node-version` file exists at the repo root or in `frontend/`.

### 2.2 Lockfile presence and sync verification

`frontend/package-lock.json` exists (235,158 bytes, last modified 2026-11-06 20:12:46) and is
**tracked by git** (`git ls-files --error-unmatch frontend/package-lock.json` -> path echoed).
No `pnpm-lock.yaml`, `yarn.lock`, or `npm-shrinkwrap.json`.

Static sync check (Node parse, no install):

```
deps match: true
devDeps match: true
lockfileVersion: 3
total packages: 439
missing integrity entries: 6
```

The six entries lacking `integrity` are all `optional: true` WASI shims nested under
`node_modules/@tailwindcss/oxide-wasm32-wasi/...` (`@emnapi/core`, `@emnapi/runtime`,
`@emnapi/wasi-threads`, `@napi-rs/wasm-runtime`, `@tybys/wasm-util`, `tslib`). These are optional
platform-specific packages and are normal to omit from integrity checking; they do not block `npm ci`.
The root `packages[""]` block in the lockfile is **structurally identical (JSON-equal)** to `package.json` dependencies and
devDependencies, so the lockfile is not stale.

Exact resolutions recorded in the lockfile:

| Package | Locked version | dev | engines |
|---|---|---|---|
| `next` | 16.4.5 | false | `{"node":">=20.9.0"}` |
| `react` | 19.3.0 | false | `{"node":">=0.10.0"}` |
| `react-dom` | 19.3.0 | false | null |
| `lucide-react` | 1.70.0 | false | null |
| `tailwindcss` | 4.3.4 | true | null |
| `typescript` | 5.9.3 | true | `{"node":">=14.17"}` |
| `eslint` | 9.39.5 | true | `^18.18.0 \|\| ^20.9.0 \|\| >=21.1.0` |
| `eslint-config-next` | 16.4.5 | true | null |
| `@tailwindcss/turbopack` | 4.3.4 | true | null |
| `@types/node` | 20.19.43 | true | null |
| `@types/react` | 19.3.0 | false | null |
| `@types/react-dom` | 19.3.0 | true | null |

### 2.3 Is `npm ci` viable?

**Yes.** CI (`.github/workflows/ci.yml:69-78`) sets up Node 20 with
`cache-dependency-path: frontend/package-lock.json` and runs `npm ci` in `frontend/`. Requirements met:
lockfile present, `lockfileVersion` 3 (npm >= 7), committed to git, complete (439 packages), root
dependency trees identical to `package.json`. `npm ci` was **not** executed here (Stage 5 owns builds).

### 2.4 Node engine expectations vs. Next 16 / React 19

| Source | Node expectation |
|---|---|
| `next` 16.4.5 `engines` | **`>=20.9.0`** |
| React 19.3.0 / react-dom 19.3.0 | no engine constraint declared |
| `.github/workflows/ci.yml` | `node-version: 20` (resolves to latest 20.x, satisfies >=20.9.0) |
| `infrastructure/docker/frontend.Dockerfile` | `node:20-alpine` (floating 20.x tag) |
| This workstation | `v24.14.1`, `npm 11.11.0` |
| `package.json` / `.nvmrc` | **no declaration** - nothing enforces any of the above |

Gap: three Node lines are in play (CI 20, Docker 20, developer 24) with no `engines` field and no
`.nvmrc`. Next 16 requires >=20.9.0, so all three work today, but nothing prevents a Node 18 or Node 26
environment from producing a different install or build.

### 2.5 Import-vs-declaration consistency

All external specifiers used by `frontend/app`, `frontend/lib`, `frontend/components` resolve to
declared packages: `next`, `next/link`, `next/navigation`, `react`, `lucide-react`,
`eslint/config`, `eslint-config-next/core-web-vitals`, `eslint-config-next/typescript`. No undeclared
runtime import was found; `@/*` path aliases correspond to `frontend/` local modules. No markdown or
charting library is imported (`MarkdownRenderer.tsx` and `citations.ts` are hand-rolled).

---

## 3. SDKs

### 3.1 `sdk/python` (package `mmaip` 0.1.0)

| Field | Value |
|---|---|
| Build backend | `setuptools.build_meta`, `requires = ["setuptools>=61.0"]` |
| `requires-python` | `>=3.10` |
| `dependencies` | `httpx>=0.24.0` (single dependency) |
| Optional `dev` | `pytest>=7.0.0` |
| Lockfile | **none** |
| README | `sdk/python/README.md` exists (matches `readme = "README.md"`) |

Consistency with code: `sdk/python/mmaip/client.py:7` imports `httpx`; `client.py` uses
`httpx.Client`, `client.stream`, `response.iter_text()` - the streaming API used needs httpx >= 0.20,
so `>=0.24.0` is sane. `sdk/python/mmaip/__init__.py` imports only from `mmaip.client`. **No undeclared
import.** `>=0.24.0` is unbounded upward (httpx 0.28.1 is installed in the backend venv; the SDK is not
installed anywhere, so its runtime is unverified).

### 3.2 `sdk/typescript` (package `@mmaip/client` 0.1.0)

| Field | Value |
|---|---|
| `main` / `types` | `dist/index.js` / `dist/index.d.ts` |
| `scripts` | `build: tsc` only |
| `dependencies` / `devDependencies` / `peerDependencies` | **none declared** |
| `engines` / `type` / `files` | absent |
| Lockfile | **none** |
| `dist/` | present on disk but **untracked** (`git ls-files sdk/typescript` returns only `README.md`, `package.json`, `src/index.ts`, `tsconfig.json`) |

`tsconfig.json`: `target ES2022`, `module`/`moduleResolution` `NodeNext`, `declaration` + `declarationMap`,
`outDir ./dist`, `rootDir ./src`, `strict`, `include: ["src/**/*"]`.

Consistency: `src/index.ts` has **zero** third-party imports (uses global `fetch`, lines 69 and 141), so
an empty dependency list is correct. Two reproducibility gaps:

1. `tsc` is required by the only build script but **TypeScript is not a devDependency**, so
   `npm run build` only works if a global `tsc` happens to be installed.
2. Because `module: NodeNext` with no `"type": "module"` in `package.json`, output is CommonJS; that is
   valid for `main: dist/index.js`, but `dist/` is not committed, so a fresh clone cannot consume the
   package (`main`/`types` point at files that do not exist until someone builds with a global tsc).
   No `files` field means a naive `npm publish` would ship `src/` too.

---

## 4. Containers and deployment

### 4.1 `infrastructure/docker/backend.Dockerfile`

| Check | Result |
|---|---|
| Base image | `python:3.12-slim` - **matches `requires-python >=3.12`** (tag is floating, no digest pin) |
| OS packages | `build-essential`, `curl`, `libpq-dev`, `tesseract-ocr`, `tesseract-ocr-eng` - covers the `pytesseract` runtime need |
| Install command | `COPY pyproject.toml /app/` then `pip install --upgrade pip && pip install -e .` |
| Covers declared deps? | Yes - `pip install -e .` reads `project.dependencies` (all 28 entries) |
| Dev-only deps at runtime? | **No** - `[project.optional-dependencies].dev` is not installed; `app/` contains no `pytest`/`mypy`/`ruff` imports (0 matches) |
| Lockfile used? | **No** - resolution happens at image build time |
| Storage env | none baked in; runtime env comes from compose/Render (`STORAGE_BACKEND=s3` in staging) |
| Secrets baked in? | **No** - `.dockerignore` excludes `.env`, `.env.*`, `data/`, `*.db`, `.venv`, `tests/` |
| `.dockerignore` | present (`backend/.dockerignore`, 18 lines) |
| Non-root user | **absent** - image runs as root |
| Multi-stage | **absent** - `build-essential`, `libpq-dev`, `curl` remain in the runtime image |
| `PIP_NO_CACHE_DIR=off` | cache is retained in the layer (larger image); `pip` itself is upgraded unpinned |
| Healthcheck | absent in Dockerfile (compose supplies one) |

**Layer-ordering defect (dependency-relevant).** `pip install -e .` runs at line 19, *before*
`COPY . /app/` at line 21. At that moment `/app` contains only `pyproject.toml`, so
`packages.find where=["."] include=["app*"]` discovers **no packages** and the modern editable
installer (`_TopLevelFinder`) writes an **empty** mapping (contrast: the developer venv's finder, built
with source present, maps `{'app': '...\backend\app'}`). The image therefore contains `mmaip-backend`
metadata with no importable package. Runtime imports still work only because:

- `CMD ["uvicorn", ...]` -> uvicorn's CLI default `--app-dir ""`
  (`uvicorn/main.py:368`, `default=""`) coerces `sys.path.insert(0, "")` -> cwd `/app`, and
- the worker entrypoint uses `python -m app.services.ingestion.worker`, which puts cwd on `sys.path`.

Any entrypoint that is neither uvicorn-cli nor `python -m` (e.g. `gunicorn app.main:app`, a script in
`/usr/local/bin`) would raise `ModuleNotFoundError: No module named 'app'`. Fix in a later stage by
copying source before installing, or by splitting dependency installation into a
`requirements`-based layer and installing the app non-editable.

### 4.2 `infrastructure/docker/frontend.Dockerfile`

| Check | Result |
|---|---|
| Base image | `node:20-alpine` - satisfies `next` `engines >=20.9.0` (floating 20.x tag); musl libc |
| Install command | `COPY package*.json ./` -> **`npm install`** (not `npm ci`) |
| Lockfile present in context? | Yes (`package*.json` copies `package-lock.json`); `.dockerignore` does **not** exclude it |
| Deterministic install? | **No** - `npm install` may rewrite the lockfile and does not fail on drift |
| Build step | **none** - no `npm run build`, no `npm run start` |
| Runtime command | `CMD ["npm", "run", "dev"]` -> Next **development server** |
| Dev-only deps at runtime | **Yes** - `next dev` requires devDependencies (`typescript`, `@tailwindcss/turbopack`, eslint configs) |
| `NODE_ENV` | not set |
| `libc6-compat` | not installed (Next/SWC on musl generally wants it) |
| Non-root user | **absent** |
| `.dockerignore` | present (`frontend/.dockerignore`, 10 lines: `node_modules/`, `.next/`, `out/`, `.env*`, `.git/`) |
| Secrets baked in? | **No** - `.env*` excluded; `NEXT_PUBLIC_API_URL` is supplied at runtime by compose |

This image is a **development** artifact. It is not suitable as a staging/production frontend (Vercel is
the declared frontend host in `render.yaml`/`.env.production.example`, so this is not a staging blocker,
but it must not be reused as one).

### 4.3 `docker-compose.yml`

| Check | Result |
|---|---|
| Purpose | Local/dev stack (explicit `ENVIRONMENT=development`, `DEBUG=true`, bind mounts of `./backend` and `./frontend`) |
| Backend build | `context: ./backend`, `dockerfile: ../infrastructure/docker/backend.Dockerfile` (valid; Dockerfile outside context is allowed) |
| Frontend build | `context: ./frontend`, `dockerfile: ../infrastructure/docker/frontend.Dockerfile` |
| Storage | `STORAGE_BACKEND=local`, `STORAGE_PATH=/app/data/storage` - **dev only**; must not be used for staging |
| Secrets | dev placeholders with defaults (`SECRET_KEY=${SECRET_KEY:-dev-secret-key-change-me...}`, same for JWT); no real secrets |
| Images pinned | `pgvector/pgvector:pg16`, `qdrant/qdrant:v1.9.0`, `redis:7-alpine`, **`arizephoenix/phoenix:latest` (unpinned)** |
| Client/server skew | `qdrant-client` 1.20.0 (backend) vs `qdrant/qdrant:v1.9.0` (server) - a 10-minor client/server gap |
| Healthchecks | postgres and backend defined; frontend/worker none |

Note: `qdrant` and `redis` are only reachable through compose profiles
(`vector`/`qdrant`/`redis`/`full`); staging uses managed Postgres + S3 and does not need them.

### 4.4 `render.yaml`

| Check | Result |
|---|---|
| Service | `mmaip-backend`, `env: python`, `rootDir: backend`, plan `starter`, region `oregon` |
| Build command | **`pip install -e .`** - no lockfile, resolves latest at every deploy |
| Pre-deploy | `alembic upgrade head` (async engine -> only `asyncpg` needed; consistent with installed deps) |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2` |
| Health check | `/health` |
| Python version | **not pinned** (`env: python` only) - Render's default interpreter may drift |
| `DATABASE_URL` | `fromDatabase ... connectionString` (plain `postgresql://`); `app/core/config.py:41-49` rewrites it to `postgresql+asyncpg://` - **correct**, no missing driver |
| `DATABASE_SYNC_URL` | same connectionString; only used by Alembic offline mode - harmless |
| Secrets | `SECRET_KEY`, `JWT_SECRET`, `SECRET_ENCRYPTION_KEY` use `generateValue: true`; `OPENAI_API_KEY`, `OMNIROUTE_API_KEY`, `S3_*` use `sync: false` - **no secrets in the file** |
| Production storage | **`STORAGE_BACKEND=s3` with `S3_BUCKET_NAME/S3_ENDPOINT_URL/S3_ACCESS_KEY_ID/S3_SECRET_ACCESS_KEY` as dashboard-managed placeholders (`sync: false`)** - meets the durable-storage requirement |
| Filesystem | `STORAGE_PATH=/app/data/storage` is still set but ignored when `STORAGE_BACKEND=s3` |
| Embedding | `DEFAULT_EMBEDDING_PROVIDER=sentence-transformers` + `DEFAULT_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2` -> **runtime Hugging Face model download** on first use |
| LLM gateway | `LLM_BASE_URL=https://api.openai.com/v1` (vendor-direct) - deviates from the OmniRoute-only platform standard in `AGENTS.md`; recorded here as a configuration observation, not a dependency defect |
| Autodeploy | `autoDeploy: true` - combined with the unpinned install this means any upstream release can reach staging unattended |

### 4.5 `.env.production.example`

| Check | Result |
|---|---|
| Secret values | placeholders only (`change-me-to-a-secure-random-64-character-hex-string`, empty `SECRET_ENCRYPTION_KEY`, empty `S3_*`) - **no real secrets** |
| Storage | **`STORAGE_BACKEND=s3`** with `S3_BUCKET_NAME=your-production-bucket-name`, empty `S3_ENDPOINT_URL` (commented AWS/R2/MinIO guidance) - S3 with placeholders, as required |
| Local fallback documented | `STORAGE_BACKEND=local` rejected at startup in production (comment at lines 56-57) |
| Baked-in paths | `STORAGE_PATH=/app/data/storage` (documented dev-only), no absolute host paths |
| Baked-in hosts | `FRONTEND_URL=https://multi-tenant-ai-platform.vercel.app`, `BACKEND_URL=https://mmaip-backend.onrender.com` - public, non-secret, environment-specific defaults; should be overridden per environment |
| Portability | consistent with `app/core/config.py` field names; no dependency declarations here |

### 4.6 `.dockerignore` coverage

| Context | File | Present |
|---|---|---|
| `./backend` (backend + worker image) | `backend/.dockerignore` | Yes |
| `./frontend` | `frontend/.dockerignore` | Yes |
| Repo root | `.dockerignore` | Not present - **not needed**, because both compose build contexts are the per-service directories |

---

## 5. Lockfile status (complete table)

Search scope: full repo tree, excluding `node_modules/`, `.venv/`, `.next/`, `.git/`.

| Project | Manifest | Lock mechanisms checked | Status |
|---|---|---|---|
| `backend/` | `pyproject.toml` | `poetry.lock`, `uv.lock`, `requirements*.txt`, `Pipfile.lock` | **NONE - unpinned** |
| `frontend/` | `package.json` | `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `npm-shrinkwrap.json` | **`package-lock.json` v3, committed, in sync** |
| `sdk/python/` | `pyproject.toml` | same Python set | **NONE - unpinned** |
| `sdk/typescript/` | `package.json` | same JS set | **NONE - unpinned, and no deps to pin** |
| Container images | Dockerfiles / compose / render | image digests, tags | **Tags only, no digests**; `python:3.12-slim`, `node:20-alpine`, `arizephoenix/phoenix:latest` float |

The only lockfile in the repository is `frontend/package-lock.json`. **No lockfile was generated during
this stage** (per constraints).

---

## 6. Reproducibility assessment

### 6.1 Is staging deployment safe without a backend lockfile?

**No - not in the strict sense.** Every staging path resolves dependencies at build time from
lower-bound-only constraints:

| Path | Command | Resolution behaviour |
|---|---|---|
| Render deploy | `buildCommand: "pip install -e ."` | fresh resolve on **every** deploy, `autoDeploy: true` |
| Docker backend image | `pip install --upgrade pip && pip install -e .` | fresh resolve on every `docker build`, no cache invalidation beyond `pyproject.toml` |
| CI backend | `pip install -e .` | fresh resolve on every run; CI can therefore go green while a later staging build fails (or vice versa) |

The same commit can therefore produce different installed versions on two consecutive days, and the
repo carries no record of what was actually validated. Given the open upper bounds, a single upstream
release can change the runtime without any code change, most plausibly:

- `huggingface-hub` / `tokenizers` / `onnxruntime` majors moving under `fastembed` (all three already
  sit at recent majors: 1.33.0 / 0.23.3 / 1.31.1),
- `numpy` 3.x (currently 2.5.4, `fastembed` declares no upper bound on py3.12),
- a `fastapi` 0.1xx minor or `sqlalchemy` 2.x minor with behavioural change,
- `aioboto3` >15 (its internal `aiobotocore==` pin moves with each release),
- `PyMuPDF` >2.1, `pillow` >14, `cryptography` >50.

This is a **risk acceptance decision**, not a proven failure. The current venv is internally consistent
(`pip check` clean) and is a valid known-good snapshot for the M10 functional work - it is simply not
recorded anywhere the deploy pipeline can consume.

Practical impact of proceeding without a lock:

- Rollback to a previous commit does **not** roll back dependencies.
- A staging incident caused by a transitive release cannot be reproduced locally from the repo.
- The `preDeployCommand: alembic upgrade head` runs with whatever SQLAlchemy/Alembic versions resolve
  that day, against a schema whose migrations were validated on 2.1.8 / 1.20.1.
- The first embedding request downloads a model at runtime; version drift in `fastembed`'s model
  registry can therefore break ingestion with no deploy at all.

### 6.2 Frontend

Reproducible **if and only if** the build uses the committed lockfile. `npm ci` in CI satisfies this.
The Dockerfile's `npm install` does not (it may update the lockfile), and it does not build a production
bundle at all. Staging frontend is hosted on Vercel (per `render.yaml`/`.env.production.example`), so the
Dockerfile is not the staging path - but any future container-based frontend deploy needs
`npm ci && npm run build` plus `next start`.

### 6.3 SDKs

`mmaip` and `@mmaip/client` are not deployed services; their reproducibility risk is limited to
consumers. Both are installable today only because the environment happens to satisfy them:
`httpx>=0.24.0` resolves to whatever the consumer has, and the TypeScript SDK cannot be rebuilt without
a global `tsc`.

---

## 7. Risk register

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| R-1 | **High** | No backend lockfile; all three build paths (`render.yaml:13`, `backend.Dockerfile:19`, `ci.yml:44`) resolve latest-compatible versions per build | section 5, 6.1 |
| R-2 | **High** | `fastembed>=0.3.0` allows 6 minors of pre-1.0 API drift; code depends on `TextEmbedding(model_name=..., cache_dir=...)` and `model.embed(texts, batch_size=...)` returning a generator | `pyproject.toml:39`, `sentence_transformer_provider.py:57-64,102,140`; `qdrant-client` extra pins `<0.10` |
| R-3 | **High** | `aioboto3>=12.4.0` unbounded; installed 15.5.0 hard-pins `aiobotocore==2.25.1`, which drags `botocore`/`boto3` 1.40.61 - a version set the repo does not record | `pyproject.toml:38`; installed metadata |
| R-4 | Medium | Embedding model is downloaded at first use from Hugging Face; nothing vendored, no pre-warm step, no offline fallback; staging sets `sentence-transformers` provider explicitly | `sentence_transformer_provider.py:63-64`; `render.yaml:66-69`; `.env.production.example:82-84` |
| R-5 | Medium | Non-`ImportError` fastembed failures are swallowed (`except Exception: logger.warning`) and fall through to an undeclared, uninstalled `sentence_transformers`, masking the root cause | `sentence_transformer_provider.py:67-70,79-85` |
| R-6 | Medium | Backend image installs the package before copying source -> editable finder has an empty package map; runtime import depends on cwd (`--app-dir ""` / `python -m`) | `backend.Dockerfile:18-21`; `uvicorn/main.py:368,558-559` |
| R-7 | Medium | Frontend image runs `npm run dev` (requires devDependencies, no build, no `NODE_ENV=production`) | `frontend.Dockerfile:6,12` |
| R-8 | Medium | No `engines` / `.nvmrc`; CI Node 20, Docker Node 20-alpine, local Node 24.14.1; Next requires >=20.9.0 | `package.json` (no engines); `ci.yml:72`; `frontend.Dockerfile:1` |
| R-9 | Low | `pip install --upgrade pip` unpinned; `PIP_NO_CACHE_DIR=off` keeps the wheel cache in the image layer | `backend.Dockerfile:4-6,19` |
| R-10 | Low | Single-stage backend image keeps `build-essential`/`libpq-dev`/`curl`; no non-root user | `backend.Dockerfile:10-16` |
| R-11 | Low | `arizephoenix/phoenix:latest` unpinned; `qdrant-client` 1.20.0 against `qdrant/qdrant:v1.9.0` server | `docker-compose.yml:104,125` |
| R-12 | Low | TypeScript SDK has no `typescript` devDependency and no lockfile; `dist/` is untracked while `main`/`types` point into it | `sdk/typescript/package.json`; `git ls-files sdk/typescript` |
| R-13 | Low | `project.readme = "README.md"` points at a non-existent, untracked `backend/README.md` -> SetuptoolsWarning and empty package description on every install | `pyproject.toml:9`; setuptools warning output above |
| R-14 | Info | `fastembed`/`qdrant-client` pull large native wheels (`onnxruntime` 1.31.1, `numpy` 2.5.4, `tokenizers`, `grpcio`, `protobuf`) - image size and build-time risk, not a correctness issue | `pip show` `Requires:` lines |

---

## 8. Unpinned heavyweight dependencies (explicit list)

Ranked by blast radius if an unbounded upstream release lands:

1. **`fastembed>=0.3.0`** - pre-1.0, native ONNX stack, model registry, runtime download. Pin a range
   aligned with what the ecosystem tests: `fastembed>=0.9,<0.10`.
2. **`aioboto3>=12.4.0`** - hard-pins `aiobotocore`, which hard-pins a botocore window; any major bump
   changes the entire AWS SDK stack underneath S3 storage. Pin `>=15.5,<16`.
3. **`qdrant-client>=1.9.0`** - 1.20.0 installed, server tag is 1.9.0; client adds `grpcio`/`protobuf`.
4. **`PyMuPDF>=2.1.0`** - PDF parsing is a core ingestion path; 2.1 is a fresh major.
5. **`pillow>=13.0.0`** / **`cryptography>=42.0.0`** (50.0.2 installed) / **`sqlglot>=30.30.0`** -
   large majors, no upper bounds, all in request-critical paths.
6. **`fastapi`, `sqlalchemy`, `pydantic`, `uvicorn`, `alembic`, `asyncpg`** - all `>=` only; a Framework
   major (Pydantic 3 / SQLAlchemy 2.2+) would land silently on the next deploy.
7. **`arizephoenix/phoenix:latest`** (image tag) - optional observability profile only.

Not heavyweight but worth recording: `frontend` `lucide-react ^1.70.0`, `tailwindcss ^4`,
`typescript ^5`, `eslint ^9` are caret-ranged, but the **committed lockfile neutralises them**.

---

## 9. Recommendations (not executed)

Ordered so that each step is independently reviewable. **None of these were performed in this stage.**

### Before staging (blocking)

1. **Add a backend lockfile in a dedicated dependency-only commit.**
   Preferred: `uv lock` + committed `uv.lock`, then `uv sync --frozen --no-dev` in Docker/Render.
   Acceptable: `pip-compile --generate-hashes` producing `backend/requirements.txt` (and
   `requirements-dev.txt`), with `pip install --require-hashes -r requirements.txt`.
   Keep it a pure dependency change: no functional edits in the same commit.
2. **Point every build path at the lock.** `render.yaml` `buildCommand`,
   `infrastructure/docker/backend.Dockerfile`, and the CI install step must all consume the locked
   artefact, otherwise the lock is decorative.
3. **Bound the two risky packages now** (can ride with step 1): `fastembed>=0.9,<0.10` and
   `aioboto3>=15.5,<16`. These match the versions that were actually exercised by the M10 test suite.

### Before staging (strongly recommended)

4. **Pre-warm / vendor the embedding model** or set an explicit cache dir with a build-time download, so
   the first staging embedding request does not depend on Hugging Face availability. At minimum, record
   `MMAIP_MODEL_CACHE_DIR` in the deploy config.
5. **Make fastembed failure loud**: in `_get_model`, log the exception with `exc_info` and do not treat a
   non-`ImportError` from fastembed as "try the other backend". Fail closed instead of degrading.
6. **Add `"engines": { "node": ">=20.9.0" }`** (or an `.nvmrc` with `20`) to `frontend/package.json` so
   CI, Docker and developer machines converge; optionally pin `node:20.x-alpine` explicitly.

### Follow-up (non-blocking, small dedicated changes)

7. Fix the backend Dockerfile ordering: `COPY . /app/` then `pip install .` (non-editable), or split a
   dependency layer from the app layer. Add a non-root user and drop build tooling from the final image.
8. Convert `frontend.Dockerfile` to `npm ci` + multi-stage `npm run build` + `next start` (or delete it
   if Vercel is the only frontend path).
9. Add `backend/README.md` (or drop `readme` from `pyproject.toml`) to clear the SetuptoolsWarning and the
   empty package description.
10. Add `typescript` as a `devDependency` in `sdk/typescript` plus a lockfile, and decide whether `dist/`
    is committed or built on publish.
11. Pin `arizephoenix/phoenix` to a version tag, and consider aligning `qdrant/qdrant` with client 1.20.x.
12. Review `render.yaml`'s `LLM_BASE_URL=https://api.openai.com/v1` against the OmniRoute-only platform
    standard (`AGENTS.md` section 2). Out of Stage 4 dependency scope; flagged for the owner of deploy
    configuration.

---

## 10. Stage 5 handoff - what must be proven by execution

| # | Check | Why |
|---|---|---|
| 1 | Clean-clone `npm ci` + `npm run build` in `frontend/` | Confirms the lockfile is complete outside this workstation (static check passed; execution pending) |
| 2 | `docker build` of `backend.Dockerfile` and `frontend.Dockerfile` | R-6 (empty editable map) and the alpine/SWC path can only be confirmed by a real build |
| 3 | Fresh venv install from the (future) lock, then `pip check` + `pytest -q` | Proves the lock reproduces the validated 114-package environment |
| 4 | `pip install -e .` on a clean checkout **without** `README.md` present | Confirms the SetuptoolsWarning is the only consequence (observed on setuptools 70.2.0; build isolation may pull a newer setuptools) |
| 5 | First-call embedding in a network-restricted container | Confirms the runtime model-download dependency (R-4) and its failure mode |
| 6 | Render `preDeployCommand: alembic upgrade head` against staging DB | Confirms the async-only driver assumption (no `psycopg2` needed) |

---

## Appendix A - Raw evidence index

| Item | Command | Result |
|---|---|---|
| Python | `backend\.venv\Scripts\python.exe -c "import sys; ..."` | 3.12.3, venv path |
| Imports | `... -c "import aioboto3, fastembed"` | OK, 15.5.0 / 0.9.1 |
| Dependency integrity | `... -m pip check` | `No broken requirements found.` |
| Package metadata | `... -m pip show fastembed aioboto3` | full blocks above |
| Venv size | `... -m pip list --format=freeze \| Measure-Object -Line` | 114 lines |
| Frontend lock | `node -e` parse of `frontend/package-lock.json` | v3, 439 packages, deps+devDeps match |
| Next engine | `frontend/node_modules/next/package.json` | `16.4.5`, `engines.node >=20.9.0` |
| Node runtime | `node --version` / `npm --version` | `v24.14.1` / `11.11.0` |
| README probe | `setuptools.config.expand.read_files(['README.md'], backend)` | `SetuptoolsWarning: File ... cannot be found`, returns `[]` |
| Editable installer | inspection of `backend/.venv/Lib/site-packages/__editable___mmaip_backend_0_1_0_finder.py` | `MAPPING = {'app': '...\\backend\\app'}` (built with source present) |
| Tracked files | `git ls-files frontend/package-lock.json`, `git ls-files sdk/typescript`, `git ls-files backend/README.md` | lock tracked; SDK dist untracked; backend README absent |

**Stage 4 conclusion:** declarations are complete and the installed backend environment is internally
consistent (`pip check` clean, both target packages import), the frontend is properly locked and
`npm ci`-ready, and the production storage contract is correct (S3 with placeholders, no secrets, no
baked paths). The one material reproducibility gap is the **absence of any backend lockfile feeding
three independent build paths**; staging should not be considered reproducible until a committed lock is
in place. No files were modified other than this document, and no install, upgrade, lock generation,
model download, cloud call or git mutation was performed.
