import uuid
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant, AssistantKnowledgeBase
from app.models.knowledge import KnowledgeBase
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
        slug: Optional[str] = None,
        description: Optional[str] = None,
        llm_provider: str = "omniroute",
        default_model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        visibility: str = "workspace",
        retrieval_mode: str = "hybrid",
        top_k: int = 5,
        system_prompt: Optional[str] = None,
        knowledge_base_ids: Optional[list[uuid.UUID]] = None,
    ) -> Assistant:
        if not default_model or not default_model.strip():
            raise ValueError("default_model cannot be empty")
        valid_providers = {"omniroute", "openai", "mock"}
        if llm_provider.lower() not in valid_providers:
            raise ValueError(f"Unsupported LLM provider '{llm_provider}'. Supported: {sorted(valid_providers)}")

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
            llm_provider=llm_provider.lower(),
            default_model=default_model.strip(),
            temperature=temperature,
            max_tokens=max_tokens,
            visibility=visibility,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
            system_prompt=system_prompt,
            status="ACTIVE",
        )
        self.session.add(assistant)
        await self.session.flush()

        if knowledge_base_ids:
            valid_kb_stmt = select(KnowledgeBase.id).where(
                KnowledgeBase.id.in_(knowledge_base_ids),
                KnowledgeBase.tenant_id == self.tenant_id,
            )
            valid_ids = set((await self.session.execute(valid_kb_stmt)).scalars().all())
            invalid_ids = set(knowledge_base_ids) - valid_ids
            if invalid_ids:
                raise ValueError(f"Knowledge bases not found in this workspace: {invalid_ids}")

            for kb_id in knowledge_base_ids:
                assoc = AssistantKnowledgeBase(
                    id=uuid.uuid4(),
                    tenant_id=self.tenant_id,
                    assistant_id=assistant.id,
                    knowledge_base_id=kb_id,
                )
                self.session.add(assoc)
            await self.session.flush()

        return assistant

    async def update_assistant(
        self,
        assistant_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        llm_provider: Optional[str] = None,
        default_model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        visibility: Optional[str] = None,
        retrieval_mode: Optional[str] = None,
        top_k: Optional[int] = None,
        system_prompt: Optional[str] = None,
        status: Optional[str] = None,
        knowledge_base_ids: Optional[list[uuid.UUID]] = None,
    ) -> Optional[Assistant]:
        assistant = await self.get_by_id(assistant_id)
        if not assistant:
            return None

        if name is not None:
            assistant.name = name
        if description is not None:
            assistant.description = description
        if llm_provider is not None:
            valid_providers = {"omniroute", "openai", "mock"}
            if llm_provider.lower() not in valid_providers:
                raise ValueError(f"Unsupported LLM provider '{llm_provider}'. Supported: {sorted(valid_providers)}")
            assistant.llm_provider = llm_provider.lower()
        if default_model is not None:
            if not default_model or not default_model.strip():
                raise ValueError("default_model cannot be empty")
            assistant.default_model = default_model.strip()
        if temperature is not None:
            assistant.temperature = temperature
        if max_tokens is not None:
            assistant.max_tokens = max_tokens
        if visibility is not None:
            assistant.visibility = visibility
        if retrieval_mode is not None:
            assistant.retrieval_mode = retrieval_mode
        if top_k is not None:
            assistant.top_k = top_k
        if system_prompt is not None:
            assistant.system_prompt = system_prompt
        if status is not None:
            assistant.status = status

        if knowledge_base_ids is not None:
            if knowledge_base_ids:
                valid_kb_stmt = select(KnowledgeBase.id).where(
                    KnowledgeBase.id.in_(knowledge_base_ids),
                    KnowledgeBase.tenant_id == self.tenant_id,
                )
                valid_ids = set((await self.session.execute(valid_kb_stmt)).scalars().all())
                invalid_ids = set(knowledge_base_ids) - valid_ids
                if invalid_ids:
                    raise ValueError(f"Knowledge bases not found in this workspace: {invalid_ids}")

            # Delete existing links
            del_stmt = delete(AssistantKnowledgeBase).where(
                AssistantKnowledgeBase.assistant_id == assistant.id,
                AssistantKnowledgeBase.tenant_id == self.tenant_id,
            )
            await self.session.execute(del_stmt)

            # Insert new links
            for kb_id in knowledge_base_ids:
                assoc = AssistantKnowledgeBase(
                    id=uuid.uuid4(),
                    tenant_id=self.tenant_id,
                    assistant_id=assistant.id,
                    knowledge_base_id=kb_id,
                )
                self.session.add(assoc)

        await self.session.flush()
        return assistant

    async def get_connected_kb_ids(self, assistant_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(AssistantKnowledgeBase.knowledge_base_id).where(
            AssistantKnowledgeBase.assistant_id == assistant_id,
            AssistantKnowledgeBase.tenant_id == self.tenant_id,
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
