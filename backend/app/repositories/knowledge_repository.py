import uuid
from collections.abc import Sequence

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
            .outerjoin(Document, Document.knowledge_base_id == KnowledgeBase.id)
            .where(KnowledgeBase.tenant_id == self.tenant_id)
            .group_by(KnowledgeBase.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.all()  # type: ignore[return-value]
