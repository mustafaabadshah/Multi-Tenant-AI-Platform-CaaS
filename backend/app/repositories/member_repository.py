import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.membership import TenantMembership
from app.repositories.base import TenantScopedRepository


class MemberRepository(TenantScopedRepository[TenantMembership]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(TenantMembership, session, tenant_id)

    async def list_members(self, limit: int = 50, offset: int = 0) -> Sequence[TenantMembership]:
        stmt = (
            select(TenantMembership)
            .options(
                selectinload(TenantMembership.user),
                selectinload(TenantMembership.role),
                selectinload(TenantMembership.department),
            )
            .where(TenantMembership.tenant_id == self.tenant_id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, membership_id: uuid.UUID) -> TenantMembership | None:
        stmt = (
            select(TenantMembership)
            .options(
                selectinload(TenantMembership.user),
                selectinload(TenantMembership.role),
                selectinload(TenantMembership.department),
            )
            .where(
                TenantMembership.id == membership_id,
                TenantMembership.tenant_id == self.tenant_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_user_id(self, user_id: uuid.UUID) -> TenantMembership | None:
        stmt = (
            select(TenantMembership)
            .options(
                selectinload(TenantMembership.user),
                selectinload(TenantMembership.role),
                selectinload(TenantMembership.department),
            )
            .where(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id == self.tenant_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_member(
        self,
        membership_id: uuid.UUID,
        role_id: uuid.UUID | None = None,
        department_id: uuid.UUID | None = None,
        title: str | None = None,
        status: str | None = None,
    ) -> TenantMembership | None:
        member = await self.get_by_id(membership_id)
        if not member:
            return None
        if role_id is not None:
            member.role_id = role_id
        if department_id is not None:
            member.department_id = department_id
        if title is not None:
            member.title = title
        if status is not None:
            member.status = status
        await self.session.flush()
        return member
