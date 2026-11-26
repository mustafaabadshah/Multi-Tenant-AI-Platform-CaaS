"""API endpoints for Assistant Publishing and Distribution Management."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_db, require_permission
from app.core.constants import PermissionName
from app.models.assistant import Assistant
from app.models.publishing import AssistantPublication
from app.models.user import User
from app.repositories.assistant_repository import AssistantRepository
from app.schemas.publishing import (
    AssistantPublicationCreate,
    AssistantPublicationResponse,
    AssistantPublicationUpdate,
)
from app.services.publishing_service import PublishingService

router = APIRouter(prefix="/assistants", tags=["Assistant Publishing"])


def _serialize_publication(pub: AssistantPublication) -> AssistantPublicationResponse:
    try:
        domains = json.loads(pub.allowed_domains) if isinstance(pub.allowed_domains, str) else (pub.allowed_domains or [])
    except Exception:
        domains = ["*"]

    return AssistantPublicationResponse(
        id=pub.id,
        tenant_id=pub.tenant_id,
        assistant_id=pub.assistant_id,
        public_id=pub.public_id,
        visibility=pub.visibility,
        is_active=pub.is_active,
        allowed_domains=domains,
        custom_greeting=pub.custom_greeting,
        brand_color=pub.brand_color,
        published_version_id=pub.published_version_id,
        published_at=pub.published_at,
        created_at=pub.created_at,
        updated_at=pub.updated_at,
    )


@router.get("/{assistant_id}/publication", response_model=AssistantPublicationResponse)
async def get_publication_status(
    assistant_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> AssistantPublicationResponse:
    """Fetch current publication status and settings for an assistant."""
    repo = AssistantRepository(db, ctx.tenant.id)
    asst = await repo.get_by_id(assistant_id)
    if not asst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found in active workspace",
        )

    svc = PublishingService(db, ctx.tenant.id)
    pub = await svc.get_or_create_publication(assistant_id)
    return _serialize_publication(pub)


@router.post("/{assistant_id}/publish", response_model=AssistantPublicationResponse)
async def publish_assistant(
    assistant_id: uuid.UUID,
    payload: AssistantPublicationCreate,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_PUBLISH.value)),
    db: AsyncSession = Depends(get_db),
) -> AssistantPublicationResponse:
    """Publish an assistant, setting its visibility and distribution channels."""
    repo = AssistantRepository(db, ctx.tenant.id)
    asst = await repo.get_by_id(assistant_id)
    if not asst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found in active workspace",
        )

    svc = PublishingService(db, ctx.tenant.id)
    pub = await svc.publish_assistant(assistant_id, payload, user_id=ctx.membership.user_id)
    return _serialize_publication(pub)


@router.post("/{assistant_id}/unpublish", response_model=AssistantPublicationResponse)
async def unpublish_assistant(
    assistant_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_PUBLISH.value)),
    db: AsyncSession = Depends(get_db),
) -> AssistantPublicationResponse:
    """Immediately unpublish an assistant, deactivating its public web link and embed widgets."""
    repo = AssistantRepository(db, ctx.tenant.id)
    asst = await repo.get_by_id(assistant_id)
    if not asst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found in active workspace",
        )

    svc = PublishingService(db, ctx.tenant.id)
    pub = await svc.unpublish_assistant(assistant_id)
    return _serialize_publication(pub)


@router.patch("/{assistant_id}/publication", response_model=AssistantPublicationResponse)
async def update_publication_settings(
    assistant_id: uuid.UUID,
    payload: AssistantPublicationUpdate,
    ctx: TenantContext = Depends(require_permission(PermissionName.ASSISTANT_PUBLISH.value)),
    db: AsyncSession = Depends(get_db),
) -> AssistantPublicationResponse:
    """Update publication settings such as allowed domains, greeting, and visibility."""
    repo = AssistantRepository(db, ctx.tenant.id)
    asst = await repo.get_by_id(assistant_id)
    if not asst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found in active workspace",
        )

    svc = PublishingService(db, ctx.tenant.id)
    pub = await svc.update_publication(assistant_id, payload)
    return _serialize_publication(pub)
