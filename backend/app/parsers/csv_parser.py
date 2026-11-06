"""CSV Document Parser using Python standard library."""

import csv
import io
import time

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
    ExtractedTable,
)


class CSVParser(DocumentParser):
    """Secure CSV parser with automatic delimiter and encoding detection."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".csv", ".tsv"}

    @property
    def supported_mime_types(self) -> set[str]:
        return {"text/csv", "text/tab-separated-values", "application/csv"}

    @property
    def parser_name(self) -> str:
        return "python-csv_Parser"

    def validate(self, content: bytes, filename: str) -> bool:
        """Validate if file is text/readable."""
        return len(content) > 0 and not content.startswith(b"\x00")

    async def extract(self, content: bytes, filename: str, mime_type: str | None = None) -> ExtractedDocument:
        start_time = time.perf_counter()
        warnings: list[str] = []

        # 1. Decode text
        decoded_text = ""
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                decoded_text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if not decoded_text:
            decoded_text = content.decode("utf-8", errors="replace")
            warnings.append("CSV contained unrecognized characters that were replaced.")

        # 2. Sniff delimiter
        sample = decoded_text[:4096]
        delimiter = ","
        if filename.endswith(".tsv"):
            delimiter = "\t"
        else:
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ","

        # 3. Read rows
        reader = csv.reader(io.StringIO(decoded_text), delimiter=delimiter)
        rows: list[list[str]] = []
        max_rows = 10000

        for idx, row in enumerate(reader):
            if idx >= max_rows:
                warnings.append(f"CSV exceeded {max_rows} rows limit; truncated.")
                break
            if any(cell.strip() for cell in row):
                rows.append([cell.strip() for cell in row])

        if not rows:
            return ExtractedDocument(
                source_filename=filename,
                mime_type=mime_type or "text/csv",
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                title=filename,
                text="",
                pages=[],
                sections=[],
                tables=[],
                metadata={"delimiter": delimiter, "rows_count": 0},
                warnings=warnings,
                extraction_stats={"duration_ms": 0, "rows_count": 0, "char_count": 0},
            )

        headers = rows[0]
        data_rows = rows[1:] if len(rows) > 1 else []

        table = ExtractedTable(
            title=filename,
            headers=headers,
            rows=data_rows,
            page_or_sheet="Data",
            metadata={"delimiter": delimiter, "total_rows": len(rows)},
        )

        table_md = table.to_markdown()
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        section = ExtractedSection(
            heading=f"Data: {filename}",
            level=1,
            content=table_md,
            page_number=1,
        )

        page = ExtractedPage(
            page_number=1,
            text=table_md,
            tables=[table],
            metadata={"delimiter": delimiter, "row_count": len(rows)},
        )

        return ExtractedDocument(
            source_filename=filename,
            mime_type=mime_type or "text/csv",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            title=filename,
            text=table_md,
            pages=[page],
            sections=[section],
            tables=[table],
            metadata={
                "delimiter": delimiter,
                "rows_count": len(rows),
                "columns_count": len(headers),
                "headers": headers,
            },
            warnings=warnings,
            extraction_stats={
                "duration_ms": duration_ms,
                "rows_count": len(rows),
                "char_count": len(table_md),
            },
        )
