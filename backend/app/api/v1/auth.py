import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.constants import SystemRole, TenantType
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.database.session import get_db
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    WorkspaceSummary,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    role_repo = RoleRepository(db)

    # Ensure system roles are seeded
    await role_repo.seed_system_roles_and_permissions()

    # Check existing user
    existing = await user_repo.get_by_email(payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    # Create User
    hashed_pwd = hash_password(payload.password)
    user = await user_repo.create(
        email=payload.email,
        hashed_password=hashed_pwd,
        full_name=payload.full_name,
    )

    owner_role = await role_repo.get_by_name(SystemRole.TENANT_OWNER.value)
    if not owner_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System roles configuration error",
        )

    # Create workspace: Organization if organization_name supplied, otherwise Individual
    if payload.organization_name and payload.organization_name.strip():
        tenant, _ = await tenant_repo.create_tenant(
            name=payload.organization_name.strip(),
            tenant_type=TenantType.ORGANIZATION,
            owner_id=user.id,
            owner_role=owner_role,
        )
    else:
        tenant, _ = await tenant_repo.create_tenant(
            name=f"{payload.full_name.strip()}'s Workspace",
            tenant_type=TenantType.INDIVIDUAL,
            owner_id=user.id,
            owner_role=owner_role,
        )

    # Issue tokens
    access_token = create_access_token(
        subject=str(user.id),
        claims={"email": user.email, "tenant_id": str(tenant.id)},
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)

    user = await user_repo.get_by_email(payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Find user's active tenant
    user_tenants = await tenant_repo.get_user_tenants(user.id)
    active_tenant_id = str(user_tenants[0][0].id) if user_tenants else None

    claims = {"email": user.email}
    if active_tenant_id:
        claims["tenant_id"] = active_tenant_id

    access_token = create_access_token(subject=str(user.id), claims=claims)
    refresh_token = create_refresh_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id_str = decoded.get("sub")
    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token",
        )

    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    user_tenants = await tenant_repo.get_user_tenants(user.id)
    active_tenant_id = str(user_tenants[0][0].id) if user_tenants else None

    claims = {"email": user.email}
    if active_tenant_id:
        claims["tenant_id"] = active_tenant_id

    access_token = create_access_token(subject=str(user.id), claims=claims)
    new_refresh = create_refresh_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    tenant_repo = TenantRepository(db)
    user_tenants = await tenant_repo.get_user_tenants(current_user.id)

    workspaces = [
        WorkspaceSummary(
            tenant_id=t.id,
            tenant_name=t.name,
            tenant_slug=t.slug,
            tenant_type=t.type,
            role=r.name,
            is_active=(idx == 0),
        )
        for idx, (t, m, r) in enumerate(user_tenants)
    ]

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        status=current_user.status,
        is_superuser=current_user.is_superuser,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        active_tenant_id=workspaces[0].tenant_id if workspaces else None,
        workspaces=workspaces,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    # In stateless JWT architecture, the client discards the token.
    # Future enhancement can store revoked JTI in Redis.
    return {"message": "Successfully logged out"}
