import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant
from app.repositories.base import TenantScopedRepository
from app.repositories.tenant_repository import slugify


class AssistantRepository(TenantScopedRepository[Assistant]):
    def __init__(self, session: AsyncSession, tenant_id: uuid.UUID):
        super().__init__(Assistant, session, tenant_id)

    async def get_by_slug(self, slug: str) -> Assistant | None:
        stmt = select(Assistant).where(
            Assistant.tenant_id == self.tenant_id,
            Assistant.slug == slug,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_assistant(
        self,
        name: str,
        slug: str | None = None,
        description: str | None = None,
        default_model: str = "auto",
        system_prompt: str | None = None,
    ) -> Assistant:
        base_slug = slug or slugify(name)
        candidate_slug = base_slug
        count = 1
        while await self.get_by_slug(candidate_slug) is not None:
            candidate_slug = f"{base_slug}-{count}"
            count += 1

        assistant = Assistant(
            tenant_id=self.tenant_id,
            name=name,
            slug=candidate_slug,
            description=description,
            default_model=default_model,
            system_prompt=system_prompt,
            status="ACTIVE",
        )
        self.session.add(assistant)
        await self.session.flush()
        return assistant
