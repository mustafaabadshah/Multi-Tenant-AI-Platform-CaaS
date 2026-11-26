"""Image Document Parser with selective OCR for Multi-Tenant AI Platform (CaaS).

Supports extracting text from PNG, JPEG, and WebP images with dimension inspection
and lightweight OCR extraction.
"""

import io
import time
from pathlib import Path
from typing import Any

from PIL import Image

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
)
from app.services.ocr_service import get_ocr_service


class ImageParser(DocumentParser):
    """Document parser for image files (.png, .jpg, .jpeg, .webp) using OCR."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".png", ".jpg", ".jpeg", ".webp"}

    @property
    def supported_mime_types(self) -> set[str]:
        return {"image/png", "image/jpeg", "image/webp"}

    @property
    def parser_name(self) -> str:
        return "image_ocr_parser"

    @property
    def parser_version(self) -> str:
        return "1.0.0"

    def validate(self, content: bytes, filename: str) -> bool:
        """Validate image magic bytes."""
        if not content or len(content) < 8:
            return False

        # PNG magic bytes: \x89PNG\r\n\x1a\n
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return True

        # JPEG magic bytes: \xff\xd8\xff
        if content.startswith(b"\xff\xd8\xff"):
            return True

        # WebP magic bytes: RIFF....WEBP
        if content[:4] == b"RIFF" and len(content) >= 12 and content[8:12] == b"WEBP":
            return True

        ext = Path(filename).suffix.lower() if filename else ""
        return ext in self.supported_extensions

    async def extract(self, content: bytes, filename: str, mime_type: str | None = None) -> ExtractedDocument:
        start_time = time.perf_counter()
        warnings: list[str] = []
        dimensions = (0, 0)
        img_format = "UNKNOWN"

        try:
            with Image.open(io.BytesIO(content)) as img:
                dimensions = img.size
                img_format = img.format or "IMAGE"
        except Exception as e:
            warnings.append(f"Failed to read image headers: {e}")

        # Execute selective OCR
        ocr_service = get_ocr_service()
        ocr_res = await ocr_service.extract_text_from_image_bytes(content, filename=filename)

        if ocr_res.warnings:
            warnings.extend(ocr_res.warnings)

        clean_text = ocr_res.text.strip() if ocr_res.text else ""
        display_text = clean_text or f"[{img_format} Image: {filename} ({dimensions[0]}x{dimensions[1]})]"

        page = ExtractedPage(
            page_number=1,
            text=display_text,
            is_scanned=True,
            images_count=1,
            metadata={
                "ocr_derived": bool(clean_text),
                "dimensions": dimensions,
                "format": img_format,
            },
        )

        section = ExtractedSection(
            heading=Path(filename).stem,
            level=1,
            content=display_text,
            page_number=1,
            metadata={"ocr_derived": bool(clean_text)},
        )

        elapsed = (time.perf_counter() - start_time) * 1000

        return ExtractedDocument(
            source_filename=filename,
            mime_type=mime_type or f"image/{img_format.lower()}",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            title=Path(filename).stem.replace("_", " ").title(),
            text=display_text,
            pages=[page],
            sections=[section],
            metadata={
                "source_type": "image",
                "dimensions": dimensions,
                "format": img_format,
                "ocr_applied": ocr_res.success,
                "ocr_derived": bool(clean_text),
                "ocr_engine": ocr_res.engine,
            },
            warnings=warnings,
            extraction_stats={
                "execution_time_ms": elapsed,
                "ocr_time_ms": ocr_res.execution_time_ms,
                "text_length": len(clean_text),
            },
        )
