# Milestone 05 — Initial Technical Inspection Before Remediation

**Audit Phase:** Pre-Remediation Technical Architecture Inspection  
**Date:** 2026-11-08  
**Scope:** Static inspection of database models, cryptography API, ingestion service, vector stores, and package dependencies.

---

## 1. Technical Findings

### 1.1 Assistant BYOK Storage & Cryptography API
- **Model Definition:** `backend/app/models/assistant.py` defines the `Assistant` model with fields for `llm_provider`, `temperature`, `max_tokens`, `system_prompt`, and `status`. Prior to remediation, `byok_encrypted_key` was not mapped on `Assistant` in the model or migration `0004_assistants_and_conversations.py`.
- **Crypto API:** `backend/app/core/crypto.py` implements AES/Fernet encryption via `encrypt_secret` and `decrypt_secret`. Canonical aliases `encrypt_credential` and `decrypt_credential` were added to match specification requirements.
- **Key Derivation:** `derive_fernet_key` generates deterministic 32-byte URL-safe base64 keys from arbitrary string key material using SHA-256 digests.

### 1.2 IngestionService & Reindexing Architecture
- **Service Constructor:**
  ```python
  class IngestionService:
      def __init__(self, session: AsyncSession, tenant_id: uuid.UUID | str):
  ```
- **Entrypoint Signature:**
  ```python
  async def reindex_knowledge_base(self, knowledge_base_id: uuid.UUID | str) -> Any:
  ```
- **Reindexing Pipeline Execution:**
  1. Resolves `RetrievalConfig` via `RetrievalRepository.get_or_create_config(kb_id)`.
  2. Queries all active `DocumentChunk` records joined with `Document` where `Document.status != 'DELETED'`.
  3. Enqueues tracked `EmbeddingJob` (status: `PROCESSING`, stage: `EMBEDDING`).
  4. Generates embeddings via `EmbeddingService.embed_chunks`.
  5. When `ret_cfg.vector_store == "qdrant"`:
     - Obtains `QdrantVectorStore` instance.
     - Constructs `VectorPoint` items with payloads (`document_id`, `chunk_id`, `embedding_version`, `provider`, `model`, `content`).
     - Calls `await qdrant_store.upsert(qpoints, self.tenant_id, kb_id)`.
  6. Updates `EmbeddingJob` status to `COMPLETED`.

### 1.3 Qdrant Vector Store Adapter
- **Collection Management:** `QdrantVectorStore._ensure_collection(dimensions)` creates collection `mmaip_knowledge_chunks_{dimensions}` if not present, configuring `Cosine` distance and payload keyword indexes on `tenant_id`, `knowledge_base_id`, and `embedding_version`.
- **Tenant Filter Enforcement:** `QdrantVectorStore.search` constructs mandatory `qmodels.FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id)))` ensuring cross-tenant data is completely unreachable.

### 1.4 Packaging Dependencies (`pyproject.toml`)
- `backend/pyproject.toml` defines runtime dependencies under `[project.dependencies]`.
- Testing tools (`pytest`, `pytest-asyncio`, `ruff`, `mypy`) are declared under `[project.optional-dependencies] dev`.
- Running `pip install -e .` without `[dev]` omits pytest, causing test execution failure on clean runner environments.
