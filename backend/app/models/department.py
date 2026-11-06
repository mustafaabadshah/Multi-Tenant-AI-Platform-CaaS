from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.group import EmployeeGroup
    from app.models.membership import TenantMembership
    from app.models.tenant import Tenant


class Department(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_department_tenant_name"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="departments")
    members: Mapped[list["TenantMembership"]] = relationship(
        "TenantMembership", back_populates="department"
    )
    groups: Mapped[list["EmployeeGroup"]] = relationship(
        "EmployeeGroup", back_populates="department"
    )
