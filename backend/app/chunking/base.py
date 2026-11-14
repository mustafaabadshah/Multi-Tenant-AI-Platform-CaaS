"""Base classes, metadata models, and abstract interface for chunking strategies."""

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.parsers.base import ExtractedDocument


def estimate_tokens(text: str) -> int:
    """Lightweight token estimator without downloading heavy models (~4 chars/token)."""
    if not text:
        return 0
    # Words + punctuation tokens heuristic
    tokens = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
    return max(1, len(tokens))


def calculate_chunk_hash(content: str) -> str:
    """SHA-256 hash of normalized chunk text."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


@dataclass
class ChunkMetadata:
    """Comprehensive source provenance metadata for a single chunk."""
    tenant_id: str
    knowledge_base_id: str
    document_id: str
    document_version_id: str | None = None
    chunk_index: int = 0
    page_number: int | None = None
    heading_path: str | None = None
    source_filename: str = ""
    source_type: str = ""
    parser_name: str = ""
    parser_version: str = "1.0.0"
    chunking_strategy: str = "recursive"
    chunking_config_version: str = "1.0.0"
    chunk_hash: str = ""
    character_count: int = 0
    token_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "knowledge_base_id": self.knowledge_base_id,
            "document_id": self.document_id,
            "document_version_id": self.document_version_id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "heading_path": self.heading_path,
            "source_filename": self.source_filename,
            "source_type": self.source_type,
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "chunking_strategy": self.chunking_strategy,
            "chunking_config_version": self.chunking_config_version,
            "chunk_hash": self.chunk_hash,
            "character_count": self.character_count,
            "token_count": self.token_count,
            "extra": self.extra,
        }


@dataclass
class ProcessedChunk:
    """Output chunk with text content and structured provenance metadata."""
    content: str
    metadata: ChunkMetadata


@dataclass
class ChunkingConfig:
    """Configurable options for chunking engine."""
    chunk_size: int = 1000
    chunk_overlap: int = 200
    strategy: str = "recursive"
    preserve_headers: bool = True
    max_tokens: int | None = None
    config_version: str = "1.0.0"


class ChunkingStrategy(ABC):
    """Abstract interface for document chunking algorithms."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def chunk(
        self,
        extracted_doc: ExtractedDocument,
        context_meta: dict[str, Any],
        config: ChunkingConfig,
    ) -> list[ProcessedChunk]:
        """Split extracted document content into structured chunks with full provenance."""
        pass
