"""Embedding service handling chunk hashing, idempotency, batching, and persistence."""

import hashlib
import logging
import time
import uuid
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt_secret
from app.embeddings.base import EmbeddingProviderConfig
from app.embeddings.registry import get_embedding_registry
from app.models.knowledge import ChunkEmbedding, DocumentChunk, RetrievalConfig

logger = logging.getLogger("mmaip.embeddings.service")


def compute_chunk_content_hash(content: str, model_name: str, dimensions: int) -> str:
    """Generate deterministic SHA-256 fingerprint for chunk content and model parameters."""
    normalized_input = f"{content}::{model_name}::{dimensions}"
    return hashlib.sha256(normalized_input.encode("utf-8")).hexdigest()


class EmbeddingService:
    """High-level embedding generation service with idempotency and batching."""

    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        self.session = session
        self.tenant_id = tenant_id
        self.registry = get_embedding_registry()

    def _resolve_provider_config(self, ret_config: Optional[RetrievalConfig]) -> EmbeddingProviderConfig:
        """Construct EmbeddingProviderConfig from KnowledgeBase RetrievalConfig or system defaults."""
        provider_name = ret_config.embedding_provider if ret_config else settings.DEFAULT_EMBEDDING_PROVIDER
        model_name = ret_config.embedding_model if ret_config else settings.DEFAULT_EMBEDDING_MODEL
        dimensions = ret_config.embedding_dimensions if ret_config else settings.DEFAULT_EMBEDDING_DIMENSIONS
        batch_size = settings.EMBEDDING_BATCH_SIZE

        # Decrypt user-supplied API key if present
        plain_key = None
        if ret_config and ret_config.encrypted_api_key:
            plain_key = decrypt_secret(ret_config.encrypted_api_key)

        return EmbeddingProviderConfig(
            provider_name=provider_name,
            model_name=model_name,
            dimensions=dimensions,
            api_key=plain_key,
            batch_size=batch_size,
            timeout_seconds=settings.EMBEDDING_TIMEOUT_SECONDS,
            max_retries=settings.EMBEDDING_MAX_RETRIES,
        )

    async def embed_chunks(
        self,
        knowledge_base_id: uuid.UUID,
        chunks: list[DocumentChunk],
        ret_config: Optional[RetrievalConfig] = None,
        embedding_version: int = 1,
    ) -> list[ChunkEmbedding]:
        """Embed a collection of chunks with idempotency checking.

        Existing valid embeddings with matching content hashes are preserved and returned.
        """
        if not chunks:
            return []

        provider_cfg = self._resolve_provider_config(ret_config)
        provider = self.registry.get_provider(provider_cfg.provider_name)
        active_version = ret_config.embedding_version if ret_config else embedding_version

        # 1. Compute content hashes for all incoming chunks
        chunk_hashes: dict[uuid.UUID, str] = {
            c.id: compute_chunk_content_hash(c.content, provider_cfg.model_name, provider_cfg.dimensions)
            for c in chunks
        }

        # 2. Check for existing embeddings with matching chunk_id, version, and content_hash
        chunk_ids = list(chunk_hashes.keys())
        stmt = (
            select(ChunkEmbedding)
            .where(
                ChunkEmbedding.tenant_id == self.tenant_id,
                ChunkEmbedding.knowledge_base_id == knowledge_base_id,
                ChunkEmbedding.chunk_id.in_(chunk_ids),
                ChunkEmbedding.embedding_version == active_version,
            )
        )
        result = await self.session.execute(stmt)
        existing_records = {e.chunk_id: e for e in result.scalars().all()}

        chunks_to_embed: list[DocumentChunk] = []
        final_embeddings: list[ChunkEmbedding] = []

        for c in chunks:
            h = chunk_hashes[c.id]
            existing = existing_records.get(c.id)
            if existing and existing.content_hash == h and existing.vector is not None:
                # Up-to-date embedding already exists
                final_embeddings.append(existing)
            else:
                chunks_to_embed.append(c)

        if not chunks_to_embed:
            logger.info(f"All {len(chunks)} chunks already have valid embeddings (idempotent skip).")
            return final_embeddings

        logger.info(
            f"Embedding {len(chunks_to_embed)} of {len(chunks)} chunks using '{provider_cfg.provider_name}' ({provider_cfg.model_name})"
        )

        # 3. Generate embeddings in batches
        texts = [c.content for c in chunks_to_embed]
        start_time = time.perf_counter()
        batch_result = await provider.embed_batch(texts, provider_cfg)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # 4. Upsert ChunkEmbedding records in DB
        for chunk, vec in zip(chunks_to_embed, batch_result.embeddings, strict=False):
            h = chunk_hashes[chunk.id]
            # Delete any previous record for this chunk & version if stale
            if chunk.id in existing_records:
                await self.session.delete(existing_records[chunk.id])
                await self.session.flush()

            emb_record = ChunkEmbedding(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                knowledge_base_id=knowledge_base_id,
                document_id=chunk.document_id,
                document_version_id=chunk.document_version_id,
                chunk_id=chunk.id,
                embedding_version=active_version,
                provider=provider_cfg.provider_name,
                model=provider_cfg.model_name,
                dimensions=len(vec),
                content_hash=h,
                vector=vec,
            )
            self.session.add(emb_record)
            final_embeddings.append(emb_record)

        await self.session.flush()
        logger.info(f"Successfully generated {len(chunks_to_embed)} embeddings in {elapsed_ms}ms")
        return final_embeddings

    async def delete_document_embeddings(self, document_id: uuid.UUID) -> int:
        """Delete all stored embeddings for a document."""
        stmt = (
            delete(ChunkEmbedding)
            .where(
                ChunkEmbedding.tenant_id == self.tenant_id,
                ChunkEmbedding.document_id == document_id,
            )
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount or 0
