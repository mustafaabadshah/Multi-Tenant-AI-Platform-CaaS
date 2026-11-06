import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.administration import AuditLog
from app.repositories.base import TenantScopedRepository


class AuditLogRepository(TenantScopedRepository[AuditLog]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(AuditLog, session, tenant_id)

    async def list_recent(self, limit: int = 50, offset: int = 0) -> Sequence[AuditLog]:
        stmt = (
            select(AuditLog)
            .options(selectinload(AuditLog.actor))
            .where(AuditLog.tenant_id == self.tenant_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def log_event(
        self,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | None = None,
        actor_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        details: dict | None = None,
    ) -> AuditLog:
        log = AuditLog(
            tenant_id=self.tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details=details or {},
        )
        self.session.add(log)
        await self.session.flush()
        return log
