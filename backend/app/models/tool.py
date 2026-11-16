"""SQLAlchemy 2.0 model for the Tool Registry (Built-in, Custom HTTP, and MCP tools)."""

import uuid
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User


class Tool(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """First-class registered tool available to AI assistants and agentic execution runtimes."""

    __tablename__ = "tools"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tool_tenant_name"),
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    namespace: Mapped[str] = mapped_column(String(50), default="default", nullable=False)
    tool_type: Mapped[str] = mapped_column(
        String(30), default="CUSTOM_HTTP", nullable=False, index=True
    )  # BUILTIN, CUSTOM_HTTP, MCP
    risk_level: Mapped[str] = mapped_column(
        String(20), default="READ_ONLY", nullable=False
    )  # READ_ONLY, WRITE, HIGH_RISK
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    http_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    max_response_bytes: Mapped[int] = mapped_column(Integer, default=1048576, nullable=False)  # 1MB limit

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    owner: Mapped[Optional["User"]] = relationship("User")
