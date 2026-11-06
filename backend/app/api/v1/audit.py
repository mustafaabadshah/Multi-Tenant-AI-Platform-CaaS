from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, require_permission
from app.core.constants import PermissionName
from app.database.session import get_db
from app.repositories.audit_repository import AuditLogRepository
from app.schemas.audit import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    limit: int = 50,
    offset: int = 0,
    ctx: TenantContext = Depends(require_permission(PermissionName.AUDIT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogResponse]:
    repo = AuditLogRepository(db, ctx.tenant.id)
    items = await repo.list_recent(limit=limit, offset=offset)

    return [
        AuditLogResponse(
            id=log.id,
            tenant_id=log.tenant_id,
            actor_id=log.actor_id,
            actor_name=log.actor.full_name if log.actor else "System",
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            ip_address=log.ip_address,
            details=log.details,
            created_at=log.created_at,
        )
        for log in items
    ]
