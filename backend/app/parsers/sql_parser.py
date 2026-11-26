"""SQL Schema and Script Parser using sqlglot (Safe Document Extraction ONLY).

CRITICAL SECURITY NOTICE:
Never execute uploaded SQL files or evaluate them against any live database connection.
This parser performs pure AST parsing and static analysis only.
"""

import time

import sqlglot
from sqlglot import exp

from app.parsers.base import (
    DocumentParser,
    ExtractedDocument,
    ExtractedPage,
    ExtractedSection,
    ExtractedTable,
)


class SQLParser(DocumentParser):
    """Secure SQL parser extracting schema definitions, tables, columns, indexes, and views."""

    @property
    def supported_extensions(self) -> set[str]:
        return {".sql", ".ddl"}

    @property
    def supported_mime_types(self) -> set[str]:
        return {"application/sql", "text/x-sql", "text/sql"}

    @property
    def parser_name(self) -> str:
        return "sqlglot_Parser"

    def validate(self, content: bytes, filename: str) -> bool:
        """Validate if file is readable text and resembles SQL."""
        return len(content) > 0 and not content.startswith(b"\x00")

    async def extract(self, content: bytes, filename: str, mime_type: str | None = None) -> ExtractedDocument:
        start_time = time.perf_counter()
        warnings: list[str] = []
        sections: list[ExtractedSection] = []
        tables: list[ExtractedTable] = []
        text_parts: list[str] = []

        decoded_text = ""
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                decoded_text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not decoded_text:
            decoded_text = content.decode("utf-8", errors="replace")

        # Parse SQL statements safely via sqlglot AST
        statements: list[exp.Expression] = []
        try:
            parsed = sqlglot.parse(decoded_text)
            statements = [stmt for stmt in parsed if stmt is not None]
        except Exception as e:
            warnings.append(f"SQL parsing warning: {e}. Falling back to line-based structure.")

        extracted_tables_summary = []
        extracted_views = []
        extracted_indexes = []

        for stmt in statements:
            if isinstance(stmt, exp.Create):
                # Check what kind of CREATE statement
                kind = stmt.args.get("kind", "").upper() if stmt.args.get("kind") else ""
                target_table = stmt.this

                if "TABLE" in kind or isinstance(target_table, exp.Schema):
                    table_exp = target_table.find(exp.Table) if hasattr(target_table, "find") else None
                    if table_exp and hasattr(table_exp, "name") and table_exp.name:
                        table_name = table_exp.name
                    elif hasattr(target_table, "name") and target_table.name:
                        table_name = target_table.name
                    elif hasattr(target_table, "this") and hasattr(target_table.this, "name"):
                        table_name = target_table.this.name
                    else:
                        table_name = str(target_table)
                    columns_data: list[list[str]] = []
                    primary_keys = []

                    # If schema expression, extract column definitions
                    if isinstance(target_table, exp.Schema):
                        for col_def in target_table.expressions:
                            if isinstance(col_def, exp.ColumnDef):
                                col_name = col_def.name
                                col_type = str(col_def.kind) if col_def.kind else "UNKNOWN"
                                is_pk = False
                                for constraint in col_def.find_all(exp.PrimaryKeyColumnConstraint):
                                    is_pk = True
                                    primary_keys.append(col_name)
                                columns_data.append([col_name, col_type, "PRIMARY KEY" if is_pk else ""])

                    tbl = ExtractedTable(
                        title=f"SQL Table: {table_name}",
                        headers=["Column Name", "Data Type", "Constraints"],
                        rows=columns_data,
                        page_or_sheet=table_name,
                    )
                    tables.append(tbl)
                    extracted_tables_summary.append(f"Table `{table_name}` ({len(columns_data)} columns)")

                    table_text = (
                        f"### Table: {table_name}\n\n"
                        f"- **Type**: Relational Table\n"
                        f"- **Primary Keys**: {', '.join(primary_keys) if primary_keys else 'None specified'}\n\n"
                        f"{tbl.to_markdown()}"
                    )
                    text_parts.append(table_text)
                    sections.append(
                        ExtractedSection(
                            heading=f"Table: {table_name}",
                            level=2,
                            content=table_text,
                        )
                    )

                elif "VIEW" in kind:
                    view_name = target_table.name if hasattr(target_table, "name") else str(target_table)
                    extracted_views.append(view_name)
                    view_text = f"### View: {view_name}\n\n```sql\n{stmt.sql()}\n```"
                    text_parts.append(view_text)
                    sections.append(
                        ExtractedSection(
                            heading=f"View: {view_name}",
                            level=2,
                            content=view_text,
                        )
                    )

                elif "INDEX" in kind:
                    idx_name = target_table.name if hasattr(target_table, "name") else str(target_table)
                    extracted_indexes.append(idx_name)

        # If no tables were parsed via CREATE TABLE (e.g. plain DML or unstructured script), preserve raw statements
        if not text_parts:
            text_parts.append(f"### SQL Script: {filename}\n\n```sql\n{decoded_text[:100000]}\n```")
            sections.append(
                ExtractedSection(
                    heading=f"SQL Script: {filename}",
                    level=1,
                    content=text_parts[0],
                )
            )

        full_text = "\n\n".join(text_parts)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        page = ExtractedPage(
            page_number=1,
            text=full_text,
            tables=tables,
            metadata={
                "tables_count": len(tables),
                "views_count": len(extracted_views),
                "indexes_count": len(extracted_indexes),
                "statements_count": len(statements),
            },
        )

        return ExtractedDocument(
            source_filename=filename,
            mime_type=mime_type or "application/sql",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            title=f"SQL Schema: {filename}",
            text=full_text,
            pages=[page],
            sections=sections,
            tables=tables,
            metadata={
                "tables": extracted_tables_summary,
                "views": extracted_views,
                "indexes": extracted_indexes,
                "total_statements": len(statements),
                "is_executable": False,  # Explicit safety flag
            },
            warnings=warnings,
            extraction_stats={
                "duration_ms": duration_ms,
                "statements_count": len(statements),
                "tables_count": len(tables),
                "char_count": len(full_text),
            },
        )
