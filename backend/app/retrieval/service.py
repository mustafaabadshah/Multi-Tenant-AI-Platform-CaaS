"""Unified Retrieval Service orchestrating lexical, semantic, hybrid, fusion, and authorization."""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt_secret
from app.embeddings.base import EmbeddingProviderConfig
from app.embeddings.registry import get_embedding_registry
from app.models.knowledge import RetrievalConfig
from app.retrieval.authorization import RetrievalAuthorizer
from app.retrieval.citations import FormattedCitation, format_citations
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.reranking import get_reranker
from app.vectorstores.base import VectorSearchResult, VectorStoreFilter
from app.vectorstores.fts_store import PostgresFTSStore
from app.vectorstores.registry import get_vector_store

logger = logging.getLogger("mmaip.retrieval.service")


@dataclass
class SearchResponse:
    """Standardized search response returned to clients and assistants."""
    query: str
    retrieval_mode: str
    vector_store: str
    embedding_provider: str
    total_results: int
    results: list[VectorSearchResult]
    citations: list[FormattedCitation]
    diagnostics: dict[str, Any]


class RetrievalService:
    """Enterprise hybrid retrieval engine delivering secure, multi-tenant knowledge retrieval."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        is_admin: bool = False,
        user_department_id: Optional[uuid.UUID] = None,
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.is_admin = is_admin
        self.user_department_id = user_department_id
        self.authorizer = RetrievalAuthorizer(session, tenant_id)
        self.embedding_registry = get_embedding_registry()

    async def _resolve_kb_config(self, kb_id: uuid.UUID) -> Optional[RetrievalConfig]:
        """Fetch RetrievalConfig for specific knowledge base."""
        stmt = select(RetrievalConfig).where(
            RetrievalConfig.tenant_id == self.tenant_id,
            RetrievalConfig.knowledge_base_id == kb_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def search(
        self,
        query: str,
        knowledge_base_ids: list[uuid.UUID],
        mode: Optional[str] = None,
        vector_store_type: Optional[str] = None,
        top_k: Optional[int] = None,
        document_ids: Optional[list[uuid.UUID]] = None,
    ) -> SearchResponse:
        """Execute authorization-aware retrieval across authorized knowledge bases."""
        start_time = time.perf_counter()
        timing: dict[str, int] = {}

        # 1. Authorize knowledge bases
        await self.authorizer.validate_knowledge_bases(
            knowledge_base_ids,
            self.user_department_id,
            self.is_admin,
        )

        # 2. Resolve retrieval config (use first KB config or system defaults)
        ret_cfg = await self._resolve_kb_config(knowledge_base_ids[0]) if knowledge_base_ids else None
        target_mode = (mode or (ret_cfg.retrieval_mode if ret_cfg else settings.DEFAULT_RETRIEVAL_MODE)).lower()
        target_store_type = (vector_store_type or (ret_cfg.vector_store if ret_cfg else settings.DEFAULT_VECTOR_STORE)).lower()
        effective_top_k = min(top_k or (ret_cfg.top_k if ret_cfg else 8), settings.MAX_TOP_K)

        embedding_version = ret_cfg.embedding_version if ret_cfg else 1
        rrf_k = ret_cfg.rrf_k if ret_cfg else settings.RRF_K_CONSTANT
        emb_provider_name = ret_cfg.embedding_provider if ret_cfg else settings.DEFAULT_EMBEDDING_PROVIDER
        emb_model = ret_cfg.embedding_model if ret_cfg else settings.DEFAULT_EMBEDDING_MODEL
        emb_dims = ret_cfg.embedding_dimensions if ret_cfg else settings.DEFAULT_EMBEDDING_DIMENSIONS

        # If store is explicitly 'fts', mode must be lexical
        if target_store_type == "fts":
            target_mode = "lexical"

        # 3. Create VectorStoreFilter
        filter_criteria = VectorStoreFilter(
            tenant_id=self.tenant_id,
            knowledge_base_ids=knowledge_base_ids,
            document_ids=document_ids,
            embedding_version=embedding_version,
            user_department_id=self.user_department_id,
            is_admin=self.is_admin,
            expected_dimensions=emb_dims if target_mode in ("semantic", "hybrid") else None,
        )

        lexical_candidates: list[VectorSearchResult] = []
        semantic_candidates: list[VectorSearchResult] = []
        fusion_diagnostics: dict[str, Any] = {}

        fts_store = PostgresFTSStore(self.session)
        target_vstore = get_vector_store(target_store_type, session=self.session)

        # 4. Lexical Search Phase
        if target_mode in ("lexical", "hybrid"):
            t0 = time.perf_counter()
            lexical_candidates = await fts_store.search_lexical(
                query,
                filter_criteria,
                top_k=effective_top_k * 2 if target_mode == "hybrid" else effective_top_k,
            )
            timing["lexical_latency_ms"] = int((time.perf_counter() - t0) * 1000)

        # 5. Semantic Search Phase
        fallback_to_lexical = False
        embedding_error: Optional[str] = None
        if target_mode in ("semantic", "hybrid"):
            t0 = time.perf_counter()
            plain_key = decrypt_secret(ret_cfg.encrypted_api_key) if ret_cfg and ret_cfg.encrypted_api_key else None
            provider = self.embedding_registry.get_provider(emb_provider_name)
            prov_cfg = EmbeddingProviderConfig(
                provider_name=emb_provider_name,
                model_name=emb_model,
                dimensions=emb_dims,
                api_key=plain_key,
                timeout_seconds=settings.EMBEDDING_TIMEOUT_SECONDS,
                max_retries=settings.EMBEDDING_MAX_RETRIES,
            )
            try:
                query_emb = await provider.embed_text(query, prov_cfg)
                timing["embedding_latency_ms"] = int((time.perf_counter() - t0) * 1000)

                t1 = time.perf_counter()
                semantic_candidates = await target_vstore.search(
                    query_emb.vector,
                    filter_criteria,
                    top_k=effective_top_k * 2 if target_mode == "hybrid" else effective_top_k,
                )
                timing["vector_search_latency_ms"] = int((time.perf_counter() - t1) * 1000)
            except Exception as emb_err:
                fallback_to_lexical = True
                embedding_error = str(emb_err)
                logger.warning(f"Semantic search phase failed ({emb_err}); gracefully continuing with lexical candidates")
                if target_mode == "semantic" and not lexical_candidates:
                    lexical_candidates = await fts_store.search_lexical(
                        query,
                        filter_criteria,
                        top_k=effective_top_k,
                    )

        # 6. Candidate Merging / Fusion
        candidates: list[VectorSearchResult] = []
        if target_mode == "hybrid":
            t0 = time.perf_counter()
            candidates, fusion_diagnostics = reciprocal_rank_fusion(
                lexical_results=lexical_candidates,
                semantic_results=semantic_candidates,
                k=rrf_k,
                top_k=effective_top_k,
            )
            timing["fusion_latency_ms"] = int((time.perf_counter() - t0) * 1000)
        elif target_mode == "semantic":
            candidates = semantic_candidates[:effective_top_k] if semantic_candidates else lexical_candidates[:effective_top_k]
        else:
            candidates = lexical_candidates[:effective_top_k]

        # 7. Authoritative Security Filter (secondary verification against authoritative DB)
        t0 = time.perf_counter()
        authorized_candidates = await self.authorizer.filter_authorized_candidates(
            candidates,
            self.user_department_id,
            self.is_admin,
        )
        timing["security_filter_latency_ms"] = int((time.perf_counter() - t0) * 1000)

        # 8. Optional Reranking
        reranker = get_reranker(ret_cfg.rerank_provider if ret_cfg and ret_cfg.rerank_enabled else None)
        final_candidates = await reranker.rerank(query, authorized_candidates, top_k=effective_top_k)

        # 9. Format citations
        citations = format_citations(final_candidates)

        total_latency_ms = int((time.perf_counter() - start_time) * 1000)
        timing["total_latency_ms"] = total_latency_ms

        retrieval_mode_actual = "lexical" if (fallback_to_lexical and not semantic_candidates) else target_mode

        diagnostics = {
            "retrieval_mode": target_mode,
            "retrieval_mode_actual": retrieval_mode_actual,
            "fallback_to_lexical": fallback_to_lexical,
            "embedding_error": embedding_error,
            "vector_store": target_store_type,
            "embedding_provider": emb_provider_name if target_mode != "lexical" else "none",
            "embedding_model": emb_model if target_mode != "lexical" else "none",
            "timing_ms": timing,
            "fusion": fusion_diagnostics,
            "candidates_found": len(candidates),
            "authorized_count": len(final_candidates),
        }

        return SearchResponse(
            query=query,
            retrieval_mode=target_mode,
            vector_store=target_store_type,
            embedding_provider=emb_provider_name if target_mode != "lexical" else "none",
            total_results=len(final_candidates),
            results=final_candidates,
            citations=citations,
            diagnostics=diagnostics,
        )
