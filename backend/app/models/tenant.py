from typing import TYPE_CHECKING

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import TenantStatus, TenantType
from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.administration import AuditLog, TenantQuota
    from app.models.assistant import Assistant
    from app.models.department import Department
    from app.models.group import EmployeeGroup
    from app.models.knowledge import KnowledgeBase
    from app.models.membership import TenantMembership
    from app.models.organization import Organization


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    type: Mapped[str] = mapped_column(
        String(50), default=TenantType.INDIVIDUAL.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default=TenantStatus.ACTIVE.value, nullable=False
    )
    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    organization: Mapped["Organization | None"] = relationship(
        "Organization", back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    memberships: Mapped[list["TenantMembership"]] = relationship(
        "TenantMembership", back_populates="tenant", cascade="all, delete-orphan"
    )
    departments: Mapped[list["Department"]] = relationship(
        "Department", back_populates="tenant", cascade="all, delete-orphan"
    )
    groups: Mapped[list["EmployeeGroup"]] = relationship(
        "EmployeeGroup", back_populates="tenant", cascade="all, delete-orphan"
    )
    assistants: Mapped[list["Assistant"]] = relationship(
        "Assistant", back_populates="tenant", cascade="all, delete-orphan"
    )
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        "KnowledgeBase", back_populates="tenant", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="tenant", cascade="all, delete-orphan"
    )
    quota: Mapped["TenantQuota | None"] = relationship(
        "TenantQuota", back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
