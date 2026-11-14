"""Citation formatting and provenance metadata generation for retrieval results."""

import uuid
from dataclasses import dataclass
from typing import Optional

from app.vectorstores.base import VectorSearchResult


@dataclass
class FormattedCitation:
    """Structured citation item linking a retrieved passage directly to its source document."""
    citation_index: int
    label: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_number: Optional[int]
    heading_path: Optional[str]
    chunk_index: int
    snippet: str
    retrieval_source: str
    score: float


def format_citations(results: list[VectorSearchResult]) -> list[FormattedCitation]:
    """Transform search candidates into human-readable, verifiable citations."""
    citations: list[FormattedCitation] = []
    for idx, item in enumerate(results, start=1):
        doc_name = item.document_title or "Untitled Document"
        parts = [f"[{idx}] {doc_name}"]
        if item.page_number is not None:
            parts.append(f"Page {item.page_number}")
        if item.heading_path:
            parts.append(f"§ {item.heading_path}")

        label = ", ".join(parts)
        # Create a preview snippet (approx 200 chars)
        clean_text = " ".join(item.content.split())
        snippet = clean_text[:200] + ("..." if len(clean_text) > 200 else "")

        citations.append(
            FormattedCitation(
                citation_index=idx,
                label=label,
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                document_title=doc_name,
                page_number=item.page_number,
                heading_path=item.heading_path,
                chunk_index=item.chunk_index,
                snippet=snippet,
                retrieval_source=item.retrieval_source,
                score=item.score,
            )
        )

    return citations
