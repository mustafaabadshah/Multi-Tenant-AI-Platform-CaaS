"""Pydantic schemas for In-App Assistant Message Feedback and Quality Telemetry."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class FeedbackRating(str, Enum):
    THUMBS_UP = "THUMBS_UP"
    THUMBS_DOWN = "THUMBS_DOWN"


class FeedbackCategory(str, Enum):
    ACCURACY = "ACCURACY"
    HALLUCINATION = "HALLUCINATION"
    HELPFULNESS = "HELPFULNESS"
    INCOMPLETE = "INCOMPLETE"
    TONE = "TONE"
    OTHER = "OTHER"


class FeedbackStatus(str, Enum):
    NEW = "NEW"
    REVIEWED = "REVIEWED"
    ACTIONED = "ACTIONED"
    CLOSED = "CLOSED"


class MessageFeedbackCreate(BaseModel):
    rating: FeedbackRating
    category: Optional[FeedbackCategory] = None
    comment: Optional[str] = Field(None, max_length=1000)


class MessageFeedbackUpdate(BaseModel):
    rating: Optional[FeedbackRating] = None
    category: Optional[FeedbackCategory] = None
    comment: Optional[str] = Field(None, max_length=1000)


class MessageFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    assistant_id: uuid.UUID
    user_id: uuid.UUID
    rating: str
    category: Optional[str] = None
    comment: Optional[str] = None
    status: str
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FeedbackListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    assistant_id: uuid.UUID
    assistant_name: Optional[str] = None
    user_id: uuid.UUID
    user_email: Optional[str] = None
    rating: str
    category: Optional[str] = None
    comment: Optional[str] = None
    status: str
    admin_notes: Optional[str] = None
    message_content_snippet: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FeedbackStatusUpdateRequest(BaseModel):
    status: FeedbackStatus
    admin_notes: Optional[str] = Field(None, max_length=2000)


class FeedbackTelemetryResponse(BaseModel):
    total_feedback_count: int
    positive_count: int
    negative_count: int
    positive_percentage: Optional[float] = None
    category_breakdown: dict[str, int]
    is_sparse_sample: bool
    status_breakdown: dict[str, int]
