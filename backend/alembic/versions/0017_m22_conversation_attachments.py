"""M22: Conversation attachments, searchable chunks, and voice preferences

Revision ID: 0017_m22_conversation_attachments
Revises: 0016_m20_2_assistant_tools_config
Create Date: 2026-11-16

Introduces:
- `conversation_attachments`: private uploaded documents attached directly to chat conversations.
- `conversation_attachment_chunks`: searchable text chunks extracted from conversation attachments for chat-scoped RAG.
- `voice_preferences`: user voice preference profiles for STT/TTS modes and playback settings.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_m22_conversation_attachments"
down_revision: str | None = "0016_m20_2_assistant_tools_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Conversation Attachments
    op.create_table(
        "conversation_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("uploader_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(50), server_default="UPLOADED", nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("total_pages", sa.Integer(), server_default="1", nullable=False),
        sa.Column("total_chunks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_promoted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("promoted_knowledge_base_id", sa.Uuid(), sa.ForeignKey("knowledge_bases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("promoted_document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversation_attachments_tenant_id", "conversation_attachments", ["tenant_id"])
    op.create_index("ix_conversation_attachments_conversation_id", "conversation_attachments", ["conversation_id"])
    op.create_index("ix_conversation_attachments_message_id", "conversation_attachments", ["message_id"])
    op.create_index("ix_conversation_attachments_uploader_user_id", "conversation_attachments", ["uploader_user_id"])
    op.create_index("ix_conversation_attachments_file_hash", "conversation_attachments", ["file_hash"])
    op.create_index("ix_conversation_attachments_status", "conversation_attachments", ["status"])
    op.create_index("ix_conversation_attachments_promoted_kb_id", "conversation_attachments", ["promoted_knowledge_base_id"])

    # 2. Conversation Attachment Chunks
    op.create_table(
        "conversation_attachment_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), sa.ForeignKey("conversation_attachments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversation_attachment_chunks_tenant_id", "conversation_attachment_chunks", ["tenant_id"])
    op.create_index("ix_conversation_attachment_chunks_attachment_id", "conversation_attachment_chunks", ["attachment_id"])
    op.create_index("ix_conversation_attachment_chunks_conversation_id", "conversation_attachment_chunks", ["conversation_id"])
    op.create_index("ix_conversation_attachment_chunks_chunk_index", "conversation_attachment_chunks", ["chunk_index"])

    # 3. Voice Preferences
    op.create_table(
        "voice_preferences",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("voice_mode", sa.String(50), server_default="TEXT", nullable=False),
        sa.Column("auto_read", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("speech_rate", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("preferred_voice", sa.String(100), nullable=True),
        sa.Column("preferred_language", sa.String(20), server_default="en-US", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_voice_pref_tenant_user"),
    )
    op.create_index("ix_voice_preferences_tenant_id", "voice_preferences", ["tenant_id"])
    op.create_index("ix_voice_preferences_user_id", "voice_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_table("voice_preferences")
    op.drop_table("conversation_attachment_chunks")
    op.drop_table("conversation_attachments")
