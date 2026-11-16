import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuthSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Server-side authentication session for refresh token rotation, replay detection, and revocation."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_user_revoked", "user_id", "is_revoked"),
        Index("ix_auth_sessions_token_hash", "refresh_token_hash"),
        Index("ix_auth_sessions_family", "session_family_id"),
        Index("ix_auth_sessions_prev_token_hash", "previous_refresh_token_hash"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    previous_refresh_token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    session_family_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, nullable=False, index=True)

    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="auth_sessions")
