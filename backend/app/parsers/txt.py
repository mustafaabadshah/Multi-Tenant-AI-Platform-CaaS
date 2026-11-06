"""Plain Text Document Parser."""

import time

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
)


class TextParser(DocumentParser):
    """Secure plain text parser with encoding detection and paragraph grouping."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".txt", ".log", ".text"}

    @property
    def supported_mime_types(self) -> set[str]:
        return {"text/plain"}

    @property
    def parser_name(self) -> str:
        return "python-text_Parser"

    def validate(self, content: bytes, filename: str) -> bool:
        """Validate if content is non-null text."""
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
            warnings.append("Text contained unknown characters that were replaced.")

        # Identify natural sections based on double newlines / blank lines
        raw_paragraphs = [p.strip() for p in decoded_text.split("\n\n") if p.strip()]
        sections: list[ExtractedSection] = []

        for idx, para in enumerate(raw_paragraphs):
            # Take first line as heading if short, else generic section
            first_line = para.split("\n")[0].strip()
            heading = first_line[:60] if len(first_line) <= 60 else f"Section {idx + 1}"
            sections.append(
                ExtractedSection(
                    heading=heading,
                    level=1,
                    content=para,
                    page_number=1,
                )
            )

        duration_ms = int((time.perf_counter() - start_time) * 1000)

        page = ExtractedPage(
            page_number=1,
            text=decoded_text,
            metadata={"paragraph_count": len(raw_paragraphs)},
        )

        return ExtractedDocument(
            source_filename=filename,
            mime_type=mime_type or "text/plain",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            title=filename,
            text=decoded_text,
            pages=[page],
            sections=sections,
            metadata={"paragraphs_count": len(raw_paragraphs)},
            warnings=warnings,
            extraction_stats={
                "duration_ms": duration_ms,
                "paragraphs_count": len(raw_paragraphs),
                "char_count": len(decoded_text),
            },
        )
