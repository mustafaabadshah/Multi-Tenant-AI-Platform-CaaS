import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group import EmployeeGroup, GroupMembership
from app.repositories.base import TenantScopedRepository


class GroupRepository(TenantScopedRepository[EmployeeGroup]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(EmployeeGroup, session, tenant_id)

    async def get_by_name(self, name: str) -> EmployeeGroup | None:
        stmt = select(EmployeeGroup).where(
            EmployeeGroup.tenant_id == self.tenant_id,
            func.lower(EmployeeGroup.name) == name.lower().strip(),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_with_member_counts(
        self, limit: int = 50, offset: int = 0
    ) -> Sequence[tuple[EmployeeGroup, int]]:
        stmt = (
            select(
                EmployeeGroup,
                func.count(GroupMembership.id).label("member_count"),
            )
            .outerjoin(GroupMembership, GroupMembership.group_id == EmployeeGroup.id)
            .where(EmployeeGroup.tenant_id == self.tenant_id)
            .group_by(EmployeeGroup.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.all()  # type: ignore[return-value]

    async def update(
        self,
        group_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        department_id: uuid.UUID | None = None,
    ) -> EmployeeGroup | None:
        group = await self.get_by_id(group_id)
        if not group:
            return None
        if name is not None:
            group.name = name.strip()
        if description is not None:
            group.description = description.strip()
        if department_id is not None:
            group.department_id = department_id
        await self.session.flush()
        return group

    async def add_member(self, group_id: uuid.UUID, membership_id: uuid.UUID) -> GroupMembership:
        from app.models.membership import TenantMembership

        group = await self.get_by_id(group_id)
        if not group:
            raise ValueError("Group not found in active workspace")

        stmt_mem = select(TenantMembership).where(
            TenantMembership.id == membership_id,
            TenantMembership.tenant_id == self.tenant_id,
        )
        mem_res = await self.session.execute(stmt_mem)
        mem = mem_res.scalar_one_or_none()
        if not mem:
            raise ValueError("Membership not found in active workspace")

        stmt_existing = select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.membership_id == membership_id,
        )
        existing = (await self.session.execute(stmt_existing)).scalar_one_or_none()
        if existing:
            return existing

        enrollment = GroupMembership(group_id=group_id, membership_id=membership_id)
        self.session.add(enrollment)
        await self.session.flush()
        return enrollment

    async def remove_member(self, group_id: uuid.UUID, membership_id: uuid.UUID) -> bool:
        group = await self.get_by_id(group_id)
        if not group:
            return False

        stmt = select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.membership_id == membership_id,
        )
        membership = (await self.session.execute(stmt)).scalar_one_or_none()
        if not membership:
            return False

        await self.session.delete(membership)
        await self.session.flush()
        return True

    async def list_members(
        self, group_id: uuid.UUID
    ) -> Sequence[tuple[GroupMembership, Any, Any]]:
        from app.models.membership import TenantMembership
        from app.models.user import User

        group = await self.get_by_id(group_id)
        if not group:
            return []

        stmt = (
            select(GroupMembership, TenantMembership, User)
            .join(TenantMembership, GroupMembership.membership_id == TenantMembership.id)
            .join(User, TenantMembership.user_id == User.id)
            .where(
                GroupMembership.group_id == group_id,
                TenantMembership.tenant_id == self.tenant_id,
            )
        )
        res = await self.session.execute(stmt)
        return res.all()

