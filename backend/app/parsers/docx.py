"""DOCX Document Parser using python-docx."""

import io
import time

import docx

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
    ExtractedTable,
)


class DOCXParser(DocumentParser):
    """Secure DOCX parser extracting paragraphs, headings, and tables."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".docx"}

    @property
    def supported_mime_types(self) -> set[str]:
        return {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }

    @property
    def parser_name(self) -> str:
        return "python-docx_Parser"

    def validate(self, content: bytes, filename: str) -> bool:
        """Validate ZIP container signature (PK\x03\x04)."""
        return content.startswith(b"PK\x03\x04")

    async def extract(self, content: bytes, filename: str, mime_type: str | None = None) -> ExtractedDocument:
        start_time = time.perf_counter()
        warnings: list[str] = []
        sections: list[ExtractedSection] = []
        tables: list[ExtractedTable] = []
        text_lines: list[str] = []

        try:
            doc = docx.Document(io.BytesIO(content))
        except Exception as e:
            raise ValueError(f"Failed to open DOCX document: {e}") from e

        core_props = doc.core_properties
        title = core_props.title or filename

        current_heading = "Introduction"
        current_level = 1
        current_section_lines: list[str] = []

        # 1. Extract paragraphs and headings
        for para in doc.paragraphs:
            raw_text = para.text.strip()
            if not raw_text:
                continue

            style_name = para.style.name if para.style else ""
            if "Heading" in style_name:
                # Flush previous section
                if current_section_lines:
                    sections.append(
                        ExtractedSection(
                            heading=current_heading,
                            level=current_level,
                            content="\n".join(current_section_lines),
                        )
                    )
                    current_section_lines = []

                # Determine heading level
                level = 1
                for char in style_name:
                    if char.isdigit():
                        level = int(char)
                        break
                current_heading = raw_text
                current_level = level
                text_lines.append(f"\n{'#' * level} {raw_text}\n")
            else:
                current_section_lines.append(raw_text)
                text_lines.append(raw_text)

        # Flush final section
        if current_section_lines:
            sections.append(
                ExtractedSection(
                    heading=current_heading,
                    level=current_level,
                    content="\n".join(current_section_lines),
                )
            )

        # 2. Extract tables
        for idx, table in enumerate(doc.tables):
            table_rows: list[list[str]] = []
            for row in table.rows:
                row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                table_rows.append(row_cells)

            if table_rows:
                headers = table_rows[0]
                data_rows = table_rows[1:] if len(table_rows) > 1 else []
                extracted_table = ExtractedTable(
                    title=f"Table {idx + 1}",
                    headers=headers,
                    rows=data_rows,
                )
                tables.append(extracted_table)
                table_md = extracted_table.to_markdown()
                if table_md:
                    text_lines.append(f"\n{table_md}\n")

        full_text = "\n\n".join(text_lines)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Single logical page representing the document flow
        pages = [ExtractedPage(page_number=1, text=full_text, tables=tables)]

        return ExtractedDocument(
            source_filename=filename,
            mime_type=mime_type or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            title=title,
            text=full_text,
            pages=pages,
            sections=sections,
            tables=tables,
            metadata={
                "author": core_props.author,
                "created": str(core_props.created) if core_props.created else None,
                "modified": str(core_props.modified) if core_props.modified else None,
                "paragraphs_count": len(doc.paragraphs),
                "tables_count": len(tables),
            },
            warnings=warnings,
            extraction_stats={
                "duration_ms": duration_ms,
                "char_count": len(full_text),
                "sections_count": len(sections),
                "tables_count": len(tables),
            },
        )
