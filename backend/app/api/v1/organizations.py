import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user, require_permission
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.organization import Organization
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.schemas.organization import OrganizationResponse, OrganizationUpdateRequest

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/{tenant_id}", response_model=OrganizationResponse)
async def get_organization(
    tenant_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.TENANT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    stmt = select(Organization).where(Organization.tenant_id == ctx.tenant.id)
    res = await db.execute(stmt)
    org = res.scalars().first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization profile not found for this workspace",
        )

    return OrganizationResponse(
        tenant_id=org.tenant_id,
        legal_name=org.legal_name,
        domain=org.domain,
        tax_id=org.tax_id,
        logo_url=org.logo_url,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


@router.patch("/{tenant_id}", response_model=OrganizationResponse)
async def update_organization(
    tenant_id: uuid.UUID,
    payload: OrganizationUpdateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.TENANT_UPDATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    stmt = select(Organization).where(Organization.tenant_id == ctx.tenant.id)
    res = await db.execute(stmt)
    org = res.scalars().first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization profile not found for this workspace",
        )

    if payload.legal_name is not None:
        org.legal_name = payload.legal_name.strip()
    if payload.domain is not None:
        org.domain = payload.domain.strip() if payload.domain else None
    if payload.tax_id is not None:
        org.tax_id = payload.tax_id.strip() if payload.tax_id else None
    if payload.logo_url is not None:
        org.logo_url = payload.logo_url.strip() if payload.logo_url else None

    await db.flush()

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="organization.update",
        resource_type="organization",
        resource_id=org.tenant_id,
        actor_id=current_user.id,
        details={"legal_name": org.legal_name},
    )

    return OrganizationResponse(
        tenant_id=org.tenant_id,
        legal_name=org.legal_name,
        domain=org.domain,
        tax_id=org.tax_id,
        logo_url=org.logo_url,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )
