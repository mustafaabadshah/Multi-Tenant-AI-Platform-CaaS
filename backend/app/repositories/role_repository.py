import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import ROLE_PERMISSIONS_MAP, PermissionName, SystemRole
from app.models.role import Permission, Role, RolePermission


class RoleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        stmt = select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_name(self, name: str) -> Role | None:
        stmt = select(Role).options(selectinload(Role.permissions)).where(Role.name == name)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_roles(self) -> Sequence[Role]:
        stmt = select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_permissions(self) -> Sequence[Permission]:
        stmt = select(Permission).order_by(Permission.category, Permission.name)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def seed_system_roles_and_permissions(self) -> None:
        """Seed all system roles and permissions if they don't already exist."""
        # 1. Seed Permissions
        permission_objs: dict[str, Permission] = {}
        for perm in PermissionName:
            stmt = select(Permission).where(Permission.name == perm.value)
            res = await self.session.execute(stmt)
            existing_perm = res.scalars().first()
            if not existing_perm:
                category = perm.value.split(".")[0]
                new_perm = Permission(
                    name=perm.value,
                    category=category,
                    description=f"Allows {perm.value.replace('.', ' ')} operations",
                )
                self.session.add(new_perm)
                await self.session.flush()
                permission_objs[perm.value] = new_perm
            else:
                permission_objs[perm.value] = existing_perm

        # 2. Seed Roles
        role_display_names = {
            SystemRole.PLATFORM_SUPERADMIN: "Platform Superadmin",
            SystemRole.TENANT_OWNER: "Tenant Owner",
            SystemRole.ORG_ADMIN: "Organization Admin",
            SystemRole.DEPT_ADMIN: "Department Admin",
            SystemRole.ASSISTANT_MANAGER: "Assistant Manager",
            SystemRole.KNOWLEDGE_EDITOR: "Knowledge Editor",
            SystemRole.EMPLOYEE: "Employee",
            SystemRole.VIEWER: "Viewer",
        }

        for role_enum in SystemRole:
            stmt = select(Role).where(Role.name == role_enum.value)
            res = await self.session.execute(stmt)
            existing_role = res.scalars().first()
            if not existing_role:
                disp = role_display_names.get(role_enum, role_enum.value)
                target_role = Role(
                    name=role_enum.value,
                    display_name=disp,
                    description=f"System role: {disp}",
                    is_system=True,
                )
                self.session.add(target_role)
                await self.session.flush()
            else:
                target_role = existing_role

            # Map permissions directly via RolePermission junction
            assigned_perms = ROLE_PERMISSIONS_MAP.get(role_enum, [])
            for perm_name in assigned_perms:
                perm_obj = permission_objs.get(perm_name.value)
                if perm_obj:
                    link_stmt = select(RolePermission).where(
                        RolePermission.role_id == target_role.id,
                        RolePermission.permission_id == perm_obj.id,
                    )
                    link_res = await self.session.execute(link_stmt)
                    if not link_res.scalars().first():
                        self.session.add(
                            RolePermission(
                                role_id=target_role.id,
                                permission_id=perm_obj.id,
                            )
                        )

        await self.session.flush()
