import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class MemberInviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="employee")
    department_id: uuid.UUID | None = None
    title: str | None = None


class MemberUpdateRequest(BaseModel):
    role: str | None = None
    department_id: uuid.UUID | None = None
    title: str | None = None
    status: str | None = None


class MemberResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    department_id: uuid.UUID | None = None
    department_name: str | None = None
    title: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    invitation_token: str | None = None
    invitation_expires_at: datetime | None = None

    model_config = {"from_attributes": True}
