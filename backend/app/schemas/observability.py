"""Pydantic schemas for Observability, Request Traces, Policies, and Metrics."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SpanSchema(BaseModel):
    span_id: str
    name: str
    duration_ms: Optional[float] = None
    status: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class TraceDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trace_id: str
    tenant_id: str
    assistant_id: Optional[str] = None
    assistant_name: str
    conversation_id: Optional[str] = None
    traffic_type: str
    status: str
    error_category: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    total_duration_ms: Optional[float] = None
    ttft_ms: Optional[float] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    credential_source: str = "byok"
    retrieval_mode: Optional[str] = None
    retrieved_chunk_count: int = 0
    citation_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    is_token_estimated: bool = True
    estimated_cost_usd: Optional[float] = None
    pricing_status: str = "unknown"
    retrieval_metadata: Optional[dict[str, Any]] = None
    input_preview: Optional[str] = None
    output_preview: Optional[str] = None
    has_preview: bool = False
    span_count: int = 0
    spans: list[SpanSchema] = Field(default_factory=list)


class ObservabilityMetricsSchema(BaseModel):
    total_requests: int
    error_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_ttft_ms: float
    total_tokens: int
    estimated_cost_usd: float
    by_status: dict[str, int]
    by_traffic_type: dict[str, int]
    by_provider: dict[str, int]
    by_error_category: dict[str, int]


class ObservabilityPolicySchema(BaseModel):
    tenant_id: UUID
    capture_mode: str
    max_preview_length: int
    retention_days: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ObservabilityPolicyUpdate(BaseModel):
    capture_mode: Optional[str] = Field(default=None, pattern="^(METADATA_ONLY|REDACTED_PREVIEW)$")
    max_preview_length: Optional[int] = Field(default=None, ge=50, le=500)
    retention_days: Optional[int] = Field(default=None, ge=7, le=90)


class PurgeResultSchema(BaseModel):
    purged_count: int
    retention_days: int
    message: str
