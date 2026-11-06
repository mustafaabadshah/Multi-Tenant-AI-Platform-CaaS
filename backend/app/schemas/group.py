import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class EmployeeGroupCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    department_id: uuid.UUID | None = None


class EmployeeGroupUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    department_id: uuid.UUID | None = None


class EmployeeGroupResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    department_id: uuid.UUID | None = None
    name: str
    description: str | None = None
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
