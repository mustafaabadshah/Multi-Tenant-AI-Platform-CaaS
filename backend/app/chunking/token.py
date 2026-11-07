"""Token-Bounded Chunking Strategy."""

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
from app.parsers.base import ExtractedDocument


class TokenBoundedChunking(ChunkingStrategy):
    """Chunking strategy strictly bounded by token counts using lightweight word/punctuation tokenization."""

    @property
    def name(self) -> str:
        return "token"

    def chunk(
        self,
        extracted_doc: ExtractedDocument,
        context_meta: dict[str, Any],
        config: ChunkingConfig,
    ) -> list[ProcessedChunk]:
        # Target tokens: either config.max_tokens or chunk_size / 4
        target_tokens = config.max_tokens or max(50, config.chunk_size // 4)
        overlap_tokens = max(10, config.chunk_overlap // 4)

        processed_chunks: list[ProcessedChunk] = []

        # Split text into natural sentence or paragraph units
        sentences = re.split(r"(?<=[.!?\n])\s+", extracted_doc.text)
        current_chunk_sentences: list[str] = []
        current_token_count = 0
        chunk_idx = 0

        for sentence in sentences:
            sentence_clean = sentence.strip()
            if not sentence_clean:
                continue

            sent_tokens = estimate_tokens(sentence_clean)

            if current_token_count + sent_tokens <= target_tokens:
                current_chunk_sentences.append(sentence_clean)
                current_token_count += sent_tokens
            else:
                if current_chunk_sentences:
                    chunk_text = " ".join(current_chunk_sentences).strip()
                    meta = ChunkMetadata(
                        tenant_id=str(context_meta.get("tenant_id")),
                        knowledge_base_id=str(context_meta.get("knowledge_base_id")),
                        document_id=str(context_meta.get("document_id")),
                        document_version_id=str(context_meta.get("document_version_id")) if context_meta.get("document_version_id") else None,
                        chunk_index=chunk_idx,
                        page_number=1,
                        source_filename=extracted_doc.source_filename,
                        source_type=extracted_doc.mime_type,
                        parser_name=extracted_doc.parser_name,
                        parser_version=extracted_doc.parser_version,
                        chunking_strategy=self.name,
                        chunk_hash=calculate_chunk_hash(chunk_text),
                        character_count=len(chunk_text),
                        token_count=current_token_count,
                    )
                    processed_chunks.append(ProcessedChunk(content=chunk_text, metadata=meta))
                    chunk_idx += 1

                    # Retain overlap sentences
                    overlap_sentences: list[str] = []
                    overlap_count = 0
                    for s in reversed(current_chunk_sentences):
                        t_count = estimate_tokens(s)
                        if overlap_count + t_count <= overlap_tokens:
                            overlap_sentences.insert(0, s)
                            overlap_count += t_count
                        else:
                            break
                    current_chunk_sentences = overlap_sentences
                    current_token_count = overlap_count

                current_chunk_sentences.append(sentence_clean)
                current_token_count += sent_tokens

        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences).strip()
            meta = ChunkMetadata(
                tenant_id=str(context_meta.get("tenant_id")),
                knowledge_base_id=str(context_meta.get("knowledge_base_id")),
                document_id=str(context_meta.get("document_id")),
                document_version_id=str(context_meta.get("document_version_id")) if context_meta.get("document_version_id") else None,
                chunk_index=chunk_idx,
                page_number=1,
                source_filename=extracted_doc.source_filename,
                source_type=extracted_doc.mime_type,
                parser_name=extracted_doc.parser_name,
                parser_version=extracted_doc.parser_version,
                chunking_strategy=self.name,
                chunk_hash=calculate_chunk_hash(chunk_text),
                character_count=len(chunk_text),
                token_count=current_token_count,
            )
            processed_chunks.append(ProcessedChunk(content=chunk_text, metadata=meta))

        return processed_chunks
