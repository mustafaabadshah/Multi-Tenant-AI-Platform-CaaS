import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, require_permission
from app.assistant_runtime.runtime import AssistantRuntime
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.assistant import Assistant
from app.models.user import User
from app.repositories.assistant_repository import AssistantRepository
from app.repositories.audit_repository import AuditLogRepository
from app.schemas.assistant import (
    AssistantCreateRequest,
    AssistantResponse,
    AssistantRollbackRequest,
    AssistantTestPreviewRequest,
    AssistantUpdateRequest,
    AssistantVersionResponse,
)

router = APIRouter(prefix="/assistants", tags=["Assistants"])


def _to_response(assistant: Assistant, kb_ids: list[uuid.UUID]) -> AssistantResponse:
    """Helper to convert Assistant ORM entity into AssistantResponse schema."""
    return AssistantResponse(
        id=assistant.id,
        tenant_id=assistant.tenant_id,
        name=assistant.name,
        slug=assistant.slug,
        description=assistant.description,
        template_id=assistant.template_id,
        audience_level=assistant.audience_level or "general",
        response_style=assistant.response_style or "balanced",
        uncertainty_behavior=assistant.uncertainty_behavior or "admit",
        citation_style=assistant.citation_style or "strict",
        llm_provider=assistant.llm_provider,
        default_model=assistant.default_model,
        temperature=assistant.temperature,
        max_tokens=assistant.max_tokens,
        visibility=assistant.visibility,
        retrieval_mode=assistant.retrieval_mode,
        top_k=assistant.top_k,
        system_prompt=assistant.system_prompt,
        status=assistant.status,
        current_version_num=assistant.current_version_num or 1,
        connected_kb_ids=kb_ids,
        created_at=assistant.created_at,
        updated_at=assistant.updated_at,
    )


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
        responses.append(_to_response(a, kb_ids))
    return responses


@router.post("", response_model=AssistantResponse, status_code=status.HTTP_201_CREATED)
async def create_assistant(
    payload: AssistantCreateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_CREATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssistantResponse:
    repo = AssistantRepository(db, ctx.tenant.id)
    try:
        assistant = await repo.create_assistant(
            name=payload.name.strip(),
            slug=payload.slug,
            description=payload.description,
            template_id=payload.template_id,
            audience_level=payload.audience_level,
            response_style=payload.response_style,
            uncertainty_behavior=payload.uncertainty_behavior,
            citation_style=payload.citation_style,
            llm_provider=payload.llm_provider,
            default_model=payload.default_model,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            visibility=payload.visibility,
            retrieval_mode=payload.retrieval_mode,
            top_k=payload.top_k,
            system_prompt=payload.system_prompt,
            knowledge_base_ids=payload.knowledge_base_ids,
            actor_id=current_user.id,
            change_summary=(
                f"Created from template '{payload.template_id}'" if payload.template_id else "Created custom assistant"
            ),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="assistant.create",
        resource_type="assistant",
        resource_id=assistant.id,
        actor_id=current_user.id,
        details={
            "name": assistant.name,
            "template_id": assistant.template_id,
            "provider": assistant.llm_provider,
            "model": assistant.default_model,
        },
    )

    kb_ids = await repo.get_connected_kb_ids(assistant.id)
    return _to_response(assistant, kb_ids)


@router.post("/preview-test")
async def preview_test_assistant(
    payload: AssistantTestPreviewRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_EXECUTE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream live test preview tokens without creating or persisting empty draft conversations."""
    runtime = AssistantRuntime(
        session=db,
        tenant_id=ctx.tenant.id,
        user_id=current_user.id,
        is_admin=ctx.is_admin,
        user_department_id=ctx.membership.department_id if ctx.membership else None,
    )
    generator = runtime.stream_preview(
        user_message=payload.message,
        system_prompt=payload.system_prompt,
        llm_provider=payload.llm_provider or "mock",
        default_model=payload.default_model or "mock-model",
        temperature=payload.temperature or 0.7,
        max_tokens=payload.max_tokens or 1024,
        retrieval_mode=payload.retrieval_mode or "hybrid",
        top_k=payload.top_k or 5,
        knowledge_base_ids=payload.knowledge_base_ids,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
    return _to_response(assistant, kb_ids)


@router.put("/{assistant_id}", response_model=AssistantResponse)
async def update_assistant(
    assistant_id: uuid.UUID,
    payload: AssistantUpdateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_UPDATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssistantResponse:
    repo = AssistantRepository(db, ctx.tenant.id)
    try:
        updated = await repo.update_assistant(
            assistant_id=assistant_id,
            name=payload.name,
            description=payload.description,
            template_id=payload.template_id,
            audience_level=payload.audience_level,
            response_style=payload.response_style,
            uncertainty_behavior=payload.uncertainty_behavior,
            citation_style=payload.citation_style,
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
            actor_id=current_user.id,
            change_summary=payload.change_summary,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found in active workspace",
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="assistant.update",
        resource_type="assistant",
        resource_id=updated.id,
        actor_id=current_user.id,
        details={
            "name": updated.name,
            "version": updated.current_version_num,
            "change_summary": payload.change_summary,
        },
    )

    kb_ids = await repo.get_connected_kb_ids(updated.id)
    return _to_response(updated, kb_ids)


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


# -----------------------------------------------------------------------------
# CONFIGURATION VERSION HISTORY & ROLLBACK ENDPOINTS
# -----------------------------------------------------------------------------


@router.get("/{assistant_id}/versions", response_model=list[AssistantVersionResponse])
async def list_assistant_versions(
    assistant_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[AssistantVersionResponse]:
    """Retrieve all configuration version records for an assistant in descending version order."""
    repo = AssistantRepository(db, ctx.tenant.id)
    assistant = await repo.get_by_id(assistant_id)
    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found in active workspace",
        )

    versions = await repo.list_versions(assistant_id)
    return [
        AssistantVersionResponse(
            id=v.id,
            tenant_id=v.tenant_id,
            assistant_id=v.assistant_id,
            version_num=v.version_num,
            model_name=v.model_name,
            system_prompt=v.system_prompt,
            config_snapshot=v.config_snapshot or {},
            actor_id=v.actor_id,
            change_summary=v.change_summary,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.get("/{assistant_id}/versions/{version_num}", response_model=AssistantVersionResponse)
async def get_assistant_version(
    assistant_id: uuid.UUID,
    version_num: int,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> AssistantVersionResponse:
    """Retrieve a specific configuration version snapshot for an assistant."""
    repo = AssistantRepository(db, ctx.tenant.id)
    version = await repo.get_version(assistant_id, version_num)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_num} not found for this assistant in active workspace",
        )

    return AssistantVersionResponse(
        id=version.id,
        tenant_id=version.tenant_id,
        assistant_id=version.assistant_id,
        version_num=version.version_num,
        model_name=version.model_name,
        system_prompt=version.system_prompt,
        config_snapshot=version.config_snapshot or {},
        actor_id=version.actor_id,
        change_summary=version.change_summary,
        created_at=version.created_at,
    )


@router.post("/{assistant_id}/rollback", response_model=AssistantResponse)
async def rollback_assistant_version(
    assistant_id: uuid.UUID,
    payload: AssistantRollbackRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_UPDATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssistantResponse:
    """Roll back assistant configuration to a historical version.

    In accordance with the immutable audit requirement:
    - Restores the configuration snapshot from target_version_num.
    - Creates a NEW forward version representing the rollback.
    - Never deletes past version records.
    """
    repo = AssistantRepository(db, ctx.tenant.id)
    try:
        restored = await repo.rollback_to_version(
            assistant_id=assistant_id,
            target_version_num=payload.target_version_num,
            actor_id=current_user.id,
            change_summary=payload.change_summary or f"Rollback to version {payload.target_version_num}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="assistant.rollback",
        resource_type="assistant",
        resource_id=restored.id,
        actor_id=current_user.id,
        details={
            "target_version": payload.target_version_num,
            "new_version": restored.current_version_num,
            "change_summary": payload.change_summary,
        },
    )

    kb_ids = await repo.get_connected_kb_ids(restored.id)
    return _to_response(restored, kb_ids)
