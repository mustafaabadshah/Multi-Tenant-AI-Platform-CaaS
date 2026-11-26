import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    TenantContext,
    get_current_user,
    require_permission,
)
from app.core.constants import PermissionName
from app.database.session import get_db
from app.models.user import User
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.group_repository import GroupRepository
from app.schemas.group import (
    AddGroupMemberRequest,
    EmployeeGroupCreateRequest,
    EmployeeGroupResponse,
    GroupMemberResponse,
)


router = APIRouter(prefix="/groups", tags=["Employee Groups"])


@router.get("", response_model=list[EmployeeGroupResponse])
async def list_groups(
    ctx: TenantContext = Depends(require_permission(PermissionName.GROUP_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[EmployeeGroupResponse]:
    group_repo = GroupRepository(db, ctx.tenant.id)
    items = await group_repo.list_with_member_counts()

    return [
        EmployeeGroupResponse(
            id=g.id,
            tenant_id=g.tenant_id,
            department_id=g.department_id,
            name=g.name,
            description=g.description,
            member_count=count,
            created_at=g.created_at,
            updated_at=g.updated_at,
        )
        for g, count in items
    ]


@router.post("", response_model=EmployeeGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: EmployeeGroupCreateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.GROUP_CREATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmployeeGroupResponse:
    group_repo = GroupRepository(db, ctx.tenant.id)

    existing = await group_repo.get_by_name(payload.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An employee group named '{payload.name}' already exists in this workspace.",
        )

    group = await group_repo.create(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        department_id=payload.department_id,
    )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="group.create",
        resource_type="group",
        resource_id=group.id,
        actor_id=current_user.id,
        details={"name": group.name},
    )

    return EmployeeGroupResponse(
        id=group.id,
        tenant_id=group.tenant_id,
        department_id=group.department_id,
        name=group.name,
        description=group.description,
        member_count=0,
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.GROUP_DELETE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    group_repo = GroupRepository(db, ctx.tenant.id)
    deleted = await group_repo.delete(group_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee group not found in active workspace",
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="group.delete",
        resource_type="group",
        resource_id=group_id,
        actor_id=current_user.id,
    )


@router.get("/{group_id}/members", response_model=list[GroupMemberResponse])
async def list_group_members(
    group_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.GROUP_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[GroupMemberResponse]:
    group_repo = GroupRepository(db, ctx.tenant.id)
    group = await group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee group not found in active workspace",
        )

    rows = await group_repo.list_members(group_id)
    return [
        GroupMemberResponse(
            id=enrollment.id,
            group_id=enrollment.group_id,
            membership_id=enrollment.membership_id,
            user_id=user.id,
            user_name=user.full_name,
            user_email=user.email,
            title=membership.title,
            created_at=enrollment.created_at,
        )
        for enrollment, membership, user in rows
    ]


@router.post(
    "/{group_id}/members",
    response_model=GroupMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_group_member(
    group_id: uuid.UUID,
    payload: AddGroupMemberRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.GROUP_UPDATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupMemberResponse:
    group_repo = GroupRepository(db, ctx.tenant.id)
    try:
        enrollment = await group_repo.add_member(group_id, payload.membership_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="group.member_add",
        resource_type="group",
        resource_id=group_id,
        actor_id=current_user.id,
        details={"membership_id": str(payload.membership_id)},
    )

    rows = await group_repo.list_members(group_id)
    for enr, mem, usr in rows:
        if enr.id == enrollment.id:
            return GroupMemberResponse(
                id=enr.id,
                group_id=enr.group_id,
                membership_id=enr.membership_id,
                user_id=usr.id,
                user_name=usr.full_name,
                user_email=usr.email,
                title=mem.title,
                created_at=enr.created_at,
            )

    return GroupMemberResponse(
        id=enrollment.id,
        group_id=enrollment.group_id,
        membership_id=enrollment.membership_id,
        user_id=current_user.id,
        created_at=enrollment.created_at,
    )


@router.delete("/{group_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_member(
    group_id: uuid.UUID,
    membership_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.GROUP_UPDATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    group_repo = GroupRepository(db, ctx.tenant.id)
    removed = await group_repo.remove_member(group_id, membership_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member enrollment not found in this employee group",
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="group.member_remove",
        resource_type="group",
        resource_id=group_id,
        actor_id=current_user.id,
        details={"membership_id": str(membership_id)},
    )

