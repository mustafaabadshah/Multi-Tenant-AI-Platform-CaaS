"""Document parsers package for MM AI Platform."""

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
    ExtractedTable,
)
from app.parsers.csv_parser import CSVParser
from app.parsers.docx import DOCXParser
from app.parsers.json_parser import JSONParser
from app.parsers.markdown import MarkdownParser
from app.parsers.pdf import PDFParser
from app.parsers.pptx import PPTXParser
from app.parsers.registry import ParserRegistry, get_parser_registry
from app.parsers.sql_parser import SQLParser
from app.parsers.txt import TextParser
from app.parsers.xlsx import XLSXParser

__all__ = [
    "CSVParser",
    "DOCXParser",
    "DocumentParser",
    "ExtractedDocument",
    "ExtractedPage",
    "ExtractedSection",
    "ExtractedTable",
    "JSONParser",
    "MarkdownParser",
    "PDFParser",
    "PPTXParser",
    "ParserRegistry",
    "SQLParser",
    "TextParser",
    "XLSXParser",
    "get_parser_registry",
]
