"""Database models for MCP Connections, Human-in-the-Loop Tool Approvals, and Tool Invocation Logs."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assistant import Assistant
    from app.models.conversation import Conversation
    from app.models.tenant import Tenant
    from app.models.user import User


JSONType = JSON().with_variant(JSONB, "postgresql")


class MCPConnection(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Tenant-scoped external Model Context Protocol (MCP) server connection."""

    __tablename__ = "mcp_connections"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    server_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    auth_mode: Mapped[str] = mapped_column(String(50), default="NONE", nullable=False)  # NONE, BEARER_TOKEN, OAUTH
    encrypted_credential: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    connection_status: Mapped[str] = mapped_column(String(50), default="CONNECTED", nullable=False)  # CONNECTED, DISCONNECTED, ERROR
    server_capabilities: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    approved_tools: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped[Optional["User"]] = relationship("User")


class ToolApproval(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Human-in-the-loop pending approval record for high-risk or mutating tool executions."""

    __tablename__ = "tool_approvals"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assistant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)  # PENDING, APPROVED, DENIED, EXPIRED, CONSUMED
    approval_token: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    conversation: Mapped["Conversation"] = relationship("Conversation")
    assistant: Mapped["Assistant"] = relationship("Assistant")
    user: Mapped["User"] = relationship("User")


class ToolInvocationLog(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Audit and Observability log for tool executions."""

    __tablename__ = "tool_invocation_logs"

    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assistant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("assistants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trace_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    tool_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_type: Mapped[str] = mapped_column(String(50), nullable=False)  # BUILTIN, CUSTOM_HTTP, MCP
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # SUCCESS, FAILED, DENIED, APPROVAL_REQUIRED
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
