# M10 Remediation — Stage 5: Dependency Declaration (fastembed, aioboto3)

**Date:** 2026-11-11
**Findings:** D5 (`aioboto3` missing — S3 production storage fails at runtime) and C2 (`fastembed`/`sentence-transformers` missing — the embedding provider selected by `render.yaml`/`.env.production.example` fails at runtime).

---

## 1. Investigation

- `backend/app/storage/s3.py` lazy-imports `aioboto3` on every operation — without a declared dependency, any S3 deployment fails with an ImportError (previous behavior: clear error message only).
- `backend/app/embeddings/providers/sentence_transformer_provider.py` tries `fastembed` (ONNX) then `sentence_transformers` — neither declared; staging config selects this provider.
- Neither package was present in any dependency group; neither import is unconditional (both lazy) — but both are required by the shipped configuration, so they belong in **core runtime dependencies** (staging blueprint `render.yaml` runs plain `pip install -e .`).
- Python 3.12 compatibility: verified — `fastembed>=0.3.0` and `aioboto3>=12.4.0` support 3.12.

## 2. Resource impact (declared before install)

| Package | Pulls | Approx install size | Models downloaded? |
|---|---|---|---|
| `aioboto3` | boto3, botocore, aiobotocore, aiohttp, jmespath, s3transfer, wrapt | ~80 MB | No |
| `fastembed` | onnxruntime (~60 MB wheel), huggingface-hub, tokenizers, tiktoken, numpy(shared), Pillow | ~250 MB total | **No — models download only at first inference** (not during install) |

Installed **only into the project venv** (`backend/.venv`, E: drive). No global installs, no model downloads during this stage, no cloud calls.

## 3. Fix implemented

`backend/pyproject.toml` — added to core runtime dependencies:

```toml
"aioboto3>=12.4.0",
"fastembed>=0.3.0",
```

## 4. Validation (measured)

| Check | Command | Result |
|---|---|---|
| Install into venv | `pip install "aioboto3>=12.4.0" "fastembed>=0.3.0"` | PASS (aioboto3 15.5.0, fastembed, onnxruntime 1.31.1) |
| Dependency health | `pip check` | PASS — "No broken requirements found." |
| Package metadata | `pip install -e . --no-deps` + `importlib.metadata.requires` | PASS — both declared in `mmaip-backend` metadata |
| Import smoke | `import aioboto3, fastembed; from fastembed import TextEmbedding` | PASS |
| S3 provider tests | `tests/test_s3_storage.py` + `tests/test_remediation_stage3_storage.py` | PASS (16 tests) |
| Embedding provider unit tests | `tests/test_embedding_providers.py` | PASS (in full suite; re-run at Stage 9) |

**Not performed (documented):** actual model inference for `sentence-transformers` (would download MiniLM ~90 MB — explicitly prohibited by stage rules). The `local` embedding provider remains the zero-download dev default; `fastembed` model download occurs lazily at first inference in staging.

## 5. Files changed

| File | Change |
|---|---|
| `backend/pyproject.toml` | + `aioboto3>=12.4.0`, + `fastembed>=0.3.0` |

## 6. Residual risks

- First staging embedding triggers a Hugging Face download of `all-MiniLM-L6-v2` (~90 MB). Recommendation for staging: pre-warm the cache during build (`MMAIP_MODEL_CACHE_DIR`) or start with `DEFAULT_EMBEDDING_PROVIDER=local` for smoke tests.
- No lockfile exists (`poetry.lock`/`requirements.lock` absent) — version drift possible across environments; documented, not in scope.

---

```text
STAGE_5_STATUS = PASS
```
