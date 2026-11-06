import uuid
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class TenantScopedRepository(Generic[ModelType]):
    """Repository base ensuring all queries and operations are strictly scoped
    to a single tenant."""

    def __init__(self, model: type[ModelType], session: AsyncSession, tenant_id: uuid.UUID):
        self.model = model
        self.session = session
        self.tenant_id = tenant_id

    async def get_by_id(self, entity_id: uuid.UUID) -> ModelType | None:
        """Fetch a single entity by ID strictly within the active tenant."""
        stmt = select(self.model).where(
            self.model.id == entity_id,  # type: ignore[attr-defined]
            self.model.tenant_id == self.tenant_id,  # type: ignore[attr-defined]
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list(self, limit: int = 50, offset: int = 0) -> Sequence[ModelType]:
        """List entities strictly within the active tenant."""
        stmt = (
            select(self.model)
            .where(self.model.tenant_id == self.tenant_id)  # type: ignore[attr-defined]
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, **kwargs: Any) -> ModelType:
        """Create a new entity, guaranteeing the tenant_id belongs to the active tenant context."""
        kwargs["tenant_id"] = self.tenant_id
        entity = self.model(**kwargs)
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity_id: uuid.UUID) -> bool:
        """Delete an entity by ID strictly within the active tenant."""
        entity = await self.get_by_id(entity_id)
        if not entity:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True
