import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    actor_id: uuid.UUID | None = None
    actor_name: str | None = None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None = None
    ip_address: str | None = None
    details: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}
