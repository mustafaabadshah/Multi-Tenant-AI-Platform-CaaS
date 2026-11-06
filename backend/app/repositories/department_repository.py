import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.models.membership import TenantMembership
from app.repositories.base import TenantScopedRepository


class DepartmentRepository(TenantScopedRepository[Department]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(Department, session, tenant_id)

    async def get_by_name(self, name: str) -> Department | None:
        stmt = select(Department).where(
            Department.tenant_id == self.tenant_id,
            func.lower(Department.name) == name.lower().strip(),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_with_member_counts(
        self, limit: int = 50, offset: int = 0
    ) -> Sequence[tuple[Department, int]]:
        stmt = (
            select(
                Department,
                func.count(TenantMembership.id).label("member_count"),
            )
            .outerjoin(
                TenantMembership,
                (TenantMembership.department_id == Department.id)
                & (TenantMembership.tenant_id == self.tenant_id),
            )
            .where(Department.tenant_id == self.tenant_id)
            .group_by(Department.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.all()  # type: ignore[return-value]

    async def update(
        self,
        department_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> Department | None:
        department = await self.get_by_id(department_id)
        if not department:
            return None
        if name is not None:
            department.name = name.strip()
        if description is not None:
            department.description = description.strip()
        await self.session.flush()
        return department
