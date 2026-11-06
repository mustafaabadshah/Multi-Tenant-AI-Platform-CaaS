import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.membership import TenantMembership
from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.memberships).joinedload(TenantMembership.tenant),
                selectinload(User.memberships).joinedload(TenantMembership.role),
            )
            .where(User.id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.memberships).joinedload(TenantMembership.tenant),
                selectinload(User.memberships).joinedload(TenantMembership.role),
            )
            .where(User.email == email.lower().strip())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(
        self, email: str, hashed_password: str, full_name: str, is_superuser: bool = False
    ) -> User:
        user = User(
            email=email.lower().strip(),
            hashed_password=hashed_password,
            full_name=full_name.strip(),
            is_superuser=is_superuser,
        )
        self.session.add(user)
        await self.session.flush()
        return user
