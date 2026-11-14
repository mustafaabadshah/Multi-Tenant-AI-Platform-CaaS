"""Pydantic v2 schemas for AI Assistant Evaluation, Datasets, and Benchmarks."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvalDatasetItemCreate(BaseModel):
    question: str = Field(..., min_length=1, description="Question or benchmark prompt")
    expected_answer: Optional[str] = Field(default=None, description="Ground truth answer if available")
    expected_chunk_ids: list[str] = Field(default_factory=list, description="IDs of chunks expected to be retrieved")
    is_unanswerable: bool = Field(default=False, description="True if query cannot be answered from authorized context")
    is_adversarial: bool = Field(default=False, description="True for prompt injection or boundary testing")
    item_metadata: dict[str, Any] = Field(default_factory=dict, description="Custom tags or categorization")


class EvalDatasetItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    question: str
    expected_answer: Optional[str]
    expected_chunk_ids: list[str]
    is_unanswerable: bool
    is_adversarial: bool
    item_metadata: dict[str, Any]
    created_at: datetime


class EvalDatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)
    items: list[EvalDatasetItemCreate] = Field(default_factory=list, description="Initial dataset items")


class EvalDatasetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None


class EvalDatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: Optional[str]
    version: int
    is_system: bool
    item_count: int = 0
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class EvalDatasetDetailResponse(EvalDatasetResponse):
    items: list[EvalDatasetItemResponse] = []


class EvalRunCreate(BaseModel):
    assistant_id: uuid.UUID
    dataset_id: uuid.UUID
    eval_type: str = Field(default="deterministic", description="'deterministic', 'llm_judge', or 'hybrid'")
    judge_provider: Optional[str] = Field(default=None, description="Provider identifier if llm_judge selected")
    judge_model: Optional[str] = Field(default=None, description="Model identifier if llm_judge selected")


class EvalRunResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    item_id: uuid.UUID
    question: Optional[str] = None
    expected_answer: Optional[str] = None
    generated_answer: Optional[str]
    retrieved_chunks: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    recall_score: float
    mrr_score: float
    faithfulness_score: float
    citation_score: float
    latency_ms: int
    error_message: Optional[str]
    created_at: datetime


class EvalRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    assistant_id: uuid.UUID
    dataset_id: uuid.UUID
    status: str
    eval_type: str
    judge_provider: Optional[str]
    judge_model: Optional[str]
    metrics_summary: dict[str, Any]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    completed_at: Optional[datetime]
    result_count: int = 0


class EvalRunDetailResponse(EvalRunResponse):
    results: list[EvalRunResultResponse] = []


class EvalRunComparisonResponse(BaseModel):
    run_a_id: uuid.UUID
    run_b_id: uuid.UUID
    assistant_id: uuid.UUID
    metrics_delta: dict[str, float]
    summary_a: dict[str, Any]
    summary_b: dict[str, Any]
