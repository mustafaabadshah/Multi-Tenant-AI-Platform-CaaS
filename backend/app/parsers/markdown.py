"""Markdown Document Parser preserving heading hierarchies and code blocks."""

import re
import time

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
)


class MarkdownParser(DocumentParser):
    """Secure Markdown parser extracting heading hierarchy and sections."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".md", ".markdown"}

    @property
    def supported_mime_types(self) -> set[str]:
        return {"text/markdown", "text/x-markdown"}

    @property
    def parser_name(self) -> str:
        return "python-markdown_Parser"

    def validate(self, content: bytes, filename: str) -> bool:
        """Validate if content is text."""
        return len(content) > 0 and not content.startswith(b"\x00")

    async def extract(self, content: bytes, filename: str, mime_type: str | None = None) -> ExtractedDocument:
        start_time = time.perf_counter()
        warnings: list[str] = []

        decoded_text = ""
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                decoded_text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not decoded_text:
            decoded_text = content.decode("utf-8", errors="replace")

        lines = decoded_text.splitlines()
        sections: list[ExtractedSection] = []
        doc_title = None

        current_heading = "Introduction"
        current_level = 1
        current_content_lines: list[str] = []
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

        for line in lines:
            match = heading_pattern.match(line.strip())
            if match:
                # Flush existing section
                if current_content_lines:
                    sections.append(
                        ExtractedSection(
                            heading=current_heading,
                            level=current_level,
                            content="\n".join(current_content_lines),
                        )
                    )
                    current_content_lines = []

                level = len(match.group(1))
                heading_text = match.group(2).strip()
                if level == 1 and not doc_title:
                    doc_title = heading_text

                current_heading = heading_text
                current_level = level
            else:
                current_content_lines.append(line)

        # Flush final section
        if current_content_lines:
            sections.append(
                ExtractedSection(
                    heading=current_heading,
                    level=current_level,
                    content="\n".join(current_content_lines),
                )
            )

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        page = ExtractedPage(
            page_number=1,
            text=decoded_text,
            metadata={"sections_count": len(sections)},
        )

        return ExtractedDocument(
            source_filename=filename,
            mime_type=mime_type or "text/markdown",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            title=doc_title or filename,
            text=decoded_text,
            pages=[page],
            sections=sections,
            metadata={"sections_count": len(sections)},
            warnings=warnings,
            extraction_stats={
                "duration_ms": duration_ms,
                "sections_count": len(sections),
                "char_count": len(decoded_text),
            },
        )
