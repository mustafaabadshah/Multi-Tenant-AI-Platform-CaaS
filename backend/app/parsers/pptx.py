"""PPTX Presentation Parser using python-pptx."""

import io
import time
from pptx import Presentation

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
    ExtractedTable,
)


class PPTXParser(DocumentParser):
    """Secure PPTX parser extracting slide titles, body shapes, notes, and tables."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".pptx"}

    @property
    def supported_mime_types(self) -> set[str]:
        return {
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
        }

    @property
    def parser_name(self) -> str:
        return "python-pptx_Parser"

    def validate(self, content: bytes, filename: str) -> bool:
        """Validate ZIP container signature."""
        return content.startswith(b"PK\x03\x04")

    async def extract(self, content: bytes, filename: str, mime_type: str | None = None) -> ExtractedDocument:
        start_time = time.perf_counter()
        warnings: list[str] = []
        pages: list[ExtractedPage] = []
        sections: list[ExtractedSection] = []
        all_tables: list[ExtractedTable] = []
        text_parts: list[str] = []

        try:
            prs = Presentation(io.BytesIO(content))
        except Exception as e:
            raise ValueError(f"Failed to open PPTX presentation: {e}") from e

        for slide_idx, slide in enumerate(prs.slides):
            slide_num = slide_idx + 1
            slide_title = ""
            slide_lines: list[str] = []
            slide_tables: list[ExtractedTable] = []

            # 1. Slide shapes & text
            for shape in slide.shapes:
                if shape.has_text_frame:
                    shape_text = shape.text.strip()
                    if shape_text:
                        # Check if this shape is slide title
                        if shape == slide.shapes.title:
                            slide_title = shape_text
                        else:
                            slide_lines.append(shape_text)

                # 2. Slide tables
                elif shape.has_table:
                    tbl = shape.table
                    rows: list[list[str]] = []
                    for row in tbl.rows:
                        rows.append([cell.text.strip().replace("\n", " ") for cell in row.cells])
                    if rows:
                        headers = rows[0]
                        data_rows = rows[1:] if len(rows) > 1 else []
                        extracted_tbl = ExtractedTable(
                            title=f"Slide {slide_num} Table",
                            headers=headers,
                            rows=data_rows,
                            page_or_sheet=slide_num,
                        )
                        slide_tables.append(extracted_tbl)
                        all_tables.append(extracted_tbl)
                        slide_lines.append(extracted_tbl.to_markdown())

            # 3. Slide notes
            notes_text = ""
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
                if notes_text:
                    slide_lines.append(f"Notes: {notes_text}")

            effective_title = slide_title or f"Slide {slide_num}"
            formatted_slide_text = f"## {effective_title}\n\n" + "\n\n".join(slide_lines)
            text_parts.append(formatted_slide_text)

            sections.append(
                ExtractedSection(
                    heading=effective_title,
                    level=2,
                    content=formatted_slide_text,
                    page_number=slide_num,
                )
            )

            pages.append(
                ExtractedPage(
                    page_number=slide_num,
                    text=formatted_slide_text,
                    tables=slide_tables,
                    metadata={"slide_title": slide_title, "has_notes": bool(notes_text)},
                )
            )

        full_text = "\n\n".join(text_parts)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return ExtractedDocument(
            source_filename=filename,
            mime_type=mime_type or "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            title=filename,
            text=full_text,
            pages=pages,
            sections=sections,
            tables=all_tables,
            metadata={"slides_count": len(pages), "tables_count": len(all_tables)},
            warnings=warnings,
            extraction_stats={
                "duration_ms": duration_ms,
                "slides_count": len(pages),
                "tables_count": len(all_tables),
                "char_count": len(full_text),
            },
        )
