"""Pydantic v2 schemas for Human-in-the-Loop Tool Approvals."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    conversation_id: uuid.UUID
    assistant_id: uuid.UUID
    user_id: uuid.UUID
    tool_id: str
    tool_name: str
    arguments: dict[str, Any]
    status: str
    approval_token: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class ToolApprovalDecisionRequest(BaseModel):
    token: Optional[str] = Field(default=None, max_length=150)
