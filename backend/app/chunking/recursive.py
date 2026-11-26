"""Recursive Character Chunking Strategy."""

from typing import Any

from app.chunking.base import (
    ChunkingConfig,
    ChunkingStrategy,
    ChunkMetadata,
    ProcessedChunk,
    calculate_chunk_hash,
    estimate_tokens,
)
from app.parsers.base import ExtractedDocument


def _split_text(text: str, delimiters: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    """Recursively split text along natural delimiter boundaries."""
    if not text or not text.strip():
        return []

    if len(text) <= chunk_size:
        return [text.strip()]

    # Pick first delimiter present in text
    chosen_delim = ""
    for delim in delimiters:
        if delim in text:
            chosen_delim = delim
            break

    splits = text.split(chosen_delim) if chosen_delim else list(text)
    next_delims = delimiters[delimiters.index(chosen_delim) + 1 :] if chosen_delim in delimiters else []

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0

    for piece in splits:
        piece_len = len(piece) + (len(chosen_delim) if current_chunk else 0)
        if current_len + piece_len <= chunk_size:
            current_chunk.append(piece)
            current_len += piece_len
        else:
            if current_chunk:
                joined = chosen_delim.join(current_chunk).strip()
                if joined:
                    chunks.append(joined)

                # Keep overlap pieces
                overlap_accum: list[str] = []
                overlap_len = 0
                for prev_piece in reversed(current_chunk):
                    if overlap_len + len(prev_piece) <= chunk_overlap:
                        overlap_accum.insert(0, prev_piece)
                        overlap_len += len(prev_piece)
                    else:
                        break
                current_chunk = overlap_accum
                current_len = sum(len(p) for p in current_chunk)

            # If a single piece is longer than chunk_size, split it with next delimiters
            if len(piece) > chunk_size and next_delims:
                sub_chunks = _split_text(piece, next_delims, chunk_size, chunk_overlap)
                chunks.extend(sub_chunks)
                current_chunk = []
                current_len = 0
            else:
                current_chunk.append(piece)
                current_len += len(piece)

    if current_chunk:
        joined = chosen_delim.join(current_chunk).strip()
        if joined:
            chunks.append(joined)

    return chunks


class RecursiveCharacterChunking(ChunkingStrategy):
    """Recursive Character Chunking preserving paragraphs, sentences, and words."""

    @property
    def name(self) -> str:
        return "recursive"

    def chunk(
        self,
        extracted_doc: ExtractedDocument,
        context_meta: dict[str, Any],
        config: ChunkingConfig,
    ) -> list[ProcessedChunk]:
        delimiters = ["\n\n", "\n", ". ", "? ", "! ", "; ", " ", ""]
        processed_chunks: list[ProcessedChunk] = []

        # If document has distinct pages with text, chunk page by page to preserve page number metadata
        if extracted_doc.pages and any(p.text for p in extracted_doc.pages):
            chunk_idx = 0
            for page in extracted_doc.pages:
                if not page.text.strip():
                    continue
                raw_chunks = _split_text(page.text, delimiters, config.chunk_size, config.chunk_overlap)
                for raw_text in raw_chunks:
                    clean_text = raw_text.strip()
                    if not clean_text:
                        continue
                    meta = ChunkMetadata(
                        tenant_id=str(context_meta.get("tenant_id")),
                        knowledge_base_id=str(context_meta.get("knowledge_base_id")),
                        document_id=str(context_meta.get("document_id")),
                        document_version_id=str(context_meta.get("document_version_id")) if context_meta.get("document_version_id") else None,
                        chunk_index=chunk_idx,
                        page_number=page.page_number,
                        source_filename=extracted_doc.source_filename,
                        source_type=extracted_doc.mime_type,
                        parser_name=extracted_doc.parser_name,
                        parser_version=extracted_doc.parser_version,
                        chunking_strategy=self.name,
                        chunk_hash=calculate_chunk_hash(clean_text),
                        character_count=len(clean_text),
                        token_count=estimate_tokens(clean_text),
                    )
                    processed_chunks.append(ProcessedChunk(content=clean_text, metadata=meta))
                    chunk_idx += 1
        else:
            # Chunk full document text
            raw_chunks = _split_text(extracted_doc.text, delimiters, config.chunk_size, config.chunk_overlap)
            for idx, raw_text in enumerate(raw_chunks):
                clean_text = raw_text.strip()
                if not clean_text:
                    continue
                meta = ChunkMetadata(
                    tenant_id=str(context_meta.get("tenant_id")),
                    knowledge_base_id=str(context_meta.get("knowledge_base_id")),
                    document_id=str(context_meta.get("document_id")),
                    document_version_id=str(context_meta.get("document_version_id")) if context_meta.get("document_version_id") else None,
                    chunk_index=idx,
                    page_number=1,
                    source_filename=extracted_doc.source_filename,
                    source_type=extracted_doc.mime_type,
                    parser_name=extracted_doc.parser_name,
                    parser_version=extracted_doc.parser_version,
                    chunking_strategy=self.name,
                    chunk_hash=calculate_chunk_hash(clean_text),
                    character_count=len(clean_text),
                    token_count=estimate_tokens(clean_text),
                )
                processed_chunks.append(ProcessedChunk(content=clean_text, metadata=meta))

        return processed_chunks
