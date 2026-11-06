import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    full_name: str = Field(min_length=2, max_length=255)
    organization_name: str | None = Field(
        default=None, description="Optional organization name if registering an enterprise"
    )


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class WorkspaceSummary(BaseModel):
    tenant_id: uuid.UUID
    tenant_name: str
    tenant_slug: str
    tenant_type: str
    role: str
    is_active: bool = False


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    status: str
    is_superuser: bool
    is_verified: bool
    created_at: datetime
    active_tenant_id: uuid.UUID | None = None
    workspaces: list[WorkspaceSummary] = []

    model_config = {"from_attributes": True}
