import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class KnowledgeBaseUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    status: str | None = None


class KnowledgeBaseResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    status: str
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Milestone 02: Document Ingestion & Extraction Schemas ---


class DocumentResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    filename: str
    safe_filename: str
    file_size: int
    mime_type: str
    file_hash: str | None = None
    status: str
    current_version_num: int
    total_pages: int
    total_chunks: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentVersionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version_num: int
    file_size: int
    file_hash: str | None = None
    parser_name: str | None = None
    parser_version: str | None = None
    ocr_applied: bool
    ocr_provider: str | None = None
    ocr_language: str | None = None
    extraction_stats: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID | None = None
    chunk_index: int
    content: str
    character_count: int
    token_count: int
    page_number: int | None = None
    heading_path: str | None = None
    chunk_hash: str | None = None
    chunking_strategy: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestionJobResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID | None = None
    status: str
    stage: str
    progress_pct: int
    retry_count: int
    max_retries: int
    error_category: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    job_metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestionEventResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    document_id: uuid.UUID
    stage: str
    status: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestionConfigResponse(BaseModel):
    knowledge_base_id: uuid.UUID
    chunking_strategy: str
    chunk_size: int
    chunk_overlap: int
    ocr_enabled: bool
    ocr_provider: str
    ocr_language: str
    max_file_size_mb: int
    settings_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class IngestionConfigUpdateRequest(BaseModel):
    chunking_strategy: str | None = Field(default=None, pattern="^(recursive|markdown|token|structured)$")
    chunk_size: int | None = Field(default=None, ge=100, le=10000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=2000)
    ocr_enabled: bool | None = None
    ocr_provider: str | None = None
    ocr_language: str | None = Field(default=None, max_length=20)
    max_file_size_mb: int | None = Field(default=None, ge=1, le=500)


class DocumentContentResponse(BaseModel):
    document_id: uuid.UUID
    version_num: int
    filename: str
    mime_type: str
    total_pages: int
    extracted_text: str | None = None
    structured_data: dict[str, Any] = Field(default_factory=dict)
    extraction_stats: dict[str, Any] = Field(default_factory=dict)


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    job: IngestionJobResponse
    is_duplicate: bool
