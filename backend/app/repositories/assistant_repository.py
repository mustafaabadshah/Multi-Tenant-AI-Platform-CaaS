import uuid
from typing import Any, Optional

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant import Assistant, AssistantKnowledgeBase, AssistantVersion
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

    def _build_config_snapshot(
        self,
        assistant: Assistant,
        knowledge_base_ids: list[uuid.UUID],
    ) -> dict[str, Any]:
        """Construct an immutable, JSON-serializable snapshot of the assistant's effective configuration."""
        return {
            "name": assistant.name,
            "slug": assistant.slug,
            "description": assistant.description,
            "template_id": assistant.template_id,
            "audience_level": assistant.audience_level,
            "response_style": assistant.response_style,
            "uncertainty_behavior": assistant.uncertainty_behavior,
            "citation_style": assistant.citation_style,
            "llm_provider": assistant.llm_provider,
            "default_model": assistant.default_model,
            "temperature": assistant.temperature,
            "max_tokens": assistant.max_tokens,
            "visibility": assistant.visibility,
            "retrieval_mode": assistant.retrieval_mode,
            "top_k": assistant.top_k,
            "system_prompt": assistant.system_prompt,
            "status": assistant.status,
            "knowledge_base_ids": [str(k) for k in knowledge_base_ids],
        }

    async def create_assistant(
        self,
        name: str,
        slug: Optional[str] = None,
        description: Optional[str] = None,
        template_id: Optional[str] = None,
        audience_level: str = "general",
        response_style: str = "balanced",
        uncertainty_behavior: str = "admit",
        citation_style: str = "strict",
        llm_provider: str = "omniroute",
        default_model: str = "auto",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        visibility: str = "workspace",
        retrieval_mode: str = "hybrid",
        top_k: int = 5,
        system_prompt: Optional[str] = None,
        knowledge_base_ids: Optional[list[uuid.UUID]] = None,
        actor_id: Optional[uuid.UUID] = None,
        change_summary: Optional[str] = None,
    ) -> Assistant:
        if not default_model or not default_model.strip():
            raise ValueError("default_model cannot be empty")
        valid_providers = {"omniroute", "openai", "mock"}
        if llm_provider.lower() not in valid_providers:
            raise ValueError(
                f"Unsupported LLM provider '{llm_provider}'. Supported: {sorted(valid_providers)}"
            )

        base_slug = slug or slugify(name)
        candidate_slug = base_slug
        count = 1
        while await self.get_by_slug(candidate_slug) is not None:
            candidate_slug = f"{base_slug}-{count}"
            count += 1

        kb_ids = knowledge_base_ids or []
        if kb_ids:
            valid_kb_stmt = select(KnowledgeBase.id).where(
                KnowledgeBase.id.in_(kb_ids),
                KnowledgeBase.tenant_id == self.tenant_id,
            )
            valid_ids = set((await self.session.execute(valid_kb_stmt)).scalars().all())
            invalid_ids = set(kb_ids) - valid_ids
            if invalid_ids:
                raise ValueError(f"Knowledge bases not found in this workspace: {invalid_ids}")

        assistant = Assistant(
            tenant_id=self.tenant_id,
            name=name,
            slug=candidate_slug,
            description=description,
            template_id=template_id,
            audience_level=audience_level,
            response_style=response_style,
            uncertainty_behavior=uncertainty_behavior,
            citation_style=citation_style,
            llm_provider=llm_provider.lower(),
            default_model=default_model.strip(),
            temperature=temperature,
            max_tokens=max_tokens,
            visibility=visibility,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
            system_prompt=system_prompt,
            status="ACTIVE",
            current_version_num=1,
        )
        self.session.add(assistant)
        await self.session.flush()

        for kb_id in kb_ids:
            assoc = AssistantKnowledgeBase(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                assistant_id=assistant.id,
                knowledge_base_id=kb_id,
            )
            self.session.add(assoc)
        await self.session.flush()

        # Create Version 1 snapshot
        snapshot = self._build_config_snapshot(assistant, kb_ids)
        summary = change_summary or (
            f"Initial creation from template '{template_id}'" if template_id else "Initial assistant creation"
        )
        v1 = AssistantVersion(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            assistant_id=assistant.id,
            version_num=1,
            model_name=assistant.default_model,
            system_prompt=assistant.system_prompt,
            config_snapshot=snapshot,
            actor_id=actor_id,
            change_summary=summary,
        )
        self.session.add(v1)
        await self.session.flush()

        return assistant

    async def update_assistant(
        self,
        assistant_id: uuid.UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        template_id: Optional[str] = None,
        audience_level: Optional[str] = None,
        response_style: Optional[str] = None,
        uncertainty_behavior: Optional[str] = None,
        citation_style: Optional[str] = None,
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
        actor_id: Optional[uuid.UUID] = None,
        change_summary: Optional[str] = None,
    ) -> Optional[Assistant]:
        assistant = await self.get_by_id(assistant_id)
        if not assistant:
            return None

        # Track if any configuration fields are changing
        changed = False

        if name is not None and name != assistant.name:
            assistant.name = name
            changed = True
        if description is not None and description != assistant.description:
            assistant.description = description
            changed = True
        if template_id is not None and template_id != assistant.template_id:
            assistant.template_id = template_id
            changed = True
        if audience_level is not None and audience_level != assistant.audience_level:
            assistant.audience_level = audience_level
            changed = True
        if response_style is not None and response_style != assistant.response_style:
            assistant.response_style = response_style
            changed = True
        if uncertainty_behavior is not None and uncertainty_behavior != assistant.uncertainty_behavior:
            assistant.uncertainty_behavior = uncertainty_behavior
            changed = True
        if citation_style is not None and citation_style != assistant.citation_style:
            assistant.citation_style = citation_style
            changed = True
        if llm_provider is not None:
            valid_providers = {"omniroute", "openai", "mock"}
            if llm_provider.lower() not in valid_providers:
                raise ValueError(
                    f"Unsupported LLM provider '{llm_provider}'. Supported: {sorted(valid_providers)}"
                )
            if llm_provider.lower() != assistant.llm_provider:
                assistant.llm_provider = llm_provider.lower()
                changed = True
        if default_model is not None:
            if not default_model or not default_model.strip():
                raise ValueError("default_model cannot be empty")
            if default_model.strip() != assistant.default_model:
                assistant.default_model = default_model.strip()
                changed = True
        if temperature is not None and temperature != assistant.temperature:
            assistant.temperature = temperature
            changed = True
        if max_tokens is not None and max_tokens != assistant.max_tokens:
            assistant.max_tokens = max_tokens
            changed = True
        if visibility is not None and visibility != assistant.visibility:
            assistant.visibility = visibility
            changed = True
        if retrieval_mode is not None and retrieval_mode != assistant.retrieval_mode:
            assistant.retrieval_mode = retrieval_mode
            changed = True
        if top_k is not None and top_k != assistant.top_k:
            assistant.top_k = top_k
            changed = True
        if system_prompt is not None and system_prompt != assistant.system_prompt:
            assistant.system_prompt = system_prompt
            changed = True
        if status is not None and status != assistant.status:
            assistant.status = status
            changed = True

        current_kbs = await self.get_connected_kb_ids(assistant.id)
        effective_kbs = current_kbs

        if knowledge_base_ids is not None:
            new_kb_set = set(knowledge_base_ids)
            if new_kb_set != set(current_kbs):
                changed = True
                effective_kbs = list(knowledge_base_ids)
                if knowledge_base_ids:
                    valid_kb_stmt = select(KnowledgeBase.id).where(
                        KnowledgeBase.id.in_(knowledge_base_ids),
                        KnowledgeBase.tenant_id == self.tenant_id,
                    )
                    valid_ids = set((await self.session.execute(valid_kb_stmt)).scalars().all())
                    invalid_ids = set(knowledge_base_ids) - valid_ids
                    if invalid_ids:
                        raise ValueError(f"Knowledge bases not found in this workspace: {invalid_ids}")

                del_stmt = delete(AssistantKnowledgeBase).where(
                    AssistantKnowledgeBase.assistant_id == assistant.id,
                    AssistantKnowledgeBase.tenant_id == self.tenant_id,
                )
                await self.session.execute(del_stmt)

                for kb_id in knowledge_base_ids:
                    assoc = AssistantKnowledgeBase(
                        id=uuid.uuid4(),
                        tenant_id=self.tenant_id,
                        assistant_id=assistant.id,
                        knowledge_base_id=kb_id,
                    )
                    self.session.add(assoc)

        if changed:
            new_version_num = (assistant.current_version_num or 1) + 1
            assistant.current_version_num = new_version_num

            snapshot = self._build_config_snapshot(assistant, effective_kbs)
            version_record = AssistantVersion(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                assistant_id=assistant.id,
                version_num=new_version_num,
                model_name=assistant.default_model,
                system_prompt=assistant.system_prompt,
                config_snapshot=snapshot,
                actor_id=actor_id,
                change_summary=change_summary or f"Updated to version {new_version_num}",
            )
            self.session.add(version_record)

        await self.session.flush()
        return assistant

    async def get_connected_kb_ids(self, assistant_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(AssistantKnowledgeBase.knowledge_base_id).where(
            AssistantKnowledgeBase.assistant_id == assistant_id,
            AssistantKnowledgeBase.tenant_id == self.tenant_id,
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def list_versions(self, assistant_id: uuid.UUID) -> list[AssistantVersion]:
        """List all configuration version records for an assistant in descending version order."""
        stmt = (
            select(AssistantVersion)
            .where(
                AssistantVersion.assistant_id == assistant_id,
                AssistantVersion.tenant_id == self.tenant_id,
            )
            .order_by(desc(AssistantVersion.version_num))
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_version(
        self, assistant_id: uuid.UUID, version_num: int
    ) -> Optional[AssistantVersion]:
        """Retrieve a specific version record for an assistant."""
        stmt = select(AssistantVersion).where(
            AssistantVersion.assistant_id == assistant_id,
            AssistantVersion.tenant_id == self.tenant_id,
            AssistantVersion.version_num == version_num,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def rollback_to_version(
        self,
        assistant_id: uuid.UUID,
        target_version_num: int,
        actor_id: Optional[uuid.UUID] = None,
        change_summary: Optional[str] = None,
    ) -> Assistant:
        """Rollback an assistant configuration to a historical version.

        Crucial security & auditing invariant:
        - Never deletes historical versions.
        - Restores configuration from target snapshot.
        - Creates a NEW forward version recording the rollback event.
        """
        assistant = await self.get_by_id(assistant_id)
        if not assistant:
            raise ValueError("Assistant not found in this workspace")

        target_version = await self.get_version(assistant_id, target_version_num)
        if not target_version:
            raise ValueError(f"Version {target_version_num} not found for this assistant")

        snapshot = target_version.config_snapshot or {}

        # Restore configuration fields from snapshot
        if "name" in snapshot:
            assistant.name = snapshot["name"]
        if "description" in snapshot:
            assistant.description = snapshot["description"]
        if "template_id" in snapshot:
            assistant.template_id = snapshot["template_id"]
        if "audience_level" in snapshot:
            assistant.audience_level = snapshot["audience_level"]
        if "response_style" in snapshot:
            assistant.response_style = snapshot["response_style"]
        if "uncertainty_behavior" in snapshot:
            assistant.uncertainty_behavior = snapshot["uncertainty_behavior"]
        if "citation_style" in snapshot:
            assistant.citation_style = snapshot["citation_style"]
        if "llm_provider" in snapshot:
            assistant.llm_provider = snapshot["llm_provider"]
        if "default_model" in snapshot:
            assistant.default_model = snapshot["default_model"]
        if "temperature" in snapshot:
            assistant.temperature = float(snapshot["temperature"])
        if "max_tokens" in snapshot:
            assistant.max_tokens = int(snapshot["max_tokens"])
        if "visibility" in snapshot:
            assistant.visibility = snapshot["visibility"]
        if "retrieval_mode" in snapshot:
            assistant.retrieval_mode = snapshot["retrieval_mode"]
        if "top_k" in snapshot:
            assistant.top_k = int(snapshot["top_k"])
        if "system_prompt" in snapshot:
            assistant.system_prompt = snapshot["system_prompt"]

        # Restore connected KBs from snapshot
        target_kb_ids_raw = snapshot.get("knowledge_base_ids", [])
        target_kb_ids = [uuid.UUID(k) for k in target_kb_ids_raw if k]

        # Verify which of these KBs still exist in the tenant
        valid_kbs = []
        if target_kb_ids:
            valid_kb_stmt = select(KnowledgeBase.id).where(
                KnowledgeBase.id.in_(target_kb_ids),
                KnowledgeBase.tenant_id == self.tenant_id,
            )
            valid_kbs = list((await self.session.execute(valid_kb_stmt)).scalars().all())

        del_stmt = delete(AssistantKnowledgeBase).where(
            AssistantKnowledgeBase.assistant_id == assistant.id,
            AssistantKnowledgeBase.tenant_id == self.tenant_id,
        )
        await self.session.execute(del_stmt)

        for kb_id in valid_kbs:
            assoc = AssistantKnowledgeBase(
                id=uuid.uuid4(),
                tenant_id=self.tenant_id,
                assistant_id=assistant.id,
                knowledge_base_id=kb_id,
            )
            self.session.add(assoc)

        # Create new forward version for the rollback
        new_version_num = (assistant.current_version_num or 1) + 1
        assistant.current_version_num = new_version_num

        new_snapshot = self._build_config_snapshot(assistant, valid_kbs)
        summary = change_summary or f"Rollback to configuration of version {target_version_num}"
        rollback_version = AssistantVersion(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            assistant_id=assistant.id,
            version_num=new_version_num,
            model_name=assistant.default_model,
            system_prompt=assistant.system_prompt,
            config_snapshot=new_snapshot,
            actor_id=actor_id,
            change_summary=summary,
        )
        self.session.add(rollback_version)
        await self.session.flush()

        return assistant
