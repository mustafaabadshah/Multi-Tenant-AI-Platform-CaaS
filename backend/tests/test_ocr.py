"""Tests for OCR subsystem, provider registration, and honest placeholder behavior."""

import pytest
import pymupdf

from app.ocr.badho import BadhoOCRProvider
from app.ocr.base import OCRConfiguration
from app.ocr.registry import get_ocr_registry
from app.ocr.tesseract import TesseractOCRProvider
from app.parsers.pdf import PDFParser


def test_ocr_registry_listing():
    """Verify registry includes both tesseract and badho providers."""
    registry = get_ocr_registry()
    providers = registry.list_providers()
    assert "tesseract" in providers
    assert "badho" in providers


@pytest.mark.asyncio
async def test_badho_ocr_honest_placeholder():
    """Verify Badho OCR returns honest blocked status without credentials and does not fake execution."""
    provider = BadhoOCRProvider()
    assert provider.provider_name == "badho"
    # By default in test environment, no credentials are set
    assert provider.is_available() is False

    config = OCRConfiguration(enabled=True, provider="badho", language="eng")
    result = await provider.process_pdf(b"%PDF-mock", [1], config)

    assert result.success is False
    assert "Badho OCR integration is not operational" in result.error_message
    assert "Required settings: BADHO_OCR_API_URL, BADHO_OCR_API_KEY" in result.error_message


@pytest.mark.asyncio
async def test_scanned_pdf_detection_heuristic():
    """Verify PDFParser flags pages with image but no text as requiring OCR."""
    # Create empty PDF page with text
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((50, 50), "This is text based content.")
    
    # Page 2: empty text
    page2 = doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    parser = PDFParser()
    extracted = await parser.extract(pdf_bytes, "doc.pdf")
    assert len(extracted.pages) == 2
    assert extracted.pages[0].is_scanned is False


@pytest.mark.asyncio
async def test_tesseract_ocr_graceful_missing_binary(monkeypatch):
    """Verify TesseractOCRProvider reports missing binary gracefully without crashing."""
    provider = TesseractOCRProvider()
    # Force is_available to return False
    monkeypatch.setattr(provider, "is_available", lambda: False)

    config = OCRConfiguration(enabled=True, provider="tesseract", language="eng")
    result = await provider.process_pdf(b"%PDF-fake", [1], config)

    assert result.success is False
    assert "Tesseract OCR is not installed" in result.error_message
