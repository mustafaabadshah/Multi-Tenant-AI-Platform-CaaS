"""Pydantic v2 schemas for retrieval, embeddings, and vector stores."""

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field


class RetrievalConfigRead(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    retrieval_mode: str
    vector_store: str
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    similarity_metric: str
    top_k: int
    rrf_k: int
    rerank_enabled: bool
    rerank_provider: Optional[str] = None
    embedding_version: int
    has_api_key: bool = False
    masked_api_key: Optional[str] = None
    settings_json: dict[str, Any] = Field(default_factory=dict)


class RetrievalConfigUpdate(BaseModel):
    retrieval_mode: Optional[str] = None
    vector_store: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dimensions: Optional[int] = None
    similarity_metric: Optional[str] = None
    top_k: Optional[int] = Field(default=None, ge=1, le=50)
    rrf_k: Optional[int] = Field(default=None, ge=1, le=200)
    rerank_enabled: Optional[bool] = None
    rerank_provider: Optional[str] = None
    api_key: Optional[str] = None
    settings_json: Optional[dict[str, Any]] = None


class EmbeddingProviderRead(BaseModel):
    name: str
    default_model: str
    supported_models: list[str]
    default_dimensions: int


class ValidateProviderRequest(BaseModel):
    provider_name: str
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    dimensions: Optional[int] = None


class ValidateProviderResponse(BaseModel):
    valid: bool
    message: str
    dimensions: Optional[int] = None


class VectorStoreRead(BaseModel):
    type: str
    name: str
    description: str
    requires_embeddings: bool
    supports_hybrid: bool
    default_metric: str


class ValidateVectorStoreRequest(BaseModel):
    store_type: str
    endpoint: Optional[str] = None
    api_key: Optional[str] = None


class ValidateVectorStoreResponse(BaseModel):
    valid: bool
    status: str
    details: dict[str, Any] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    knowledge_base_ids: list[uuid.UUID] = Field(min_length=1)
    mode: Optional[str] = None  # "lexical", "semantic", "hybrid"
    vector_store: Optional[str] = None  # "pgvector", "qdrant", "fts"
    top_k: Optional[int] = Field(default=8, ge=1, le=50)
    document_ids: Optional[list[uuid.UUID]] = None


class SearchResultChunk(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    score: float
    rank: int
    content: str
    document_title: Optional[str] = None
    page_number: Optional[int] = None
    heading_path: Optional[str] = None
    chunk_index: int = 0
    retrieval_source: str = "semantic"
    metadata: dict[str, Any] = Field(default_factory=dict)


class CitationItem(BaseModel):
    citation_index: int
    label: str
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    page_number: Optional[int] = None
    heading_path: Optional[str] = None
    chunk_index: int
    snippet: str
    retrieval_source: str
    score: float


class SearchResponseSchema(BaseModel):
    query: str
    retrieval_mode: str
    vector_store: str
    embedding_provider: str
    total_results: int
    results: list[SearchResultChunk]
    citations: list[CitationItem]
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class IndexStatusResponse(BaseModel):
    knowledge_base_id: str
    retrieval_mode: str
    vector_store: str
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int
    active_embedding_version: int
    total_documents: int
    total_chunks: int
    indexed_chunks: int
    pending_chunks: int
    has_custom_api_key: bool
    last_indexed_at: Optional[str] = None
    vector_store_health: dict[str, Any] = Field(default_factory=dict)


class EmbeddingJobRead(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    embedding_version: int
    status: str
    stage: str
    total_chunks: int
    processed_chunks: int
    failed_chunks: int
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
