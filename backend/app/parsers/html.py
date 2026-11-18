"""Deterministic, safe HTML Document Parser for Multi-Tenant AI Platform (CaaS).

Extracts clean article text, headings, code blocks, lists, and tables using
WebContentExtractor while stripping scripts, styles, and navigation boilerplate.
"""

import re
import time
from typing import Any

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
)
from app.services.web.extractor import WebContentExtractor


class HTMLParser(DocumentParser):
    """Secure HTML document parser supporting .html and .htm files."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".html", ".htm"}

    @property
    def supported_mime_types(self) -> set[str]:
        return {"text/html", "application/xhtml+xml"}

    @property
    def parser_name(self) -> str:
        return "deterministic_html_parser"

    @property
    def parser_version(self) -> str:
        return "1.0.0"

    def validate(self, content: bytes, filename: str) -> bool:
        """Validate if content is safe and recognizable HTML."""
        if not content or len(content) == 0:
            return False

        # Must not contain null bytes (binary files)
        if content.startswith(b"\x00") or b"\x00" in content[:1024]:
            return False

        ext = filename.lower() if filename else ""
        if ext.endswith((".html", ".htm")):
            return True

        # Sniff HTML opening tags in first 2048 bytes
        header_sample = content[:2048].lower()
        html_signatures = (
            b"<!doctype html",
            b"<html",
            b"<head",
            b"<body",
            b"<title",
            b"<?xml",
        )
        return any(sig in header_sample for sig in html_signatures)

    async def extract(
        self,
        content: bytes,
        filename: str,
        mime_type: str | None = None,
    ) -> ExtractedDocument:
        """Extract structured sections, code, and text from HTML bytes."""
        start_time = time.perf_counter()
        warnings: list[str] = []

        # 1. Safe multi-encoding decode
        decoded_text = ""
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"):
            try:
                decoded_text = content.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if not decoded_text:
            decoded_text = content.decode("utf-8", errors="replace")

        # 2. Extract structured content using WebContentExtractor
        extracted = WebContentExtractor.extract(decoded_text, source_url=filename)
        cleaned_markdown = extracted.get("content", "").strip()

        if not cleaned_markdown:
            from app.services.ingestion.limits import UnparseableDocumentError
            raise UnparseableDocumentError(f"HTML document '{filename}' contains no readable or extractable text content.")

        title = extracted.get("title") or filename
        description = extracted.get("description", "")

        # 3. Parse Markdown headings into structured sections
        lines = cleaned_markdown.splitlines()
        sections: list[ExtractedSection] = []
        current_heading = title
        current_level = 1
        current_content_lines: list[str] = []
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

        for line in lines:
            match = heading_pattern.match(line.strip())
            if match:
                if current_content_lines:
                    sections.append(
                        ExtractedSection(
                            heading=current_heading,
                            level=current_level,
                            content="\n".join(current_content_lines).strip(),
                            page_number=1,
                        )
                    )
                    current_content_lines = []
                current_level = len(match.group(1))
                current_heading = match.group(2).strip()
            else:
                current_content_lines.append(line)

        if current_content_lines:
            sections.append(
                ExtractedSection(
                    heading=current_heading,
                    level=current_level,
                    content="\n".join(current_content_lines).strip(),
                    page_number=1,
                )
            )

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        page = ExtractedPage(
            page_number=1,
            text=cleaned_markdown,
            metadata={
                "sections_count": len(sections),
                "title": title,
                "description": description,
            },
        )

        return ExtractedDocument(
            source_filename=filename,
            mime_type=mime_type or "text/html",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            title=title,
            text=cleaned_markdown,
            pages=[page],
            sections=sections,
            metadata={
                "description": description,
                "is_js_required": extracted.get("is_js_required", False),
                "is_blocked": extracted.get("is_blocked", False),
                "char_count": extracted.get("char_count", len(cleaned_markdown)),
            },
            warnings=warnings,
            extraction_stats={
                "duration_ms": duration_ms,
                "char_count": len(cleaned_markdown),
                "sections_count": len(sections),
            },
        )
