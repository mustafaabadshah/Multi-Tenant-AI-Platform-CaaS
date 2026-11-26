"""Pydantic schemas for Assistant Publishing, Embed Widgets, and Developer API Keys."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AssistantPublicationCreate(BaseModel):
    visibility: str = Field(default="PUBLIC", description="PRIVATE, WORKSPACE, or PUBLIC")
    allowed_domains: list[str] = Field(default_factory=lambda: ["*"], description="Allowed origins for widget embed")
    custom_greeting: Optional[str] = Field(default=None, description="Initial greeting displayed in public / embed chat")
    brand_color: str = Field(default="#0284c7", description="Hex brand accent color")
    published_version_id: Optional[uuid.UUID] = Field(default=None, description="Specific configuration version to lock")


class AssistantPublicationUpdate(BaseModel):
    visibility: Optional[str] = None
    is_active: Optional[bool] = None
    allowed_domains: Optional[list[str]] = None
    custom_greeting: Optional[str] = None
    brand_color: Optional[str] = None


class AssistantPublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    assistant_id: uuid.UUID
    public_id: str
    visibility: str
    is_active: bool
    allowed_domains: list[str]
    custom_greeting: Optional[str]
    brand_color: str
    published_version_id: Optional[uuid.UUID]
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class PublicAssistantMetadataResponse(BaseModel):
    public_id: str
    name: str
    description: Optional[str]
    custom_greeting: Optional[str]
    brand_color: str
    avatar_url: Optional[str] = None
    visibility: str
    citation_style: str = "strict"


class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["assistant:read", "assistant:chat"])
    assistant_id: Optional[uuid.UUID] = Field(default=None, description="Optional single assistant restriction")
    expires_days: Optional[int] = Field(default=None, ge=1, le=365)


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    assistant_id: Optional[uuid.UUID] = None
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class APIKeyCreatedResponse(APIKeyResponse):
    raw_key: str = Field(..., description="Raw secret API key. Displayed ONCE upon generation.")


class PublicChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_token: Optional[str] = Field(default=None, description="Client session token for continuing dialog")


class DeveloperChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[uuid.UUID] = Field(default=None)
