"""Pydantic schemas for Provider Directory, BYOK Credentials, Usage Accounting, and Playground."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ProviderCredentialCreate(BaseModel):
    provider_name: str = Field(min_length=2, max_length=50)
    display_name: str = Field(min_length=2, max_length=100)
    api_key: str = Field(min_length=4, max_length=500)
    base_url: Optional[str] = Field(default=None, max_length=255)
    is_default: bool = False


class ProviderCredentialRotateRequest(BaseModel):
    new_api_key: str = Field(min_length=4, max_length=500)


class ProviderCredentialResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    provider_name: str
    display_name: str
    api_key_masked: str
    base_url: Optional[str] = None
    is_active: bool
    is_default: bool
    status: str
    error_message: Optional[str] = None
    last_tested_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProviderModelInfo(BaseModel):
    model_id: str
    display_name: str
    context_window: int
    max_output_tokens: int
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_vision: bool = False
    supports_audio: bool = False
    description: str = ""


class ProviderDirectoryItem(BaseModel):
    name: str
    display_name: str
    description: str
    requires_api_key: bool
    default_base_url: Optional[str] = None
    models: list[ProviderModelInfo] = Field(default_factory=list)


class ProviderUsageSummaryResponse(BaseModel):
    monthly_tokens_used: int
    monthly_tokens_limit: int
    monthly_prompt_tokens: int
    monthly_completion_tokens: int
    percentage_used: float
    today_requests: int
    daily_request_limit: int
    by_provider: list[dict[str, Any]] = Field(default_factory=list)


class URLIngestRequest(BaseModel):
    knowledge_base_id: uuid.UUID
    url: str = Field(min_length=7, max_length=2000)


class PlaygroundSearchRequest(BaseModel):
    knowledge_base_id: uuid.UUID
    query: str = Field(min_length=1, max_length=1000)
    mode: str = Field(default="hybrid", pattern="^(hybrid|semantic|lexical)$")
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class PlaygroundChunkResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    rank: int
    sparse_score: Optional[float] = None
    dense_score: Optional[float] = None
    score: float
    retrieval_source: str
    content: str
    page_number: Optional[int] = None
    heading_path: Optional[str] = None


class PlaygroundSearchResponse(BaseModel):
    query: str
    knowledge_base_id: uuid.UUID
    retrieval_mode: str
    vector_store: str
    latency_ms: float
    total_results: int
    results: list[PlaygroundChunkResult] = Field(default_factory=list)
