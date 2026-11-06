import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import MembershipStatus, UserStatus
from app.core.security import decode_token
from app.database.session import get_db
from app.models.membership import TenantMembership
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.tenant_repository import TenantRepository
from app.repositories.user_repository import UserRepository

security = HTTPBearer(auto_error=False)


@dataclass
class TenantContext:
    tenant: Tenant
    membership: TenantMembership
    role: Role
    permissions: set[str]


async def get_current_user(
    auth: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(auth.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed user ID in token",
        )

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if user.status != UserStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or suspended",
        )

    return user


async def get_current_tenant_context(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header is required for this tenant-scoped operation",
        )

    try:
        tenant_uuid = uuid.UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Tenant-ID format, must be a valid UUID",
        )

    tenant_repo = TenantRepository(db)
    tenant = await tenant_repo.get_by_id(tenant_uuid)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Superuser bypass for platform maintenance if explicitly configured
    if current_user.is_superuser:
        # Fetch membership or synthesize superuser context
        membership = await tenant_repo.get_membership(current_user.id, tenant_uuid)
        if membership:
            role = membership.role
            perms = {p.name for p in role.permissions}
        else:
            # Grant all permissions for superadmin
            perms = {"*"}
            # Return context with fallback
            from app.core.constants import SystemRole
            from app.models.role import Role

            dummy_role = Role(
                name=SystemRole.PLATFORM_SUPERADMIN.value, display_name="Superuser", is_system=True
            )
            membership = TenantMembership(
                user_id=current_user.id,
                tenant_id=tenant.id,
                role_id=uuid.uuid4(),
                title="Superuser",
            )
            return TenantContext(
                tenant=tenant, membership=membership, role=dummy_role, permissions=perms
            )
        return TenantContext(tenant=tenant, membership=membership, role=role, permissions=perms)

    # Verify membership
    membership = await tenant_repo.get_membership(current_user.id, tenant_uuid)
    if not membership or membership.status != MembershipStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not have active membership in this workspace",
        )

    role = membership.role
    perms = {p.name for p in role.permissions}

    return TenantContext(
        tenant=tenant,
        membership=membership,
        role=role,
        permissions=perms,
    )


def require_permission(required_perm: str) -> Callable:
    """Dependency factory checking that active tenant context possesses the required permission."""

    async def permission_checker(
        ctx: TenantContext = Depends(get_current_tenant_context),
    ) -> TenantContext:
        if "*" in ctx.permissions or required_perm in ctx.permissions:
            return ctx
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions: requires '{required_perm}'",
        )

    return permission_checker
