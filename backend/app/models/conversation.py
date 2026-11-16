import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assistant import Assistant


class Conversation(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    assistant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assistants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), default="New Conversation", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)

    # Relationships
    assistant: Mapped["Assistant"] = relationship("Assistant", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["ConversationAttachment"]] = relationship(
        "ConversationAttachment", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_type: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    attachments: Mapped[list["MessageAttachment"]] = relationship(
        "MessageAttachment", back_populates="message", cascade="all, delete-orphan"
    )
    citations: Mapped[list["MessageCitation"]] = relationship(
        "MessageCitation", back_populates="message", cascade="all, delete-orphan"
    )


class MessageAttachment(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "message_attachments"

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    message: Mapped["Message"] = relationship("Message", back_populates="attachments")


class MessageCitation(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    __tablename__ = "message_citations"

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    citation_num: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    citation_text: Mapped[str] = mapped_column(Text, nullable=False)

    message: Mapped["Message"] = relationship("Message", back_populates="citations")


class ConversationAttachment(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Uploaded document attached to a conversation with extraction and promotion lifecycle."""

    __tablename__ = "conversation_attachments"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    uploader_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="UPLOADED", nullable=False, index=True)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_pages: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_promoted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    promoted_knowledge_base_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    promoted_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="attachments")
    chunks: Mapped[list["ConversationAttachmentChunk"]] = relationship(
        "ConversationAttachmentChunk",
        back_populates="attachment",
        cascade="all, delete-orphan",
        order_by="ConversationAttachmentChunk.chunk_index.asc()",
    )


class ConversationAttachmentChunk(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Searchable text chunk extracted from a conversation attachment."""

    __tablename__ = "conversation_attachment_chunks"

    attachment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversation_attachments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    attachment: Mapped["ConversationAttachment"] = relationship("ConversationAttachment", back_populates="chunks")


class VoicePreference(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """User voice preference for STT/TTS interaction modes."""

    __tablename__ = "voice_preferences"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_voice_pref_tenant_user"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    voice_mode: Mapped[str] = mapped_column(String(50), default="TEXT", nullable=False)  # TEXT, DICTATION, LISTEN, VOICE_CONVERSATION
    auto_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    speech_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    preferred_voice: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(20), default="en-US", nullable=False)


