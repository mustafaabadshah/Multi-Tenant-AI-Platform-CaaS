"""Base models and abstract interface for MM AI Platform document parsers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedTable:
    """Structured representation of an extracted tabular data source."""
    title: str | None = None
    headers: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    page_or_sheet: str | int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Render table as standard markdown."""
        if not self.headers and not self.rows:
            return ""
        lines = []
        if self.title:
            lines.append(f"**Table: {self.title}**\n")
        
        headers = [str(h) for h in self.headers] if self.headers else [f"Col {i+1}" for i in range(len(self.rows[0]) if self.rows else 0)]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in self.rows:
            row_str = [str(cell) if cell is not None else "" for cell in row]
            # Pad row if columns mismatch
            if len(row_str) < len(headers):
                row_str.extend([""] * (len(headers) - len(row_str)))
            lines.append("| " + " | ".join(row_str[:len(headers)]) + " |")
        return "\n".join(lines)


@dataclass
class ExtractedSection:
    """Represents a logical section, heading, or slide."""
    heading: str
    level: int = 1
    content: str = ""
    page_number: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedPage:
    """Represents a page, slide, or sheet."""
    page_number: int
    text: str
    is_scanned: bool = False
    images_count: int = 0
    tables: list[ExtractedTable] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedDocument:
    """Normalized document extraction representation."""
    source_filename: str
    mime_type: str
    parser_name: str
    parser_version: str = "1.0.0"
    title: str | None = None
    text: str = ""
    pages: list[ExtractedPage] = field(default_factory=list)
    sections: list[ExtractedSection] = field(default_factory=list)
    tables: list[ExtractedTable] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    extraction_stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary for database persistence."""
        return {
            "title": self.title,
            "source_filename": self.source_filename,
            "mime_type": self.mime_type,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "metadata": self.metadata,
            "warnings": self.warnings,
            "extraction_stats": self.extraction_stats,
            "pages_count": len(self.pages),
            "sections_count": len(self.sections),
            "tables_count": len(self.tables),
            "sections": [
                {
                    "heading": s.heading,
                    "level": s.level,
                    "content_snippet": s.content[:200] if s.content else "",
                    "page_number": s.page_number,
                }
                for s in self.sections[:100]  # Store top 100 sections in json summary
            ],
            "tables": [
                {
                    "title": t.title,
                    "headers": t.headers,
                    "row_count": len(t.rows),
                    "page_or_sheet": t.page_or_sheet,
                }
                for t in self.tables[:50]
            ],
        }


class DocumentParser(ABC):
    """Abstract contract for document format parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Set of supported lower-cased file extensions with leading dot (e.g. {'.pdf'})."""
        pass

    @property
    @abstractmethod
    def supported_mime_types(self) -> set[str]:
        """Set of supported MIME types (e.g. {'application/pdf'})."""
        pass

    @property
    @abstractmethod
    def parser_name(self) -> str:
        """Name of the parser."""
        pass

    @property
    def parser_version(self) -> str:
        return "1.0.0"

    @abstractmethod
    def validate(self, content: bytes, filename: str) -> bool:
        """Validate if the file content matches expected format signatures."""
        pass

    @abstractmethod
    async def extract(self, content: bytes, filename: str, mime_type: str | None = None) -> ExtractedDocument:
        """Extract structured content and text from raw file bytes."""
        pass
