"""Reciprocal Rank Fusion (RRF) for combining lexical and semantic search results."""

import logging
import uuid
from dataclasses import replace
from typing import Any

from app.vectorstores.base import VectorSearchResult

logger = logging.getLogger("mmaip.retrieval.fusion")


def reciprocal_rank_fusion(
    lexical_results: list[VectorSearchResult],
    semantic_results: list[VectorSearchResult],
    k: int = 60,
    top_k: int = 8,
) -> tuple[list[VectorSearchResult], dict[str, Any]]:
    """Combine lexical and semantic candidate lists using standard Reciprocal Rank Fusion.

    RRF formula: RRF_score(d) = sum_{r in R} (1 / (k + rank_r(d)))
    """
    scores: dict[uuid.UUID, float] = {}
    items_by_id: dict[uuid.UUID, VectorSearchResult] = {}
    lexical_ranks: dict[uuid.UUID, int] = {}
    semantic_ranks: dict[uuid.UUID, int] = {}
    lexical_scores: dict[uuid.UUID, float] = {}
    semantic_scores: dict[uuid.UUID, float] = {}

    # 1. Process Lexical ranks
    for rank, item in enumerate(lexical_results, start=1):
        cid = item.chunk_id
        items_by_id[cid] = item
        lexical_ranks[cid] = rank
        lexical_scores[cid] = item.score
        rrf_contrib = 1.0 / (k + rank)
        scores[cid] = scores.get(cid, 0.0) + rrf_contrib

    # 2. Process Semantic ranks
    for rank, item in enumerate(semantic_results, start=1):
        cid = item.chunk_id
        if cid not in items_by_id:
            items_by_id[cid] = item
        semantic_ranks[cid] = rank
        semantic_scores[cid] = item.score
        rrf_contrib = 1.0 / (k + rank)
        scores[cid] = scores.get(cid, 0.0) + rrf_contrib

    # 3. Sort candidates by fused RRF score descending
    sorted_chunk_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
    top_chunk_ids = sorted_chunk_ids[:top_k]

    fused_results: list[VectorSearchResult] = []
    for final_rank, cid in enumerate(top_chunk_ids, start=1):
        base_item = items_by_id[cid]
        combined_meta = dict(base_item.metadata)
        combined_meta["lexical_rank"] = lexical_ranks.get(cid)
        combined_meta["semantic_rank"] = semantic_ranks.get(cid)
        combined_meta["lexical_score"] = lexical_scores.get(cid)
        combined_meta["semantic_score"] = semantic_scores.get(cid)
        combined_meta["rrf_score"] = scores[cid]

        fused_item = replace(
            base_item,
            score=round(scores[cid], 6),
            rank=final_rank,
            retrieval_source="hybrid",
            metadata=combined_meta,
        )
        fused_results.append(fused_item)

    overlap_count = len(set(lexical_ranks.keys()).intersection(semantic_ranks.keys()))
    diagnostics = {
        "rrf_k": k,
        "lexical_candidates": len(lexical_results),
        "semantic_candidates": len(semantic_results),
        "unique_candidates": len(items_by_id),
        "overlap_count": overlap_count,
        "final_count": len(fused_results),
    }

    return fused_results, diagnostics
