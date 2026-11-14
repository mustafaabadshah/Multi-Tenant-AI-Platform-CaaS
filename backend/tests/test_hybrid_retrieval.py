"""Unit tests for Hybrid Retrieval, Reciprocal Rank Fusion (RRF), and Citation Formatting."""

import uuid

import pytest

from app.retrieval.citations import format_citations
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.reranking import NoOpReranker, get_reranker
from app.vectorstores.base import VectorSearchResult


def test_rrf_fusion_overlapping_item_ranks_highest():
    kb_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    chunk_overlap = uuid.uuid4()
    chunk_lex_only = uuid.uuid4()
    chunk_sem_only = uuid.uuid4()

    # Lexical results: chunk_overlap is rank 1, chunk_lex_only is rank 2
    lexical = [
        VectorSearchResult(
            chunk_id=chunk_overlap,
            document_id=doc_id,
            knowledge_base_id=kb_id,
            score=0.85,
            content="Overlap chunk text",
            rank=1,
            retrieval_source="lexical",
        ),
        VectorSearchResult(
            chunk_id=chunk_lex_only,
            document_id=doc_id,
            knowledge_base_id=kb_id,
            score=0.72,
            content="Lexical only text",
            rank=2,
            retrieval_source="lexical",
        ),
    ]

    # Semantic results: chunk_overlap is rank 1, chunk_sem_only is rank 2
    semantic = [
        VectorSearchResult(
            chunk_id=chunk_overlap,
            document_id=doc_id,
            knowledge_base_id=kb_id,
            score=0.91,
            content="Overlap chunk text",
            rank=1,
            retrieval_source="semantic",
        ),
        VectorSearchResult(
            chunk_id=chunk_sem_only,
            document_id=doc_id,
            knowledge_base_id=kb_id,
            score=0.82,
            content="Semantic only text",
            rank=2,
            retrieval_source="semantic",
        ),
    ]

    # Execute RRF fusion with k=60
    fused, diag = reciprocal_rank_fusion(lexical, semantic, k=60, top_k=5)

    assert len(fused) == 3
    assert diag["unique_candidates"] == 3
    assert diag["overlap_count"] == 1

    # Overlapping item must receive highest fused score: 1/(60+1) + 1/(60+1) = 2/61 ≈ 0.032787
    assert fused[0].chunk_id == chunk_overlap
    assert fused[0].retrieval_source == "hybrid"
    assert fused[0].rank == 1
    assert fused[0].metadata["lexical_rank"] == 1
    assert fused[0].metadata["semantic_rank"] == 1
    assert fused[0].score > fused[1].score


def test_citation_formatting_provenance():
    cid = uuid.uuid4()
    did = uuid.uuid4()
    kbid = uuid.uuid4()

    item = VectorSearchResult(
        chunk_id=cid,
        document_id=did,
        knowledge_base_id=kbid,
        score=0.95,
        content="Antigravity security architecture requires strict tenant scoping on every SQL query.",
        document_title="Security_Guidelines.pdf",
        page_number=12,
        heading_path="Tenant Isolation > Repositories",
        chunk_index=3,
        retrieval_source="hybrid",
    )

    citations = format_citations([item])
    assert len(citations) == 1
    c = citations[0]
    assert c.citation_index == 1
    assert c.document_title == "Security_Guidelines.pdf"
    assert c.page_number == 12
    assert c.heading_path == "Tenant Isolation > Repositories"
    assert "[1] Security_Guidelines.pdf, Page 12, § Tenant Isolation > Repositories" in c.label
    assert "Antigravity security architecture" in c.snippet


@pytest.mark.asyncio
async def test_reranker_pass_through():
    reranker = get_reranker()
    assert isinstance(reranker, NoOpReranker)
    candidates = [
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=uuid.uuid4(),
            score=0.9,
            content="Content A",
        ),
        VectorSearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            knowledge_base_id=uuid.uuid4(),
            score=0.8,
            content="Content B",
        ),
    ]
    out = await reranker.rerank("test query", candidates, top_k=1)
    assert len(out) == 1
    assert out[0].score == 0.9
