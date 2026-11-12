import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Document, KnowledgeBase
from app.repositories.base import TenantScopedRepository


class KnowledgeRepository(TenantScopedRepository[KnowledgeBase]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(KnowledgeBase, session, tenant_id)

    async def list_with_counts(
        self, limit: int = 50, offset: int = 0
    ) -> Sequence[tuple[KnowledgeBase, int]]:
        stmt = (
            select(
                KnowledgeBase,
                func.count(Document.id).label("document_count"),
            )
            .outerjoin(
                Document,
                (Document.knowledge_base_id == KnowledgeBase.id) & (Document.status != "DELETED"),
            )
            .where(KnowledgeBase.tenant_id == self.tenant_id)
            .group_by(KnowledgeBase.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.all()  # type: ignore[return-value]

    async def get_document_count(self, kb_id: uuid.UUID) -> int:
        stmt = select(func.count(Document.id)).where(
            Document.tenant_id == self.tenant_id,
            Document.knowledge_base_id == kb_id,
            Document.status != "DELETED",
        )
        res = await self.session.execute(stmt)
        return res.scalar_one() or 0

    async def update(self, kb_id: uuid.UUID, **kwargs: Any) -> KnowledgeBase | None:
        kb = await self.get_by_id(kb_id)
        if not kb:
            return None
        for k, v in kwargs.items():
            if hasattr(kb, k) and v is not None:
                setattr(kb, k, v)
        await self.session.flush()
        return kb

