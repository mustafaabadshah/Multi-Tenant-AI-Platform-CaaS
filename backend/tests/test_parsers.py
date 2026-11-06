"""Comprehensive unit tests for all 9 document parsers and registry."""

import io
import pytest
import docx
import openpyxl
from pptx import Presentation
import pymupdf

from app.parsers.csv_parser import CSVParser
from app.parsers.docx import DOCXParser
from app.parsers.json_parser import JSONParser
from app.parsers.markdown import MarkdownParser
from app.parsers.pdf import PDFParser
from app.parsers.pptx import PPTXParser
from app.parsers.registry import get_parser_registry
from app.parsers.sql_parser import SQLParser
from app.parsers.txt import TextParser
from app.parsers.xlsx import XLSXParser


@pytest.mark.asyncio
async def test_pdf_parser_text_and_pages():
    """Test PDF parser with PyMuPDF text and page extraction."""
    # Generate in-memory PDF
    doc = pymupdf.open()
    page1 = doc.new_page()
    page1.insert_text((50, 50), "Hello Multi-Tenant AI Platform-CaaS PDF Page 1")
    page2 = doc.new_page()
    page2.insert_text((50, 50), "Second page content for testing")
    pdf_bytes = doc.tobytes()
    doc.close()

    parser = PDFParser()
    assert parser.validate(pdf_bytes, "test.pdf") is True

    extracted = await parser.extract(pdf_bytes, "test.pdf")
    assert extracted.title == "test.pdf"
    assert "Hello Multi-Tenant AI Platform-CaaS" in extracted.text
    assert len(extracted.pages) == 2
    assert extracted.pages[0].page_number == 1
    assert "Page 1" in extracted.pages[0].text
    assert extracted.pages[1].page_number == 2
    assert extracted.extraction_stats["pages_count"] == 2


@pytest.mark.asyncio
async def test_docx_parser_headings_and_tables():
    """Test DOCX parser extracting paragraphs, headings, and tables."""
    doc = docx.Document()
    doc.add_heading("Architecture Overview", level=1)
    doc.add_paragraph("This is the main introduction paragraph.")
    doc.add_heading("Sub-section Details", level=2)
    doc.add_paragraph("Details about the system.")

    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Header 1"
    table.cell(0, 1).text = "Header 2"
    table.cell(1, 0).text = "Value A"
    table.cell(1, 1).text = "Value B"

    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    parser = DOCXParser()
    assert parser.validate(docx_bytes, "doc.docx") is True

    extracted = await parser.extract(docx_bytes, "doc.docx")
    assert "Architecture Overview" in extracted.text
    assert "Header 1" in extracted.text
    assert "Value A" in extracted.text
    assert len(extracted.sections) >= 2
    assert len(extracted.tables) == 1
    assert extracted.tables[0].headers == ["Header 1", "Header 2"]


@pytest.mark.asyncio
async def test_xlsx_parser_sheets_and_rows():
    """Test XLSX parser extracting sheet names and table data."""
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Financials"
    ws1.append(["Quarter", "Revenue", "Profit"])
    ws1.append(["Q1", 100000, 25000])
    ws1.append(["Q2", 150000, 35000])

    ws2 = wb.create_sheet(title="Headcount")
    ws2.append(["Department", "Count"])
    ws2.append(["Engineering", 12])

    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    parser = XLSXParser()
    extracted = await parser.extract(xlsx_bytes, "budget.xlsx")
    assert "Financials" in extracted.text
    assert "Headcount" in extracted.text
    assert "Revenue" in extracted.text
    assert len(extracted.tables) == 2
    assert extracted.extraction_stats["sheets_count"] == 2


@pytest.mark.asyncio
async def test_pptx_parser_slides_and_titles():
    """Test PPTX parser extracting slide titles and body shapes."""
    prs = Presentation()
    slide_layout = prs.slide_layouts[0]  # Title slide
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Quarterly Strategy"
    slide.placeholders[1].text = "Key priorities: Multi-tenant security and RAG."

    buf = io.BytesIO()
    prs.save(buf)
    pptx_bytes = buf.getvalue()

    parser = PPTXParser()
    extracted = await parser.extract(pptx_bytes, "presentation.pptx")
    assert "Quarterly Strategy" in extracted.text
    assert "Key priorities" in extracted.text
    assert len(extracted.pages) == 1
    assert extracted.pages[0].page_number == 1


@pytest.mark.asyncio
async def test_csv_parser_delimiter_sniffing():
    """Test CSV parser with semicolon delimiter detection and headers."""
    csv_data = "Name;Department;Role\nAlice;Engineering;Lead\nBob;Product;Manager\n"
    csv_bytes = csv_data.encode("utf-8")

    parser = CSVParser()
    extracted = await parser.extract(csv_bytes, "employees.csv")
    assert "Alice" in extracted.text
    assert "Engineering" in extracted.text
    assert len(extracted.tables) == 1
    assert extracted.tables[0].headers == ["Name", "Department", "Role"]
    assert extracted.metadata["delimiter"] == ";"


@pytest.mark.asyncio
async def test_json_parser_paths_and_jsonl():
    """Test JSON parser flattening structured paths."""
    json_data = b'{"tenant": {"id": "123", "name": "Company A"}, "active": true}'
    parser = JSONParser()
    extracted = await parser.extract(json_data, "config.json")
    assert "tenant.id" in extracted.text
    assert "Company A" in extracted.text
    assert extracted.metadata["total_paths"] >= 2


@pytest.mark.asyncio
async def test_sql_parser_schema_safety():
    """Test SQL parser extracts tables and columns without executing SQL."""
    sql_script = """
    -- Users Table Definition
    CREATE TABLE app_users (
        id UUID PRIMARY KEY,
        username VARCHAR(100) NOT NULL,
        email VARCHAR(255) UNIQUE,
        created_at TIMESTAMP
    );

    CREATE VIEW active_users AS
    SELECT * FROM app_users;
    """
    parser = SQLParser()
    extracted = await parser.extract(sql_script.encode("utf-8"), "schema.sql")
    assert "app_users" in extracted.text
    assert "username" in extracted.text
    assert len(extracted.tables) == 1
    assert extracted.tables[0].title == "SQL Table: app_users"
    assert extracted.metadata["is_executable"] is False


@pytest.mark.asyncio
async def test_text_and_markdown_parsers():
    """Test plain text and Markdown heading hierarchy."""
    md_content = """# Main Header
Introductory text.

## Subsection 1
First subsection details.

### Deep Section
Deep details.
"""
    parser = MarkdownParser()
    extracted = await parser.extract(md_content.encode("utf-8"), "notes.md")
    assert extracted.title == "Main Header"
    assert len(extracted.sections) == 3
    assert extracted.sections[0].heading == "Main Header"
    assert extracted.sections[1].heading == "Subsection 1"

    txt_parser = TextParser()
    txt_extracted = await txt_parser.extract(b"Plain text note\n\nSecond paragraph", "note.txt")
    assert "Plain text note" in txt_extracted.text
    assert len(txt_extracted.sections) == 2


def test_parser_registry_unsupported():
    """Test ParserRegistry rejects unsupported file types."""
    registry = get_parser_registry()
    with pytest.raises(ValueError, match="Unsupported document format"):
        registry.resolve_parser("archive.tar.gz", b"\x1f\x8b\x08", "application/gzip")
