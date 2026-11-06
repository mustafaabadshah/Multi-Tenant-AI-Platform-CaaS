from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.schemas.role import PermissionResponse, RoleResponse

router = APIRouter(tags=["Roles & Permissions"])


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RoleResponse]:
    role_repo = RoleRepository(db)
    roles = await role_repo.list_roles()

    return [
        RoleResponse(
            id=r.id,
            name=r.name,
            display_name=r.display_name,
            description=r.description,
            is_system=r.is_system,
            permissions=[
                PermissionResponse(
                    id=p.id,
                    name=p.name,
                    category=p.category,
                    description=p.description,
                )
                for p in r.permissions
            ],
        )
        for r in roles
    ]


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PermissionResponse]:
    role_repo = RoleRepository(db)
    perms = await role_repo.list_permissions()

    return [
        PermissionResponse(
            id=p.id,
            name=p.name,
            category=p.category,
            description=p.description,
        )
        for p in perms
    ]
