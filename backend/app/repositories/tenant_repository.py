import re
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import MembershipStatus, TenantStatus, TenantType
from app.models.administration import TenantQuota
from app.models.membership import TenantMembership
from app.models.organization import Organization
from app.models.role import Role
from app.models.tenant import Tenant


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", slug)


class TenantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        stmt = (
            select(Tenant)
            .options(selectinload(Tenant.organization), selectinload(Tenant.quota))
            .where(Tenant.id == tenant_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = (
            select(Tenant)
            .options(selectinload(Tenant.organization), selectinload(Tenant.quota))
            .where(Tenant.slug == slug)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_tenant(
        self,
        name: str,
        tenant_type: TenantType,
        owner_id: uuid.UUID,
        owner_role: Role,
        slug: str | None = None,
        legal_name: str | None = None,
        domain: str | None = None,
    ) -> tuple[Tenant, TenantMembership]:
        # Generate slug if not provided
        base_slug = slug or slugify(name)
        candidate_slug = base_slug
        count = 1
        while await self.get_by_slug(candidate_slug) is not None:
            candidate_slug = f"{base_slug}-{count}"
            count += 1

        tenant = Tenant(
            name=name,
            slug=candidate_slug,
            type=tenant_type.value,
            status=TenantStatus.ACTIVE.value,
            settings={},
        )
        self.session.add(tenant)
        await self.session.flush()

        # If organization, create organization metadata
        if tenant_type == TenantType.ORGANIZATION:
            org = Organization(
                tenant_id=tenant.id,
                legal_name=legal_name or name,
                domain=domain,
            )
            self.session.add(org)

        # Create default tenant quota
        quota = TenantQuota(
            tenant_id=tenant.id,
            max_users=50 if tenant_type == TenantType.ORGANIZATION else 1,
            max_assistants=10 if tenant_type == TenantType.ORGANIZATION else 3,
        )
        self.session.add(quota)

        # Create owner membership
        membership = TenantMembership(
            user_id=owner_id,
            tenant_id=tenant.id,
            role_id=owner_role.id,
            title="Owner",
            status=MembershipStatus.ACTIVE.value,
        )
        self.session.add(membership)
        await self.session.flush()

        return tenant, membership

    async def get_user_tenants(
        self, user_id: uuid.UUID
    ) -> Sequence[tuple[Tenant, TenantMembership, Role]]:
        stmt = (
            select(Tenant, TenantMembership, Role)
            .join(TenantMembership, Tenant.id == TenantMembership.tenant_id)
            .join(Role, TenantMembership.role_id == Role.id)
            .where(
                TenantMembership.user_id == user_id,
                TenantMembership.status == MembershipStatus.ACTIVE.value,
                Tenant.status == TenantStatus.ACTIVE.value,
            )
        )
        result = await self.session.execute(stmt)
        return result.all()  # type: ignore[return-value]

    async def get_membership(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> TenantMembership | None:
        stmt = (
            select(TenantMembership)
            .options(selectinload(TenantMembership.role).selectinload(Role.permissions))
            .where(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id == tenant_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
