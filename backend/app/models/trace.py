import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assistant import Assistant
    from app.models.conversation import Conversation
    from app.models.tenant import Tenant


class RequestTrace(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Durable request-level trace for AI assistant inference, retrieval, and streaming."""

    __tablename__ = "request_traces"
    __table_args__ = (
        Index("ix_request_traces_tenant_created", "tenant_id", "created_at"),
        Index("ix_request_traces_tenant_status", "tenant_id", "status"),
        Index("ix_request_traces_tenant_assistant", "tenant_id", "assistant_id"),
        Index("ix_request_traces_tenant_traffic", "tenant_id", "traffic_type"),
    )

    trace_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    assistant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("assistants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assistant_name: Mapped[str] = mapped_column(String(100), default="Assistant", nullable=False)
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    traffic_type: Mapped[str] = mapped_column(String(50), default="internal", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING", nullable=False, index=True)
    error_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    credential_source: Mapped[str] = mapped_column(String(50), default="byok", nullable=False)
    retrieval_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    retrieved_chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    citation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_token_estimated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    estimated_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pricing_status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)

    total_duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ttft_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    spans_data: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    retrieval_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    input_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_preview: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    assistant: Mapped[Optional["Assistant"]] = relationship("Assistant")
    conversation: Mapped[Optional["Conversation"]] = relationship("Conversation")


class ObservabilityPolicy(Base, TimestampMixin):
    """Tenant-level observability configuration for I/O previews and data retention."""

    __tablename__ = "observability_policies"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    capture_mode: Mapped[str] = mapped_column(String(20), default="METADATA_ONLY", nullable=False)
    max_preview_length: Mapped[int] = mapped_column(Integer, default=250, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
