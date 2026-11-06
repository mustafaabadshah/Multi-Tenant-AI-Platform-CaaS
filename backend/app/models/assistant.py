import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.tenant import Tenant


class Assistant(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "assistants"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_assistant_tenant_slug"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    default_model: Mapped[str] = mapped_column(String(100), default="auto", nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="assistants")
    versions: Mapped[list["AssistantVersion"]] = relationship(
        "AssistantVersion", back_populates="assistant", cascade="all, delete-orphan"
    )
    prompts: Mapped[list["AssistantPrompt"]] = relationship(
        "AssistantPrompt", back_populates="assistant", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="assistant", cascade="all, delete-orphan"
    )


class AssistantVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assistant_versions"

    assistant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_num: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    assistant: Mapped["Assistant"] = relationship("Assistant", back_populates="versions")


class AssistantPrompt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assistant_prompts"

    assistant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt_type: Mapped[str] = mapped_column(String(50), default="SYSTEM", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    assistant: Mapped["Assistant"] = relationship("Assistant", back_populates="prompts")


class AssistantMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "assistant_memberships"

    assistant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=True,
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employee_groups.id", ondelete="CASCADE"),
        nullable=True,
    )
