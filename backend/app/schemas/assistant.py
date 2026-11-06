import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AssistantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    default_model: str = Field(default="auto")
    system_prompt: str | None = None


class AssistantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    default_model: str | None = None
    system_prompt: str | None = None
    status: str | None = None


class AssistantResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    default_model: str
    system_prompt: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
