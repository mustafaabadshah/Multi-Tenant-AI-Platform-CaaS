"""Parser Registry for MM AI Platform."""

import os
from pathlib import Path
import filetype

from app.parsers.base import DocumentParser
from app.parsers.csv_parser import CSVParser
from app.parsers.docx import DOCXParser
from app.parsers.json_parser import JSONParser
from app.parsers.markdown import MarkdownParser
from app.parsers.pdf import PDFParser
from app.parsers.pptx import PPTXParser
from app.parsers.sql_parser import SQLParser
from app.parsers.txt import TextParser
from app.parsers.xlsx import XLSXParser


class ParserRegistry:
    """Registry managing format-specific document parsers with magic signature detection."""

    def __init__(self) -> None:
        self._parsers: list[DocumentParser] = [
            PDFParser(),
            DOCXParser(),
            XLSXParser(),
            PPTXParser(),
            CSVParser(),
            JSONParser(),
            SQLParser(),
            MarkdownParser(),
            TextParser(),
        ]

    def get_supported_extensions(self) -> set[str]:
        """Return all supported file extensions."""
        exts: set[str] = set()
        for p in self._parsers:
            exts.update(p.supported_extensions)
        return exts

    def detect_mime_type(self, content: bytes, filename: str) -> str:
        """Inspect file content signatures using filetype before relying on extension."""
        kind = filetype.guess(content)
        if kind is not None:
            return kind.mime

        ext = Path(filename).suffix.lower()
        ext_to_mime = {
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".csv": "text/csv",
            ".tsv": "text/tab-separated-values",
            ".json": "application/json",
            ".jsonl": "application/x-ndjson",
            ".sql": "application/sql",
            ".ddl": "application/sql",
            ".txt": "text/plain",
            ".text": "text/plain",
            ".md": "text/markdown",
            ".markdown": "text/markdown",
        }
        return ext_to_mime.get(ext, "application/octet-stream")

    def resolve_parser(
        self,
        filename: str,
        content: bytes,
        declared_mime: str | None = None,
    ) -> DocumentParser:
        """Resolve parser based on content signature and validated file extension.

        Never trusts client-supplied MIME or extension blindly.
        """
        ext = Path(filename).suffix.lower()
        detected_mime = self.detect_mime_type(content, filename)

        # 1. Check for specific binary magic signatures first
        for parser in self._parsers:
            if ext in parser.supported_extensions and parser.validate(content, filename):
                return parser

        # 2. Check for text-based parsers matching extension
        for parser in self._parsers:
            if ext in parser.supported_extensions:
                return parser

        # 3. Check for parsers matching detected MIME type
        for parser in self._parsers:
            if detected_mime in parser.supported_mime_types:
                return parser

        raise ValueError(
            f"Unsupported document format: extension '{ext}', detected MIME '{detected_mime}'. "
            f"Supported extensions: {', '.join(sorted(self.get_supported_extensions()))}"
        )


_default_registry = ParserRegistry()


def get_parser_registry() -> ParserRegistry:
    return _default_registry
