import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, require_permission
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.user import User
from app.repositories.assistant_repository import AssistantRepository
from app.repositories.audit_repository import AuditLogRepository
from app.schemas.assistant import AssistantCreateRequest, AssistantResponse

router = APIRouter(prefix="/assistants", tags=["Assistants Foundation"])


@router.get("", response_model=list[AssistantResponse])
async def list_assistants(
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[AssistantResponse]:
    repo = AssistantRepository(db, ctx.tenant.id)
    items = await repo.list()

    return [
        AssistantResponse(
            id=a.id,
            tenant_id=a.tenant_id,
            name=a.name,
            slug=a.slug,
            description=a.description,
            default_model=a.default_model,
            system_prompt=a.system_prompt,
            status=a.status,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in items
    ]


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
        default_model=payload.default_model,
        system_prompt=payload.system_prompt,
    )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="assistant.create",
        resource_type="assistant",
        resource_id=assistant.id,
        actor_id=current_user.id,
        details={"name": assistant.name, "model": assistant.default_model},
    )

    return AssistantResponse(
        id=assistant.id,
        tenant_id=assistant.tenant_id,
        name=assistant.name,
        slug=assistant.slug,
        description=assistant.description,
        default_model=assistant.default_model,
        system_prompt=assistant.system_prompt,
        status=assistant.status,
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

    return AssistantResponse(
        id=assistant.id,
        tenant_id=assistant.tenant_id,
        name=assistant.name,
        slug=assistant.slug,
        description=assistant.description,
        default_model=assistant.default_model,
        system_prompt=assistant.system_prompt,
        status=assistant.status,
        created_at=assistant.created_at,
        updated_at=assistant.updated_at,
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
