"""Comprehensive tests for all chunking strategies and metadata preservation."""

import uuid
import pytest

from app.chunking.base import ChunkingConfig, estimate_tokens
from app.chunking.markdown import MarkdownHeaderChunking
from app.chunking.recursive import RecursiveCharacterChunking
from app.chunking.registry import get_chunking_registry
from app.chunking.structured import StructuredDocumentChunking
from app.chunking.token import TokenBoundedChunking
from app.parsers.base import ExtractedDocument, ExtractedPage, ExtractedTable


@pytest.fixture
def test_context():
    return {
        "tenant_id": uuid.uuid4(),
        "knowledge_base_id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "document_version_id": uuid.uuid4(),
    }


def test_recursive_character_chunking(test_context):
    """Test recursive character chunking preserves paragraph boundaries and overlaps."""
    doc = ExtractedDocument(
        source_filename="test.txt",
        mime_type="text/plain",
        parser_name="test_parser",
        text=(
            "Paragraph one is relatively short.\n\n"
            "Paragraph two contains somewhat longer text designed to test how splitting works "
            "across boundaries when multiple paragraphs exist in a single document.\n\n"
            "Paragraph three concludes the document."
        ),
    )

    strategy = RecursiveCharacterChunking()
    config = ChunkingConfig(chunk_size=120, chunk_overlap=30)
    chunks = strategy.chunk(doc, test_context, config)

    assert len(chunks) >= 2
    for i, c in enumerate(chunks):
        assert c.metadata.chunk_index == i
        assert c.metadata.tenant_id == str(test_context["tenant_id"])
        assert c.metadata.document_id == str(test_context["document_id"])
        assert c.metadata.chunk_hash is not None
        assert len(c.content) <= 150  # Boundary buffer


def test_markdown_header_chunking(test_context):
    """Test Markdown header chunking preserves hierarchical heading paths."""
    doc = ExtractedDocument(
        source_filename="guide.md",
        mime_type="text/markdown",
        parser_name="test_parser",
        title="Engineering Guide",
        text=(
            "# Engineering Guide\n\nWelcome to engineering.\n\n"
            "## Architecture\n\nArchitecture details and principles.\n\n"
            "### Tenant Isolation\n\nStrict multi-tenant security rules.\n\n"
            "## Deployment\n\nProduction deployment steps."
        ),
    )

    strategy = MarkdownHeaderChunking()
    config = ChunkingConfig(chunk_size=500, chunk_overlap=50)
    chunks = strategy.chunk(doc, test_context, config)

    assert len(chunks) >= 3
    # Check heading paths
    paths = [c.metadata.heading_path for c in chunks if c.metadata.heading_path]
    assert any("Architecture" in p for p in paths)
    assert any("Tenant Isolation" in p for p in paths)
    assert any("Deployment" in p for p in paths)


def test_token_bounded_chunking(test_context):
    """Test token-bounded chunking limits chunks strictly by token estimation."""
    text = " ".join([f"Word{i} is part of a long sentence sequence." for i in range(100)])
    doc = ExtractedDocument(
        source_filename="tokens.txt",
        mime_type="text/plain",
        parser_name="test_parser",
        text=text,
    )

    strategy = TokenBoundedChunking()
    config = ChunkingConfig(chunk_size=1000, chunk_overlap=100, max_tokens=50)
    chunks = strategy.chunk(doc, test_context, config)

    assert len(chunks) > 1
    for c in chunks:
        assert c.metadata.token_count <= 65  # Target 50 + small boundary


def test_structured_table_chunking_preserves_headers(test_context):
    """Test structured chunking repeats table headers on row batches."""
    table = ExtractedTable(
        title="Employees",
        headers=["ID", "Name", "Department"],
        rows=[[str(i), f"Employee {i}", "Engineering"] for i in range(25)],
    )
    doc = ExtractedDocument(
        source_filename="data.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        parser_name="test_parser",
        tables=[table],
        text=table.to_markdown(),
    )

    strategy = StructuredDocumentChunking()
    # Small chunk size forces splitting table into multiple chunks
    config = ChunkingConfig(chunk_size=300, chunk_overlap=0)
    chunks = strategy.chunk(doc, test_context, config)

    assert len(chunks) >= 2
    for c in chunks:
        # Every chunk must contain the column header names
        assert "ID" in c.content
        assert "Name" in c.content
        assert "Department" in c.content
        assert c.metadata.extra.get("is_table") is True


def test_structured_slides_chunking(test_context):
    """Test structured chunking preserves slide titles and numbers on slide chunks."""
    pages = [
        ExtractedPage(page_number=1, text="Introduction slide", metadata={"slide_title": "Slide 1: Intro"}),
        ExtractedPage(page_number=2, text="Architecture slide", metadata={"slide_title": "Slide 2: Architecture"}),
    ]
    doc = ExtractedDocument(
        source_filename="deck.pptx",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        parser_name="test_parser",
        pages=pages,
        text="Slide 1: Intro\nSlide 2: Architecture",
    )

    strategy = StructuredDocumentChunking()
    config = ChunkingConfig(chunk_size=1000, chunk_overlap=100)
    chunks = strategy.chunk(doc, test_context, config)

    assert len(chunks) == 2
    assert chunks[0].metadata.page_number == 1
    assert chunks[0].metadata.heading_path == "Slide 1: Intro"
    assert chunks[1].metadata.page_number == 2
    assert chunks[1].metadata.heading_path == "Slide 2: Architecture"


def test_chunking_registry():
    """Verify ChunkingStrategyRegistry provides all 4 strategies."""
    registry = get_chunking_registry()
    strategies = registry.list_strategies()
    assert "recursive" in strategies
    assert "markdown" in strategies
    assert "token" in strategies
    assert "structured" in strategies
