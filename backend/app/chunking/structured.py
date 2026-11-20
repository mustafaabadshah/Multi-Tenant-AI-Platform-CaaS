"""Structured Document Chunking Strategy."""

from typing import Any

from app.chunking.base import (
    ChunkingConfig,
    ChunkingStrategy,
    ChunkMetadata,
    ProcessedChunk,
    calculate_chunk_hash,
    estimate_tokens,
)
from app.chunking.recursive import RecursiveCharacterChunking
from app.parsers.base import ExtractedDocument, ExtractedTable


def _chunk_table(table: ExtractedTable, max_chars: int) -> list[str]:
    """Chunk a table while preserving table title and headers on every generated chunk."""
    if not table.rows:
        return [table.to_markdown()] if table.headers else []

    headers_str = "| " + " | ".join(str(h) for h in table.headers) + " |"
    divider_str = "| " + " | ".join(["---"] * len(table.headers)) + " |"
    title_prefix = f"**Table: {table.title}**\n\n" if table.title else ""
    header_block = f"{title_prefix}{headers_str}\n{divider_str}"

    chunks: list[str] = []
    current_rows: list[str] = []
    current_len = len(header_block)

    for row in table.rows:
        row_str = "| " + " | ".join(str(c) if c is not None else "" for c in row[:len(table.headers)]) + " |"
        if current_len + len(row_str) + 1 <= max_chars:
            current_rows.append(row_str)
            current_len += len(row_str) + 1
        else:
            if current_rows:
                chunk_md = header_block + "\n" + "\n".join(current_rows)
                chunks.append(chunk_md)
            current_rows = [row_str]
            current_len = len(header_block) + len(row_str) + 1

    if current_rows:
        chunk_md = header_block + "\n" + "\n".join(current_rows)
        chunks.append(chunk_md)

    return chunks


class StructuredDocumentChunking(ChunkingStrategy):
    """Chunking strategy designed for structured data: tables, sheets, slides, and schemas."""

    @property
    def name(self) -> str:
        return "structured"

    def chunk(
        self,
        extracted_doc: ExtractedDocument,
        context_meta: dict[str, Any],
        config: ChunkingConfig,
    ) -> list[ProcessedChunk]:
        processed_chunks: list[ProcessedChunk] = []
        chunk_idx = 0

        # Case 1: Spreadsheets / Tables (CSV, XLSX, DOCX with tables)
        if extracted_doc.tables and not extracted_doc.pages:
            for table in extracted_doc.tables:
                table_chunks = _chunk_table(table, config.chunk_size)
                for t_text in table_chunks:
                    clean_text = t_text.strip()
                    if not clean_text:
                        continue
                    meta = ChunkMetadata(
                        tenant_id=str(context_meta.get("tenant_id")),
                        knowledge_base_id=str(context_meta.get("knowledge_base_id")),
                        document_id=str(context_meta.get("document_id")),
                        document_version_id=str(context_meta.get("document_version_id")) if context_meta.get("document_version_id") else None,
                        chunk_index=chunk_idx,
                        page_number=1,
                        heading_path=str(table.page_or_sheet or table.title or "Table"),
                        source_filename=extracted_doc.source_filename,
                        source_type=extracted_doc.mime_type,
                        parser_name=extracted_doc.parser_name,
                        parser_version=extracted_doc.parser_version,
                        chunking_strategy=self.name,
                        chunk_hash=calculate_chunk_hash(clean_text),
                        character_count=len(clean_text),
                        token_count=estimate_tokens(clean_text),
                        extra={"is_table": True, "table_title": table.title},
                    )
                    processed_chunks.append(ProcessedChunk(content=clean_text, metadata=meta))
                    chunk_idx += 1
            if processed_chunks:
                return processed_chunks

        # Case 2: Presentation slides or multi-page documents with distinct sections/tables
        if extracted_doc.pages and len(extracted_doc.pages) > 0:
            for page in extracted_doc.pages:
                slide_title = page.metadata.get("slide_title") or f"Page {page.page_number}"
                
                # If page contains tables, chunk tables with header preservation
                if page.tables:
                    for table in page.tables:
                        table_chunks = _chunk_table(table, config.chunk_size)
                        for t_text in table_chunks:
                            clean_text = t_text.strip()
                            if not clean_text:
                                continue
                            meta = ChunkMetadata(
                                tenant_id=str(context_meta.get("tenant_id")),
                                knowledge_base_id=str(context_meta.get("knowledge_base_id")),
                                document_id=str(context_meta.get("document_id")),
                                document_version_id=str(context_meta.get("document_version_id")) if context_meta.get("document_version_id") else None,
                                chunk_index=chunk_idx,
                                page_number=page.page_number,
                                heading_path=slide_title,
                                source_filename=extracted_doc.source_filename,
                                source_type=extracted_doc.mime_type,
                                parser_name=extracted_doc.parser_name,
                                parser_version=extracted_doc.parser_version,
                                chunking_strategy=self.name,
                                chunk_hash=calculate_chunk_hash(clean_text),
                                character_count=len(clean_text),
                                token_count=estimate_tokens(clean_text),
                                extra={"page_number": page.page_number, "is_table": True},
                            )
                            processed_chunks.append(ProcessedChunk(content=clean_text, metadata=meta))
                            chunk_idx += 1
                else:
                    # Non-table page text (e.g. presentation slide text)
                    clean_text = page.text.strip()
                    if not clean_text:
                        continue
                    if len(clean_text) <= config.chunk_size:
                        meta = ChunkMetadata(
                            tenant_id=str(context_meta.get("tenant_id")),
                            knowledge_base_id=str(context_meta.get("knowledge_base_id")),
                            document_id=str(context_meta.get("document_id")),
                            document_version_id=str(context_meta.get("document_version_id")) if context_meta.get("document_version_id") else None,
                            chunk_index=chunk_idx,
                            page_number=page.page_number,
                            heading_path=slide_title,
                            source_filename=extracted_doc.source_filename,
                            source_type=extracted_doc.mime_type,
                            parser_name=extracted_doc.parser_name,
                            parser_version=extracted_doc.parser_version,
                            chunking_strategy=self.name,
                            chunk_hash=calculate_chunk_hash(clean_text),
                            character_count=len(clean_text),
                            token_count=estimate_tokens(clean_text),
                            extra={"page_number": page.page_number},
                        )
                        processed_chunks.append(ProcessedChunk(content=clean_text, metadata=meta))
                        chunk_idx += 1
                    else:
                        # Fallback split for extra long slide/page
                        sub_chunks = RecursiveCharacterChunking().chunk(
                            ExtractedDocument(
                                source_filename=extracted_doc.source_filename,
                                mime_type=extracted_doc.mime_type,
                                parser_name=extracted_doc.parser_name,
                                parser_version=extracted_doc.parser_version,
                                title=slide_title,
                                text=clean_text,
                            ),
                            context_meta={**context_meta, "page_number": page.page_number},
                            config=config,
                        )
                        for sc in sub_chunks:
                            sc.metadata.chunk_index = chunk_idx
                            sc.metadata.page_number = page.page_number
                            sc.metadata.heading_path = slide_title
                            sc.metadata.chunking_strategy = self.name
                            processed_chunks.append(sc)
                            chunk_idx += 1

            if processed_chunks:
                return processed_chunks

        # Case 3: SQL or other structured text: fall back to recursive with structured strategy label
        fallback = RecursiveCharacterChunking().chunk(extracted_doc, context_meta, config)
        for fb in fallback:
            fb.metadata.chunking_strategy = self.name
        return fallback
