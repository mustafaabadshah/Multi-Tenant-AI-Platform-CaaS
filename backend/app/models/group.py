import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.membership import TenantMembership
    from app.models.tenant import Tenant


class EmployeeGroup(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "employee_groups"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_group_tenant_name"),)

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="groups")
    department: Mapped["Department | None"] = relationship("Department", back_populates="groups")
    memberships: Mapped[list["GroupMembership"]] = relationship(
        "GroupMembership", back_populates="group", cascade="all, delete-orphan"
    )


class GroupMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "group_memberships"
    __table_args__ = (UniqueConstraint("group_id", "membership_id", name="uq_group_membership"),)

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employee_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant_memberships.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    group: Mapped["EmployeeGroup"] = relationship("EmployeeGroup", back_populates="memberships")
    membership: Mapped["TenantMembership"] = relationship(
        "TenantMembership", back_populates="group_enrollments"
    )
