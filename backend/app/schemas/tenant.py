import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import TenantType


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    type: TenantType = Field(default=TenantType.INDIVIDUAL)
    slug: str | None = Field(default=None, max_length=255)
    legal_name: str | None = None
    domain: str | None = None


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    settings: dict | None = None


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    type: str
    status: str
    settings: dict = {}
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
