"""Markdown Header-Aware Chunking Strategy."""

import re
from typing import Any

from app.chunking.base import (
    ChunkingConfig,
    ChunkingStrategy,
    ChunkMetadata,
    ProcessedChunk,
    calculate_chunk_hash,
    estimate_tokens,
)
from app.chunking.recursive import _split_text
from app.parsers.base import ExtractedDocument


class MarkdownHeaderChunking(ChunkingStrategy):
    """Header-aware chunking preserving Markdown hierarchy and contextual heading paths."""

    @property
    def name(self) -> str:
        return "markdown"

    def chunk(
        self,
        extracted_doc: ExtractedDocument,
        context_meta: dict[str, Any],
        config: ChunkingConfig,
    ) -> list[ProcessedChunk]:
        processed_chunks: list[ProcessedChunk] = []
        heading_regex = re.compile(r"^(#{1,6})\s+(.+)$")

        lines = extracted_doc.text.splitlines()
        sections_data: list[tuple[str, list[str]]] = []  # (heading_path, lines)

        heading_stack: list[tuple[int, str]] = []  # (level, title)
        current_lines: list[str] = []

        def get_current_path() -> str:
            if not heading_stack:
                return extracted_doc.title or "General"
            return " > ".join(title for _, title in heading_stack)

        for line in lines:
            match = heading_regex.match(line.strip())
            if match:
                # Flush previous section
                if current_lines:
                    sections_data.append((get_current_path(), current_lines))
                    current_lines = []

                level = len(match.group(1))
                title = match.group(2).strip()

                # Pop higher or equal levels from stack
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                current_lines.append(line)
            else:
                current_lines.append(line)

        if current_lines:
            sections_data.append((get_current_path(), current_lines))

        # Build chunks from sections
        chunk_idx = 0
        delimiters = ["\n\n", "\n", ". ", " "]

        for heading_path, sec_lines in sections_data:
            sec_text = "\n".join(sec_lines).strip()
            if not sec_text:
                continue

            # If section fits within chunk_size, keep whole
            if len(sec_text) <= config.chunk_size:
                chunks_to_add = [sec_text]
            else:
                # Split large section while repeating header context if desired
                chunks_to_add = _split_text(sec_text, delimiters, config.chunk_size, config.chunk_overlap)

            for raw_chunk in chunks_to_add:
                clean_chunk = raw_chunk.strip()
                if not clean_chunk:
                    continue

                # Add header path contextual prefix if chunk doesn't already start with heading
                final_content = clean_chunk
                if config.preserve_headers and not clean_chunk.startswith("#"):
                    final_content = f"[{heading_path}]\n{clean_chunk}"

                meta = ChunkMetadata(
                    tenant_id=str(context_meta.get("tenant_id")),
                    knowledge_base_id=str(context_meta.get("knowledge_base_id")),
                    document_id=str(context_meta.get("document_id")),
                    document_version_id=str(context_meta.get("document_version_id")) if context_meta.get("document_version_id") else None,
                    chunk_index=chunk_idx,
                    page_number=1,
                    heading_path=heading_path,
                    source_filename=extracted_doc.source_filename,
                    source_type=extracted_doc.mime_type,
                    parser_name=extracted_doc.parser_name,
                    parser_version=extracted_doc.parser_version,
                    chunking_strategy=self.name,
                    chunk_hash=calculate_chunk_hash(final_content),
                    character_count=len(final_content),
                    token_count=estimate_tokens(final_content),
                )
                processed_chunks.append(ProcessedChunk(content=final_content, metadata=meta))
                chunk_idx += 1

        return processed_chunks
