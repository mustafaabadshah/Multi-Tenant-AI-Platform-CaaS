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
from app.repositories.department_repository import DepartmentRepository
from app.schemas.department import (
    DepartmentCreateRequest,
    DepartmentResponse,
    DepartmentUpdateRequest,
)

router = APIRouter(prefix="/departments", tags=["Departments"])


@router.get("", response_model=list[DepartmentResponse])
async def list_departments(
    ctx: TenantContext = Depends(require_permission(PermissionName.DEPARTMENT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> list[DepartmentResponse]:
    dept_repo = DepartmentRepository(db, ctx.tenant.id)
    items = await dept_repo.list_with_member_counts()

    return [
        DepartmentResponse(
            id=d.id,
            tenant_id=d.tenant_id,
            name=d.name,
            description=d.description,
            member_count=count,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d, count in items
    ]


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentCreateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.DEPARTMENT_CREATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DepartmentResponse:
    dept_repo = DepartmentRepository(db, ctx.tenant.id)

    # Check duplicate name within this tenant
    existing = await dept_repo.get_by_name(payload.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A department named '{payload.name}' already exists in this workspace.",
        )

    dept = await dept_repo.create(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
    )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="department.create",
        resource_type="department",
        resource_id=dept.id,
        actor_id=current_user.id,
        details={"name": dept.name},
    )

    return DepartmentResponse(
        id=dept.id,
        tenant_id=dept.tenant_id,
        name=dept.name,
        description=dept.description,
        member_count=0,
        created_at=dept.created_at,
        updated_at=dept.updated_at,
    )


@router.get("/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.DEPARTMENT_READ.value)),
    db: AsyncSession = Depends(get_db),
) -> DepartmentResponse:
    dept_repo = DepartmentRepository(db, ctx.tenant.id)
    dept = await dept_repo.get_by_id(department_id)
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found in active workspace",
        )

    return DepartmentResponse(
        id=dept.id,
        tenant_id=dept.tenant_id,
        name=dept.name,
        description=dept.description,
        member_count=0,
        created_at=dept.created_at,
        updated_at=dept.updated_at,
    )


@router.patch("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdateRequest,
    ctx: TenantContext = Depends(require_permission(PermissionName.DEPARTMENT_UPDATE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DepartmentResponse:
    dept_repo = DepartmentRepository(db, ctx.tenant.id)
    dept = await dept_repo.get_by_id(department_id)
    if not dept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found in active workspace",
        )

    if payload.name and payload.name.lower().strip() != dept.name.lower():
        existing = await dept_repo.get_by_name(payload.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A department named '{payload.name}' already exists in this workspace.",
            )

    updated = await dept_repo.update(
        department_id=department_id,
        name=payload.name,
        description=payload.description,
    )
    assert updated is not None

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="department.update",
        resource_type="department",
        resource_id=updated.id,
        actor_id=current_user.id,
        details={"name": updated.name},
    )

    return DepartmentResponse(
        id=updated.id,
        tenant_id=updated.tenant_id,
        name=updated.name,
        description=updated.description,
        member_count=0,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(PermissionName.DEPARTMENT_DELETE.value)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    dept_repo = DepartmentRepository(db, ctx.tenant.id)
    deleted = await dept_repo.delete(department_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found in active workspace",
        )

    audit_repo = AuditLogRepository(db, ctx.tenant.id)
    await audit_repo.log_event(
        action="department.delete",
        resource_type="department",
        resource_id=department_id,
        actor_id=current_user.id,
    )
