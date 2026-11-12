"""SQLAlchemy 2.0 models for Assistant Publishing, Embed Widgets, and Developer API Keys."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TenantScopedMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assistant import Assistant, AssistantVersion
    from app.models.conversation import Conversation
    from app.models.tenant import Tenant
    from app.models.user import User


class AssistantPublication(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Publication configuration and public web/embed distribution state for an assistant."""

    __tablename__ = "assistant_publications"

    assistant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    public_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    visibility: Mapped[str] = mapped_column(
        String(50),
        default="PRIVATE",
        nullable=False,
    )  # PRIVATE, WORKSPACE, PUBLIC
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    allowed_domains: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default="[]",
    )  # JSON-encoded array of allowed hostnames (e.g. '["example.com"]')
    custom_greeting: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    brand_color: Mapped[str] = mapped_column(
        String(20),
        default="#0284c7",
        nullable=False,
    )
    published_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("assistant_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    assistant: Mapped["Assistant"] = relationship("Assistant")
    published_version: Mapped[Optional["AssistantVersion"]] = relationship("AssistantVersion")
    creator: Mapped[Optional["User"]] = relationship("User")


class APIKey(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Scoped developer API credentials for programmatic assistant integration."""

    __tablename__ = "api_keys"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assistant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("assistants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    key_prefix: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )  # e.g. "mmaip_live_"
    key_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )  # SHA-256 hash of secret token
    scopes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default='["assistant:read", "assistant:chat"]',
    )  # JSON-encoded array of scopes
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    user: Mapped[Optional["User"]] = relationship("User")
    assistant: Mapped[Optional["Assistant"]] = relationship("Assistant")


class PublicChatSession(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Ephemeral session isolation state for public and embedded widget visitors."""

    __tablename__ = "public_chat_sessions"

    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assistant_publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_token: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    client_ip_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    publication: Mapped["AssistantPublication"] = relationship("AssistantPublication")
    conversation: Mapped[Optional["Conversation"]] = relationship("Conversation")
