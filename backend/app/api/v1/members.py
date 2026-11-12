import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    TenantContext,
    get_current_user,
    require_permission,
)
from app.core.constants import MembershipStatus, PermissionName, SystemRole
from app.core.security import hash_password
from app.database.session import get_db
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.member_repository import MemberRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.member import MemberInviteRequest, MemberResponse, MemberUpdateRequest
from app.services.invitation_service import InvitationService

router = APIRouter(prefix="/members", tags=["Members & Employees"])


@router.get("", response_model=list[MemberResponse])
async def list_members(
    ctx: TenantContext = Depends(require_permission(PermissionName.MEMBER_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[MemberResponse]:
    member_repo = MemberRepository(db, ctx.tenant.id)
    members = await member_repo.list_members()

    return [
        MemberResponse(
            id=m.id,
            tenant_id=m.tenant_id,
            user_id=m.user_id,
            email=m.user.email,
            full_name=m.user.full_name,
            role=m.role.name,
            department_id=m.department_id,
            department_name=m.department.name if m.department else None,
            title=m.title,
            status=m.status,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in members
    ]


@router.post("/invite", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    payload: MemberInviteRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.MEMBER_INVITE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)
    dept_repo = DepartmentRepository(db, ctx.tenant.id)
    member_repo = MemberRepository(db, ctx.tenant.id)

    # Resolve target role
    role = await role_repo.get_by_name(payload.role)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{payload.role}' does not exist",
        )

    # Restrict owner and superadmin assignment
    if payload.role in (SystemRole.TENANT_OWNER.value, SystemRole.PLATFORM_SUPERADMIN.value) and not ctx.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owners can assign owner privileges",
        )

    # Validate department if provided
    if payload.department_id:
        dept = await dept_repo.get_by_id(payload.department_id)
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department not found in active workspace",
            )

    # Check if target user exists or create account
    user = await user_repo.get_by_email(payload.email)
    newly_created_user = False
    if not user:
        # Create a new user with placeholder temporary password
        temp_pwd = hash_password(str(uuid.uuid4()))
        name_from_email = payload.email.split("@")[0].replace(".", " ").title()
        user = await user_repo.create(
            email=payload.email,
            hashed_password=temp_pwd,
            full_name=name_from_email,
        )
        newly_created_user = True

    # Check if already a member in this tenant
    existing_membership = await member_repo.get_by_user_id(user.id)
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user is already a member of this workspace.",
        )

    # Create membership
    membership = await member_repo.create(
        user_id=user.id,
        role_id=role.id,
        department_id=payload.department_id,
        title=payload.title,
        status=MembershipStatus.ACTIVE.value,
    )

    invitation = None
    invitation_raw_token = None
    if newly_created_user:
        invitation_service = InvitationService(db)
        invitation, invitation_raw_token = await invitation_service.create_invitation(
            tenant_id=ctx.tenant.id,
            email=user.email,
            role_id=role.id,
            department_id=payload.department_id,
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="member.invite",
        resource_type="member",
        resource_id=membership.id,
        actor_id=current_user.id,
        details={"email": user.email, "role": role.name},
    )

    # Reload membership with relations
    fresh_member = await member_repo.get_by_id(membership.id)
    assert fresh_member is not None

    return MemberResponse(
        id=fresh_member.id,
        tenant_id=fresh_member.tenant_id,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=role.name,
        department_id=fresh_member.department_id,
        department_name=fresh_member.department.name if fresh_member.department else None,
        title=fresh_member.title,
        status=fresh_member.status,
        created_at=fresh_member.created_at,
        updated_at=fresh_member.updated_at,
        invitation_token=invitation_raw_token,
        invitation_expires_at=invitation.expires_at if invitation else None,
    )


@router.patch("/{member_id}", response_model=MemberResponse)
async def update_member(
    member_id: uuid.UUID,
    payload: MemberUpdateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.MEMBER_UPDATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    member_repo = MemberRepository(db, ctx.tenant.id)
    role_repo = RoleRepository(db)
    dept_repo = DepartmentRepository(db, ctx.tenant.id)

    target_member = await member_repo.get_by_id(member_id)
    if not target_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in active workspace",
        )

    # Prevent self-role modification
    if target_member.user_id == current_user.id and payload.role and payload.role != target_member.role.name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Users cannot modify their own role",
        )

    new_role_id = None
    if payload.role:
        if payload.role in (SystemRole.TENANT_OWNER.value, SystemRole.PLATFORM_SUPERADMIN.value) and not ctx.is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only workspace owners can assign owner privileges",
            )
        role_obj = await role_repo.get_by_name(payload.role)
        if not role_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{payload.role}' does not exist",
            )
        new_role_id = role_obj.id

    if payload.department_id:
        dept = await dept_repo.get_by_id(payload.department_id)
        if not dept:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department not found in active workspace",
            )

    updated = await member_repo.update_member(
        membership_id=member_id,
        role_id=new_role_id,
        department_id=payload.department_id,
        title=payload.title,
        status=payload.status,
    )
    assert updated is not None

    # Reload with relations
    fresh = await member_repo.get_by_id(member_id)
    assert fresh is not None

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="member.update",
        resource_type="member",
        resource_id=member_id,
        actor_id=current_user.id,
        details={"updated_fields": payload.model_dump(exclude_unset=True)},
    )

    return MemberResponse(
        id=fresh.id,
        tenant_id=fresh.tenant_id,
        user_id=fresh.user_id,
        email=fresh.user.email,
        full_name=fresh.user.full_name,
        role=fresh.role.name,
        department_id=fresh.department_id,
        department_name=fresh.department.name if fresh.department else None,
        title=fresh.title,
        status=fresh.status,
        created_at=fresh.created_at,
        updated_at=fresh.updated_at,
    )


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.MEMBER_REMOVE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    member_repo = MemberRepository(db, ctx.tenant.id)
    target = await member_repo.get_by_id(member_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in active workspace",
        )

    # Prevent owner from removing themselves if they are the only owner
    if target.role.name == SystemRole.TENANT_OWNER.value and target.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant owner cannot remove themselves from their workspace",
        )

    await member_repo.delete(member_id)

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="member.remove",
        resource_type="member",
        resource_id=member_id,
        actor_id=current_user.id,
    )
