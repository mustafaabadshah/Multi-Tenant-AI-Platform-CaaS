# M10 Final Integration — Stage C: Configuration Consistency Audit

**Date:** 2026-11-11
**Status vocabulary:** VERIFIED / REPORTED / PARTIAL / NOT VERIFIED / NOT RUN
**Scope:** `backend/app/core/config.py`, `.env.example`, `.env.production.example`, `render.yaml`, `docker-compose.yml`, provider registries, deployment docs.

---

## C1. LLM provider strategy — VERIFIED (with 3 config defects)

**Registry (`app/llm/registry.py`):** 6 providers — `groq`, `anthropic`, `gemini`, `openai` (direct BYOK), `omniroute` (local gateway), `mock`. Each direct provider has its own default base URL and API key env var. Direct providers are fully independent of OmniRoute.

| Requirement | Finding |
|---|---|
| OmniRoute not mandatory | VERIFIED — direct providers resolve their own endpoints; OmniRoute is only one of six. |
| Missing OmniRoute must not block direct providers | VERIFIED — only the `omniroute` provider touches `localhost:20128` (via `os.environ["LLM_BASE_URL"]` fallback, `llm/providers/openai_provider.py:81`). |
| `auto` must not silently select unconfigured/paid provider | PARTIAL — assistant default is `llm_provider="omniroute"`, `default_model="auto"` (`schemas/assistant.py:17-18`). `auto` is only meaningful to OmniRoute/Groq (`groq_provider` normalizes `auto`→`llama-3.3-70b-versatile`); sent to direct OpenAI it would 404. No silent cross-provider fallback exists. |
| Explicit, predictable provider selection | VERIFIED — wizard selects provider; runtime resolves strictly from assistant record. |
| Commercial providers require BYOK | VERIFIED — `runtime.py:262` blocks `openai/anthropic/gemini/groq` without an active vault credential (no silent platform-key fallback); same for preview path. |
| No secrets in logs/API responses | VERIFIED — `sanitize_error_message` (runtime.py:33) + tracer `sanitize_value` redaction; tests cover both. |

**Config defects:**

- **C1-D1:** `LLM_DEFAULT_MODEL` (`config.py:92`) is a **dead variable** — no consuming code. `render.yaml` and `.env.production.example` set it, but providers never read it.
- **C1-D2:** `.env.production.example` sets `LLM_BASE_URL=https://api.openai.com/v1` + `LLM_DEFAULT_MODEL=auto` — this combination implies "auto" against direct OpenAI, which is not a valid OpenAI model. Misleading template.
- **C1-D3:** `GROQ_DEFAULT_MODEL` is read via `os.environ` in `groq_provider.py` but absent from `config.py` and `.env.example` (undocumented knob; sane fallback exists).
- **C1-D4:** Provider API-key env vars (`GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`/`GOOGLE_API_KEY`) are read by providers but documented nowhere. Pre-existing gap, now more impactful because strict BYOK blocks unvaulted keys.

**Recommended default strategy (no code change applied):** keep `mock` for offline dev; default new assistants to an explicitly configured provider at creation time (wizard already forces a choice); document OmniRoute as opt-in. The `omniroute` schema default is acceptable only while the gateway is present in dev.

---

## C2. Embedding provider strategy — PARTIAL

**Registry (`app/embeddings/registry.py`):** 5 providers — `omniroute`, `openai`, `sentence-transformers`, `local` (CPU feature projection, zero downloads), `mock`.

| Question | Finding |
|---|---|
| Is `sentence-transformers` supported? | VERIFIED — `SentenceTransformerProvider` registered; tries `fastembed` (ONNX) then `sentence_transformers`. |
| Usable in current runtime? | **NOT VERIFIED / at-risk** — **neither `fastembed` nor `sentence-transformers` nor `aioboto3` is declared in `backend/pyproject.toml`**. The provider fails at runtime with a clear error unless manually installed. `render.yaml` sets `DEFAULT_EMBEDDING_PROVIDER=sentence-transformers` — the staging backend would fail its first embedding unless the package is added to dependencies. |
| FastEmbed/local ONNX actual implementation? | VERIFIED — fastembed is the primary backend, sentence-transformers the fallback. |
| Dimension validation? | VERIFIED — provider enforces exact dims (`ValueError` on mismatch); Qdrant store validates dims; `EmbeddingService` pins dims into the content hash so model/dimension changes create distinct embeddings (no silent vector-space corruption). |
| CPU-only without GPU? | VERIFIED — both backends are CPU-capable; `local` provider requires nothing. |
| Automatic model downloads? | YES on first inference for `sentence-transformers` (huggingface download). **Risk on the 8 GB dev machine and in staging**: first embedding triggers a network model download (~90 MB for MiniLM). `local` and `mock` download nothing. |

**Conflicting defaults (measured):**

| Source | DEFAULT_EMBEDDING_PROVIDER | Model | Dims |
|---|---|---|---|
| `core/config.py` | `omniroute` | `text-embedding-3-small` | 1536 |
| `.env.example` | `sentence-transformers` | `all-MiniLM-L6-v2` | 384 |
| `.env.production.example` | `sentence-transformers` | `all-MiniLM-L6-v2` | 384 |
| `render.yaml` | `sentence-transformers` | `all-MiniLM-L6-v2` | 384 |
| `docker-compose.yml` | `omniroute` | (default) | (default) |

**Recommended configuration per environment (documented, not applied):**
1. **Local lightweight dev (8 GB, no GPU):** `DEFAULT_EMBEDDING_PROVIDER=local` (or `mock` for tests) — zero downloads.
2. **PostgreSQL staging:** `sentence-transformers` + MiniLM (384) **after** adding `fastembed` to `pyproject.toml`; pre-warm the model cache during build.
3. **Production:** explicit choice — either managed OmniRoute/OpenAI embeddings (1536) or self-hosted fastembed (384). Never change provider/model for an existing KB without a re-embedding plan (versioned via `embedding_version`).

**C2-D1:** `embeddings/providers/openai_provider.py:58` — the `openai` embedding provider falls back to `settings.LLM_BASE_URL` (default `localhost:20128`), i.e. a KB configured with provider `openai` and no explicit base URL silently targets **OmniRoute**, not OpenAI. Coupling defect.

---

## C3. Environment variable audit

| Variable | Purpose | Req | Dev default | Prod requirement | Secret | Consumed by | Issues |
|---|---|---|---|---|---|---|---|
| `SECRET_KEY` / `JWT_SECRET` | token signing | Yes | dev placeholders | mandatory strong | Yes | `core/security.py` | placeholder defaults acceptable in dev only |
| `SECRET_ENCRYPTION_KEY` / `PREVIOUS_SECRET_KEYS` | Fernet BYOK encryption | Yes (BYOK) | empty | mandatory | Yes | `core/crypto.py`, `byok_vault.py` | empty default silently breaks BYOK — good (fail-closed) |
| `DATABASE_URL` / `DATABASE_SYNC_URL` | async/sync DB | Yes | postgres localhost | managed Postgres | Semi | session, alembic | URL normalizers handle `postgres://` |
| `STORAGE_BACKEND` / `STORAGE_PATH` | storage adapter | Yes | local | **S3 in prod** | No | `app/storage/` | `.env.production.example` still says `local` → Render ephemeral FS risk (deployment audit) |
| `S3_BUCKET_NAME`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_REGION_NAME` | S3 storage | Cond (S3) | — | when STORAGE_BACKEND=s3 | Yes | `storage/s3.py` | defined in `config.py`, **absent from `.env.example`** |
| `LLM_BASE_URL` | gateway URL | Cond | `http://localhost:20128/v1` | explicit | No | openai provider (env fallback) + embedding openai provider | conflicts across templates (C1-D2) |
| `LLM_DEFAULT_MODEL` | (intended) default model | No | `auto` | — | No | **nothing** | dead variable (C1-D1) |
| `OMNIROUTE_API_KEY` / `OPENAI_API_KEY` | provider keys | Cond | — | per BYOK policy | Yes | providers | ok |
| `DEFAULT_RETRIEVAL_MODE` / `DEFAULT_VECTOR_STORE` | retrieval defaults | Yes | hybrid/pgvector | hybrid/pgvector | No | retrieval, ingestion | consistent across templates |
| `DEFAULT_EMBEDDING_PROVIDER/MODEL/DIMENSIONS` | embedding defaults | Yes | omniroute/1536 in code; sentence-transformers/384 in templates | **conflicting** (C2) | No | `embeddings/service.py` | must be reconciled before staging |
| `RRF_K_CONSTANT`, `EMBEDDING_BATCH_SIZE`, `EMBEDDING_TIMEOUT_SECONDS` | tuning | No | 60/32/30 | ok | No | retrieval, embeddings | consistent |
| `QDRANT_URL` / `QDRANT_API_KEY` / `QDRANT_COLLECTION_NAME` | Qdrant | Cond | localhost:6333 | per deployment | Semi | `vectorstores/qdrant_store.py` | `QDRANT_COLLECTION` in `.env.example` vs `QDRANT_COLLECTION_NAME` in config — **naming inconsistency** (config uses `QDRANT_COLLECTION_NAME`) |
| `REDIS_URL` | cache | No | localhost | — | No | not consumed anywhere in app code (reserved) | dormant |
| `PHOENIX_ENABLED`, `PHOENIX_COLLECTOR_ENDPOINT` | observability | No | false | — | No | not consumed (tracer is in-process) | dormant |
| `CORS_ORIGIN_REGEX` / `ALLOWED_ORIGINS` / `FRONTEND_URL` | CORS | Yes | localhost | production allowlist | No | `main.py` | default-active dev regex risk (see C1 in security audit + D11) |
| `DEBUG`, `ENVIRONMENT` | mode switches | Yes | true/dev | **must be false/production** | No | CORS, error detail | the only guard against permissive dev CORS |

Duplicate/dead vars: `LLM_DEFAULT_MODEL` (dead), `PHOENIX_*` + `REDIS_URL` (dormant). Naming mismatch: `QDRANT_COLLECTION` vs `QDRANT_COLLECTION_NAME`. Missing from templates: `S3_*`, `GROQ_DEFAULT_MODEL`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`.

---

## Declaration

```text
CONFIGURATION_CONSISTENCY = PARTIAL
```
Remediation requirements: (1) unify embedding defaults across `config.py`/templates/`render.yaml`; (2) add `fastembed` + `aioboto3` to `pyproject.toml`; (3) fix `.env.production.example` LLM section and set `STORAGE_BACKEND=s3`; (4) document provider key env vars; (5) drop or implement dead/dormant variables; (6) production CORS gate must not rely on defaults.
