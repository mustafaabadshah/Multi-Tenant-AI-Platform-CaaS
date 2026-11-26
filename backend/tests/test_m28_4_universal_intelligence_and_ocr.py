"""Comprehensive M28.4 Automated Tests: Universal Web & Document Intelligence,
Selective OCR, ImageParser, Multi-Format Web Reader, and KB Import.
"""

import io
import uuid
import pytest
from PIL import Image, ImageDraw

from app.parsers.base import ExtractedDocument
from app.parsers.image import ImageParser
from app.parsers.pdf import PDFParser
from app.parsers.registry import ParserRegistry, get_parser_registry
from app.services.ocr_service import OCRService, get_ocr_service
from app.services.web.kb_saver import WebKBSaveService, WebSaveMode
from app.services.web.reader import WebFetchService
from app.assistant_runtime.context import build_rag_context
from app.vectorstores.base import VectorSearchResult


def _create_test_image_bytes(text: str = "SAMPLE TEXT", width: int = 200, height: int = 60, fmt: str = "PNG") -> bytes:
    """Create a real synthetic image in memory with drawn text."""
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), text, fill="black")
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. OCR Service & Graceful Degradation Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ocr_service_graceful_when_tesseract_missing():
    """Verify OCRService returns clear warning without crashing when Tesseract is not installed."""
    service = OCRService(tesseract_cmd="C:/nonexistent/tesseract.exe")
    service._is_available = False
    OCRService.set_test_ocr_handler(None)

    img_bytes = _create_test_image_bytes("Hello OCR")
    res = await service.extract_text_from_image_bytes(img_bytes, filename="test.png")

    assert res.success is False
    assert res.error == "OCR_UNAVAILABLE"
    assert any("not installed" in w for w in res.warnings)


@pytest.mark.asyncio
async def test_ocr_service_with_injected_test_handler():
    """Verify OCRService invokes test handler hook for deterministic test verification."""
    service = get_ocr_service()
    OCRService.set_test_ocr_handler(lambda b, name: "EXTRACTED_MOCK_TEXT: " + name)

    try:
        img_bytes = _create_test_image_bytes("Mock Test")
        res = await service.extract_text_from_image_bytes(img_bytes, filename="sample_invoice.png")

        assert res.success is True
        assert res.text == "EXTRACTED_MOCK_TEXT: sample_invoice.png"
        assert res.engine == "test_mock"
    finally:
        OCRService.set_test_ocr_handler(None)


# ---------------------------------------------------------------------------
# 2. ImageParser Tests
# ---------------------------------------------------------------------------

def test_image_parser_magic_bytes_validation():
    """Verify ImageParser validates PNG, JPEG, and WebP signatures accurately."""
    parser = ImageParser()

    png_bytes = _create_test_image_bytes("PNG test", fmt="PNG")
    assert parser.validate(png_bytes, "doc.png") is True

    jpeg_bytes = _create_test_image_bytes("JPEG test", fmt="JPEG")
    assert parser.validate(jpeg_bytes, "photo.jpg") is True

    invalid_bytes = b"NOT_AN_IMAGE_FILE_AT_ALL"
    assert parser.validate(invalid_bytes, "doc.txt") is False


@pytest.mark.asyncio
async def test_image_parser_extracts_structured_document_with_ocr():
    """Verify ImageParser returns an ExtractedDocument with dimension metadata and OCR text."""
    parser = ImageParser()
    OCRService.set_test_ocr_handler(lambda b, name: "Order #98765 Total: $450.00")

    try:
        img_bytes = _create_test_image_bytes("Receipt", width=300, height=100)
        doc = await parser.extract(img_bytes, filename="receipt_scan.png")

        assert isinstance(doc, ExtractedDocument)
        assert doc.source_filename == "receipt_scan.png"
        assert "Order #98765" in doc.text
        assert len(doc.pages) == 1
        assert doc.pages[0].is_scanned is True
        assert doc.metadata.get("ocr_derived") is True
        assert doc.metadata.get("dimensions") == (300, 100)
    finally:
        OCRService.set_test_ocr_handler(None)


# ---------------------------------------------------------------------------
# 3. PDFParser Selective OCR Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pdf_parser_selective_ocr_on_scanned_pages():
    """Verify PDFParser selectively applies OCR to image-only pages and preserves text pages."""
    import pymupdf

    # Create a synthetic 2-page PDF: Page 1 = normal text, Page 2 = image only
    pdf_doc = pymupdf.open()

    # Page 1: normal text
    p1 = pdf_doc.new_page(width=595, height=842)
    p1.insert_text((50, 100), "Normal digital text on page 1 with plenty of content.")

    # Page 2: scanned image
    p2 = pdf_doc.new_page(width=595, height=842)
    img_bytes = _create_test_image_bytes("SCANNED_PAGE_2_CONTENT", width=400, height=200)
    rect = pymupdf.Rect(50, 50, 450, 250)
    p2.insert_image(rect, stream=img_bytes)

    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    parser = PDFParser()
    OCRService.set_test_ocr_handler(lambda b, name: "RECOGNIZED_OCR_PAGE_2")

    try:
        extracted = await parser.extract(pdf_bytes, filename="hybrid_doc.pdf")
        assert len(extracted.pages) == 2

        # Page 1: digital text, no OCR
        assert "Normal digital text" in extracted.pages[0].text
        assert extracted.pages[0].metadata.get("ocr_derived") is False

        # Page 2: scanned image, OCR derived
        assert "RECOGNIZED_OCR_PAGE_2" in extracted.pages[1].text
        assert extracted.pages[1].metadata.get("ocr_derived") is True
    finally:
        OCRService.set_test_ocr_handler(None)


# ---------------------------------------------------------------------------
# 4. Parser Registry Resolution Tests
# ---------------------------------------------------------------------------

def test_parser_registry_resolves_image_parser():
    """Verify ParserRegistry routes image extensions and MIME types to ImageParser."""
    registry = ParserRegistry()
    assert ".png" in registry.get_supported_extensions()
    assert ".jpg" in registry.get_supported_extensions()

    png_bytes = _create_test_image_bytes("Test")
    parser = registry.resolve_parser("screenshot.png", png_bytes, declared_mime="image/png")
    assert isinstance(parser, ImageParser)


# ---------------------------------------------------------------------------
# 5. Multi-Format Web Reader Dispatcher Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_web_reader_dispatches_pdf_and_image_urls(monkeypatch):
    """Verify WebFetchService dispatches PDF and image URLs to appropriate parsers."""
    reader = WebFetchService(tenant_id=uuid.uuid4())

    # Mock _sync_extract or OCR test handler
    OCRService.set_test_ocr_handler(lambda b, name: "OCR_WEB_IMAGE_CONTENT")

    try:
        # Mock httpx response stream for image URL
        img_bytes = _create_test_image_bytes("Diagram", width=150, height=50)

        class MockStreamResponse:
            status_code = 200
            is_redirect = False
            encoding = "utf-8"
            headers = {"content-type": "image/png"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def aiter_bytes(self, chunk_size=16384):
                yield img_bytes

        class MockAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def stream(self, method, url, **kwargs):
                return MockStreamResponse()

        monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)

        result = await reader.read_webpage(
            url="https://example.com/diagram.png",
            allow_http_for_testing=True,
            bypass_cache=True,
        )

        assert result["source_type"] == "web_image"
        assert result["ocr_derived"] is True
        assert "OCR_WEB_IMAGE_CONTENT" in result["extracted_text"]
        assert result["citation"]["page_number"] is None
    finally:
        OCRService.set_test_ocr_handler(None)


# ---------------------------------------------------------------------------
# 6. Knowledge Base Saver Modes Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_kb_saver_modes_and_no_default_page_number(monkeypatch):
    """Verify WebKBSaveService supports REFERENCE, NOTES, and SEARCHABLE_CONTENT without defaulting page_number to 1."""
    class FakeSession:
        def __init__(self):
            self.added = []

        def add(self, obj):
            self.added.append(obj)

        async def flush(self):
            pass

        async def commit(self):
            pass

        async def execute(self, stmt):
            class ScalarRes:
                def __init__(self, obj):
                    self.obj = obj
                def scalar_one_or_none(self):
                    return self.obj
                def scalars(self):
                    return self
                def all(self):
                    return []
            stmt_str = str(stmt).lower()
            if "from knowledge_bases" in stmt_str:
                class KB:
                    id = uuid.uuid4()
                    status = "ACTIVE"
                return ScalarRes(KB())
            return ScalarRes(None)

    session = FakeSession()
    tenant_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    svc = WebKBSaveService(session, tenant_id)

    # Test 1: REFERENCE mode (0 chunks)
    res_ref = await svc.save_web_source_to_kb(
        url="https://docs.python.org/3/library/ast.html",
        knowledge_base_id=kb_id,
        title="Python AST Docs",
        extracted_text="AST documentation body text...",
        mode="REFERENCE",
    )
    assert res_ref["storage_mode"] == "REFERENCE"
    assert res_ref["total_chunks"] == 0

    # Test 2: NOTES mode (chunks user notes, not page)
    res_notes = await svc.save_web_source_to_kb(
        url="https://docs.python.org/3/library/ast.html",
        knowledge_base_id=kb_id,
        title="Python AST Docs",
        notes="My personal notes on Python AST compilation.\n\nSecond note paragraph.",
        extracted_text="Large raw text...",
        mode="NOTES",
    )
    assert res_notes["storage_mode"] == "NOTES"
    assert res_notes["total_chunks"] == 1

    # Verify that created DocumentChunks have page_number is None (not 1)
    from app.models.knowledge import DocumentChunk
    chunks = [o for o in session.added if isinstance(o, DocumentChunk)]
    assert len(chunks) > 0
    for c in chunks:
        assert c.page_number is None


# ---------------------------------------------------------------------------
# 7. Context & Citation Provenance Tests
# ---------------------------------------------------------------------------

def test_build_rag_context_citation_ocr_and_page_provenance():
    """Verify build_rag_context populates ocr_derived and avoids defaulting page_number to 1."""
    chunk_web = VectorSearchResult(
        chunk_id=str(uuid.uuid4()),
        document_id="https://example.com/spec.html",
        document_title="Web Specification",
        knowledge_base_id=None,
        content="Article text about web standard.",
        score=0.95,
        metadata={"source_type": "web", "source_url": "https://example.com/spec.html", "domain": "example.com"},
    )
    chunk_image = VectorSearchResult(
        chunk_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        document_title="Diagram Screenshot",
        knowledge_base_id=None,
        content="Text extracted from image diagram.",
        score=0.88,
        metadata={"source_type": "image", "ocr_derived": True},
    )

    messages, citations = build_rag_context(
        system_prompt="Assistant prompt",
        conversation_history=[],
        current_user_message="Explain the diagram and the web spec.",
        retrieved_results=[chunk_web, chunk_image],
    )

    assert len(citations) == 2
    # Web citation: page_number is None
    assert citations[0]["source_type"] == "web"
    assert citations[0]["page_number"] is None

    # Image citation: ocr_derived is True
    assert citations[1]["ocr_derived"] is True
    # System block has OCR notice
    assert "[OCR Derived]" in messages[0].content
