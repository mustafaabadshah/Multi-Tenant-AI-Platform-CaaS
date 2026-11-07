"""XLSX Spreadsheet Parser using openpyxl."""

import io
import time

import openpyxl

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
    ExtractedTable,
)


class XLSXParser(DocumentParser):
    """Secure XLSX parser extracting sheets, rows, and structured tables."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".xlsx", ".xlsm"}

    @property
    def supported_mime_types(self) -> set[str]:
        return {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        }

    @property
    def parser_name(self) -> str:
        return "openpyxl_Parser"

    def validate(self, content: bytes, filename: str) -> bool:
        """Validate ZIP container signature."""
        return content.startswith(b"PK\x03\x04")

    async def extract(self, content: bytes, filename: str, mime_type: str | None = None) -> ExtractedDocument:
        start_time = time.perf_counter()
        warnings: list[str] = []
        pages: list[ExtractedPage] = []
        sections: list[ExtractedSection] = []
        tables: list[ExtractedTable] = []
        text_parts: list[str] = []

        try:
            wb = openpyxl.load_workbook(
                filename=io.BytesIO(content),
                read_only=True,
                data_only=True,
            )
        except Exception as e:
            raise ValueError(f"Failed to open XLSX document: {e}") from e

        try:
            for sheet_idx, sheet_name in enumerate(wb.sheetnames):
                sheet = wb[sheet_name]
                sheet_rows: list[list[str]] = []

                # Limit maximum rows per sheet to prevent unbounded memory consumption
                max_rows = 5000
                for row_idx, row in enumerate(sheet.iter_rows(values_only=True)):
                    if row_idx >= max_rows:
                        warnings.append(f"Sheet '{sheet_name}' exceeded {max_rows} rows limit; truncated.")
                        break
                    # Filter completely empty rows
                    if any(cell is not None and str(cell).strip() != "" for cell in row):
                        row_values = [str(c).strip() if c is not None else "" for c in row]
                        sheet_rows.append(row_values)

                if not sheet_rows:
                    continue

                headers = sheet_rows[0]
                data_rows = sheet_rows[1:] if len(sheet_rows) > 1 else []

                table = ExtractedTable(
                    title=f"Sheet: {sheet_name}",
                    headers=headers,
                    rows=data_rows,
                    page_or_sheet=sheet_name,
                )
                tables.append(table)

                table_md = table.to_markdown()
                sheet_text = f"### Sheet: {sheet_name}\n\n{table_md}"
                text_parts.append(sheet_text)

                sections.append(
                    ExtractedSection(
                        heading=f"Sheet: {sheet_name}",
                        level=2,
                        content=sheet_text,
                        page_number=sheet_idx + 1,
                    )
                )

                pages.append(
                    ExtractedPage(
                        page_number=sheet_idx + 1,
                        text=sheet_text,
                        tables=[table],
                        metadata={"sheet_name": sheet_name, "row_count": len(sheet_rows)},
                    )
                )

            full_text = "\n\n".join(text_parts)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return ExtractedDocument(
                source_filename=filename,
                mime_type=mime_type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                title=filename,
                text=full_text,
                pages=pages,
                sections=sections,
                tables=tables,
                metadata={"sheets": wb.sheetnames, "sheets_count": len(wb.sheetnames)},
                warnings=warnings,
                extraction_stats={
                    "duration_ms": duration_ms,
                    "sheets_count": len(pages),
                    "tables_count": len(tables),
                    "char_count": len(full_text),
                },
            )
        finally:
            wb.close()
