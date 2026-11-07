"""PostgreSQL Full-Text Search (FTS) vectorless retrieval adapter with SQLite test fallback."""

import logging
import re
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, DocumentChunk
from app.vectorstores.base import (
    VectorPoint,
    VectorSearchResult,
    VectorStore,
    VectorStoreFilter,
)

logger = logging.getLogger("mmaip.vectorstores.fts")


class PostgresFTSStore(VectorStore):
    """PostgreSQL Full-Text Search engine delivering pure lexical keyword retrieval without vector dependencies."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @property
    def store_name(self) -> str:
        return "fts"

    async def upsert(
        self,
        points: list[VectorPoint],
        tenant_id: uuid.UUID,
        knowledge_base_id: uuid.UUID,
    ) -> int:
        # In FTS mode, chunks in DocumentChunk are already indexed by the relational DB.
        return len(points)

    async def search(
        self,
        query_vector: list[float],
        filter_criteria: VectorStoreFilter,
        top_k: int = 8,
    ) -> list[VectorSearchResult]:
        # Vector search is not applicable in FTS mode; returns empty if called directly.
        return []

    async def search_lexical(
        self,
        query_text: str,
        filter_criteria: VectorStoreFilter,
        top_k: int = 8,
    ) -> list[VectorSearchResult]:
        """Perform full-text lexical search against document chunks."""
        cleaned_query = query_text.strip()
        if not cleaned_query:
            return []

        bind = self.session.bind
        dialect_name = bind.dialect.name if bind else "postgresql"

        # Base query joined with Document
        stmt = (
            select(
                DocumentChunk.id,
                DocumentChunk.document_id,
                DocumentChunk.knowledge_base_id,
                DocumentChunk.content,
                DocumentChunk.page_number,
                DocumentChunk.heading_path,
                DocumentChunk.chunk_index,
                Document.filename,
                Document.department_id,
                Document.access_level,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.tenant_id == filter_criteria.tenant_id,
                DocumentChunk.knowledge_base_id.in_(filter_criteria.knowledge_base_ids),
                Document.status != "DELETED",
            )
        )

        if filter_criteria.document_ids:
            stmt = stmt.where(DocumentChunk.document_id.in_(filter_criteria.document_ids))

        # Enforce department isolation
        if not filter_criteria.is_admin and filter_criteria.user_department_id:
            stmt = stmt.where(
                (Document.department_id.is_(None)) |
                (Document.department_id == filter_criteria.user_department_id)
            )

        # 1. PostgreSQL native full-text search with ts_rank_cd
        if dialect_name == "postgresql":
            # Sanitize search query for plainto_tsquery
            ts_query = func.plainto_tsquery("english", cleaned_query)
            ts_vector = func.to_tsvector("english", DocumentChunk.content)
            rank_col = func.ts_rank_cd(ts_vector, ts_query).label("rank_score")

            stmt = (
                stmt.add_columns(rank_col)
                .where(ts_vector.op("@@")(ts_query))
                .order_by(rank_col.desc())
                .limit(top_k)
            )

            rows = (await self.session.execute(stmt)).all()
            results: list[VectorSearchResult] = []
            for rank, r in enumerate(rows, start=1):
                cid, doc_id, kb_id, content, page_num, heading, chunk_idx, doc_title, dept_id, acc_lvl, score = r
                results.append(
                    VectorSearchResult(
                        chunk_id=cid,
                        document_id=doc_id,
                        knowledge_base_id=kb_id,
                        score=float(score),
                        content=content,
                        metadata={
                            "department_id": str(dept_id) if dept_id else None,
                            "access_level": acc_lvl,
                        },
                        rank=rank,
                        document_title=doc_title,
                        page_number=page_num,
                        heading_path=heading,
                        chunk_index=chunk_idx,
                        retrieval_source="lexical",
                    )
                )
            return results

        # 2. SQLite / in-memory test fallback: tokenized keyword relevance
        tokens = [t.lower() for t in re.findall(r"\w+", cleaned_query) if len(t) > 1]
        if not tokens:
            tokens = [cleaned_query.lower()]

        # Filter chunks that contain any of the query tokens
        token_filters = [DocumentChunk.content.ilike(f"%{token}%") for token in tokens]
        stmt = stmt.where(or_(*token_filters))

        rows = (await self.session.execute(stmt)).all()

        scored_chunks = []
        for r in rows:
            cid, doc_id, kb_id, content, page_num, heading, chunk_idx, doc_title, dept_id, acc_lvl = r
            content_lower = content.lower()
            # Simple term-frequency score: sum of matches weighted by token length
            score = 0.0
            for t in tokens:
                count = content_lower.count(t)
                if count > 0:
                    score += count * (len(t) ** 0.5)

            if score > 0:
                scored_chunks.append((
                    score,
                    cid,
                    doc_id,
                    kb_id,
                    content,
                    page_num,
                    heading,
                    chunk_idx,
                    doc_title,
                    dept_id,
                    acc_lvl,
                ))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = scored_chunks[:top_k]

        results = []
        for rank, item in enumerate(top_chunks, start=1):
            score, cid, doc_id, kb_id, content, page_num, heading, chunk_idx, doc_title, dept_id, acc_lvl = item
            results.append(
                VectorSearchResult(
                    chunk_id=cid,
                    document_id=doc_id,
                    knowledge_base_id=kb_id,
                    score=float(score),
                    content=content,
                    metadata={
                        "department_id": str(dept_id) if dept_id else None,
                        "access_level": acc_lvl,
                    },
                    rank=rank,
                    document_title=doc_title,
                    page_number=page_num,
                    heading_path=heading,
                    chunk_index=chunk_idx,
                    retrieval_source="lexical",
                )
            )

        return results

    async def delete(self, chunk_ids: list[uuid.UUID], tenant_id: uuid.UUID) -> int:
        return len(chunk_ids)

    async def delete_document(self, document_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        return 1

    async def check_health(self) -> dict[str, Any]:
        bind = self.session.bind
        dialect = bind.dialect.name if bind else "unknown"
        return {
            "status": "healthy",
            "store": "fts",
            "driver": dialect,
            "embeddings_required": False,
        }
