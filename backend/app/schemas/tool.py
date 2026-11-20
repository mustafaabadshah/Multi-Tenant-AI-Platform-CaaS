"""Pydantic v2 schemas for the Tool Registry and Execution."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-]+$")
    display_name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    endpoint_url: str = Field(..., min_length=8, max_length=2000)
    method: str = Field(default="POST", pattern=r"^(GET|POST|PUT|PATCH|DELETE)$")
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    output_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})
    headers: dict[str, str] = Field(default_factory=dict)
    risk_level: str = Field(default="READ_ONLY", pattern=r"^(READ_ONLY|WRITE|HIGH_RISK)$")
    requires_approval: bool = Field(default=False)
    timeout_seconds: int = Field(default=15, ge=1, le=30)


class ToolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    display_name: str
    description: Optional[str]
    namespace: str
    tool_type: str
    risk_level: str
    requires_approval: bool
    is_enabled: bool
    version: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    http_config: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class ToolExecuteRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolExecuteResponse(BaseModel):
    status_code: int = 200
    is_success: bool = True
    data: Any
