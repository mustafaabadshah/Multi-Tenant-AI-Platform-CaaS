import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    TenantContext,
    get_current_user,
    require_permission,
)
from app.core.config import settings
from app.core.constants import PermissionName, SystemRole
from app.core.security import create_access_token, create_refresh_token
from app.database.session import get_db
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.tenant_repository import TenantRepository
from app.schemas.auth import TokenResponse, WorkspaceSummary
from app.schemas.tenant import TenantCreateRequest, TenantResponse, TenantUpdateRequest

router = APIRouter(prefix="/tenants", tags=["Workspaces & Tenants"])


@router.get("", response_model=list[WorkspaceSummary])
async def list_user_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceSummary]:
    tenant_repo = TenantRepository(db)
    user_tenants = await tenant_repo.get_user_tenants(current_user.id)

    return [
        WorkspaceSummary(
            tenant_id=t.id,
            tenant_name=t.name,
            tenant_slug=t.slug,
            tenant_type=t.type,
            role=r.name,
        )
        for t, m, r in user_tenants
    ]


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: TenantCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    tenant_repo = TenantRepository(db)
    role_repo = RoleRepository(db)

    owner_role = await role_repo.get_by_name(SystemRole.TENANT_OWNER.value)
    if not owner_role:
        await role_repo.seed_system_roles_and_permissions()
        owner_role = await role_repo.get_by_name(SystemRole.TENANT_OWNER.value)

    tenant, _ = await tenant_repo.create_tenant(
        name=payload.name,
        tenant_type=payload.type,
        owner_id=current_user.id,
        owner_role=owner_role,  # type: ignore[arg-type]
        slug=payload.slug,
        legal_name=payload.legal_name,
        domain=payload.domain,
    )

    # Log audit event
    audit_repo = AuditLogRepository(db, tenant.id)
    await audit_repo.log_event(
        action="tenant.create",
        resource_type="tenant",
        resource_id=tenant.id,
        actor_id=current_user.id,
        details={"name": tenant.name, "type": tenant.type},
    )

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        type=tenant.type,
        status=tenant.status,
        settings=tenant.settings,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_workspace(
    tenant_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.TENANT_READ.value)),
) -> TenantResponse:
    if tenant_id != ctx.tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Path workspace ID does not match active X-Tenant-ID context",
        )
    # TenantContext already guarantees the user has active membership in this tenant
    tenant = ctx.tenant
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        type=tenant.type,
        status=tenant.status,
        settings=tenant.settings,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_workspace(
    tenant_id: uuid.UUID,
    payload: TenantUpdateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.TENANT_UPDATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    if tenant_id != ctx.tenant.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Path workspace ID does not match active X-Tenant-ID context",
        )
    tenant = ctx.tenant

    if payload.name is not None and payload.name.strip():
        tenant.name = payload.name.strip()
    if payload.settings is not None:
        tenant.settings = payload.settings

    await db.flush()

    audit_repo = AuditLogRepository(db, tenant.id)
    await audit_repo.log_event(
        action="tenant.update",
        resource_type="tenant",
        resource_id=tenant.id,
        actor_id=current_user.id,
        details={"name": tenant.name},
    )

    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        type=tenant.type,
        status=tenant.status,
        settings=tenant.settings,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
    )


@router.post("/{tenant_id}/switch", response_model=TokenResponse)
async def switch_workspace(
    tenant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    tenant_repo = TenantRepository(db)
    membership = await tenant_repo.get_membership(current_user.id, tenant_id)
    if not membership and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this workspace",
        )

    # Issue new access token scoped to the switched tenant
    access_token = create_access_token(
        subject=str(current_user.id),
        claims={"email": current_user.email, "tenant_id": str(tenant_id)},
    )
    refresh_token = create_refresh_token(subject=str(current_user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
