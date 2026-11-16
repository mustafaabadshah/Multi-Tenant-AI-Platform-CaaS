"""Pydantic v2 schemas for MCP Connections and Remote Tool Discovery."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class MCPConnectionCreateRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    server_url: str = Field(..., min_length=8, max_length=2000)
    auth_mode: str = Field(default="NONE", pattern=r"^(NONE|BEARER_TOKEN|OAUTH)$")
    credential: Optional[str] = Field(default=None, max_length=2000)
    is_personal: bool = Field(default=False)


class MCPToolApproveRequest(BaseModel):
    tool_names: list[str] = Field(..., min_length=1)


class MCPConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    display_name: str
    server_url: str
    auth_mode: str
    connection_status: str
    server_capabilities: dict[str, Any] = Field(default_factory=dict)
    approved_tools: list[dict[str, Any]] = Field(default_factory=list)
    is_enabled: bool = True
    created_at: datetime
    updated_at: datetime


class MCPDiscoverResponse(BaseModel):
    server_url: str
    tools: list[dict[str, Any]] = Field(default_factory=list)
