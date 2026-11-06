import uuid

from pydantic import BaseModel


class PermissionResponse(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    description: str | None = None

    model_config = {"from_attributes": True}


class RoleResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    description: str | None = None
    is_system: bool
    permissions: list[PermissionResponse] = []

    model_config = {"from_attributes": True}
