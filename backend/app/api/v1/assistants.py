import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, require_permission
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.user import User
from app.repositories.assistant_repository import AssistantRepository
from app.repositories.audit_repository import AuditLogRepository
from app.schemas.assistant import (
    AssistantCreateRequest,
    AssistantResponse,
    AssistantUpdateRequest,
)

router = APIRouter(prefix="/assistants", tags=["Assistants"])


@router.get("", response_model=list[AssistantResponse])
async def list_assistants(
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[AssistantResponse]:
    repo = AssistantRepository(db, ctx.tenant.id)
    items = await repo.list()

    responses = []
    for a in items:
        kb_ids = await repo.get_connected_kb_ids(a.id)
        responses.append(
            AssistantResponse(
                id=a.id,
                tenant_id=a.tenant_id,
                name=a.name,
                slug=a.slug,
                description=a.description,
                llm_provider=a.llm_provider,
                default_model=a.default_model,
                temperature=a.temperature,
                max_tokens=a.max_tokens,
                visibility=a.visibility,
                retrieval_mode=a.retrieval_mode,
                top_k=a.top_k,
                system_prompt=a.system_prompt,
                status=a.status,
                connected_kb_ids=kb_ids,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
        )
    return responses


@router.post("", response_model=AssistantResponse, status_code=status.HTTP_201_CREATED)
async def create_assistant(
    payload: AssistantCreateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_CREATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssistantResponse:
    repo = AssistantRepository(db, ctx.tenant.id)
    assistant = await repo.create_assistant(
        name=payload.name.strip(),
        slug=payload.slug,
        description=payload.description,
        llm_provider=payload.llm_provider,
        default_model=payload.default_model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        visibility=payload.visibility,
        retrieval_mode=payload.retrieval_mode,
        top_k=payload.top_k,
        system_prompt=payload.system_prompt,
        knowledge_base_ids=payload.knowledge_base_ids,
    )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="assistant.create",
        resource_type="assistant",
        resource_id=assistant.id,
        actor_id=current_user.id,
        details={
            "name": assistant.name,
            "provider": assistant.llm_provider,
            "model": assistant.default_model,
        },
    )

    kb_ids = await repo.get_connected_kb_ids(assistant.id)
    return AssistantResponse(
        id=assistant.id,
        tenant_id=assistant.tenant_id,
        name=assistant.name,
        slug=assistant.slug,
        description=assistant.description,
        llm_provider=assistant.llm_provider,
        default_model=assistant.default_model,
        temperature=assistant.temperature,
        max_tokens=assistant.max_tokens,
        visibility=assistant.visibility,
        retrieval_mode=assistant.retrieval_mode,
        top_k=assistant.top_k,
        system_prompt=assistant.system_prompt,
        status=assistant.status,
        connected_kb_ids=kb_ids,
        created_at=assistant.created_at,
        updated_at=assistant.updated_at,
    )


@router.get("/{assistant_id}", response_model=AssistantResponse)
async def get_assistant(
    assistant_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> AssistantResponse:
    repo = AssistantRepository(db, ctx.tenant.id)
    assistant = await repo.get_by_id(assistant_id)
    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found in active workspace",
        )

    kb_ids = await repo.get_connected_kb_ids(assistant.id)
    return AssistantResponse(
        id=assistant.id,
        tenant_id=assistant.tenant_id,
        name=assistant.name,
        slug=assistant.slug,
        description=assistant.description,
        llm_provider=assistant.llm_provider,
        default_model=assistant.default_model,
        temperature=assistant.temperature,
        max_tokens=assistant.max_tokens,
        visibility=assistant.visibility,
        retrieval_mode=assistant.retrieval_mode,
        top_k=assistant.top_k,
        system_prompt=assistant.system_prompt,
        status=assistant.status,
        connected_kb_ids=kb_ids,
        created_at=assistant.created_at,
        updated_at=assistant.updated_at,
    )


@router.put("/{assistant_id}", response_model=AssistantResponse)
async def update_assistant(
    assistant_id: uuid.UUID,
    payload: AssistantUpdateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_CREATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssistantResponse:
    repo = AssistantRepository(db, ctx.tenant.id)
    updated = await repo.update_assistant(
        assistant_id=assistant_id,
        name=payload.name,
        description=payload.description,
        llm_provider=payload.llm_provider,
        default_model=payload.default_model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        visibility=payload.visibility,
        retrieval_mode=payload.retrieval_mode,
        top_k=payload.top_k,
        system_prompt=payload.system_prompt,
        status=payload.status,
        knowledge_base_ids=payload.knowledge_base_ids,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found in active workspace",
        )

    kb_ids = await repo.get_connected_kb_ids(updated.id)
    return AssistantResponse(
        id=updated.id,
        tenant_id=updated.tenant_id,
        name=updated.name,
        slug=updated.slug,
        description=updated.description,
        llm_provider=updated.llm_provider,
        default_model=updated.default_model,
        temperature=updated.temperature,
        max_tokens=updated.max_tokens,
        visibility=updated.visibility,
        retrieval_mode=updated.retrieval_mode,
        top_k=updated.top_k,
        system_prompt=updated.system_prompt,
        status=updated.status,
        connected_kb_ids=kb_ids,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete("/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant(
    assistant_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_DELETE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    repo = AssistantRepository(db, ctx.tenant.id)
    deleted = await repo.delete(assistant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found in active workspace",
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="assistant.delete",
        resource_type="assistant",
        resource_id=assistant_id,
        actor_id=current_user.id,
    )
