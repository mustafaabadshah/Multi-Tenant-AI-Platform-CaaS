import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrganizationCreateRequest(BaseModel):
    legal_name: str = Field(min_length=2, max_length=255)
    domain: str | None = None
    tax_id: str | None = None
    logo_url: str | None = None


class OrganizationUpdateRequest(BaseModel):
    legal_name: str | None = None
    domain: str | None = None
    tax_id: str | None = None
    logo_url: str | None = None


class OrganizationResponse(BaseModel):
    tenant_id: uuid.UUID
    legal_name: str
    domain: str | None = None
    tax_id: str | None = None
    logo_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
