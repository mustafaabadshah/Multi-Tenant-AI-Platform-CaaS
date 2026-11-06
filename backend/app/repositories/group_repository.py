import uuid
from collections.abc import Sequence

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
