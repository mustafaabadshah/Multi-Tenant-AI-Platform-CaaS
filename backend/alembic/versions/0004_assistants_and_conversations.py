"""Assistants runtime, knowledge connections, conversations, and citations schema

Revision ID: 0004_assistants_and_conversations
Revises: 0003_embeddings_and_vector_stores
Create Date: 2026-11-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_assistants_and_conversations"
down_revision: str | None = "0003_embeddings_and_vector_stores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add LLM generation and retrieval configuration columns to assistants
    op.add_column(
        "assistants",
        sa.Column("llm_provider", sa.String(50), nullable=False, server_default="omniroute"),
    )
    op.add_column(
        "assistants",
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
    )
    op.add_column(
        "assistants",
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="1024"),
    )
    op.add_column(
        "assistants",
        sa.Column("visibility", sa.String(50), nullable=False, server_default="workspace"),
    )
    op.add_column(
        "assistants",
        sa.Column("retrieval_mode", sa.String(50), nullable=False, server_default="hybrid"),
    )
    op.add_column(
        "assistants",
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="5"),
    )

    # 2. Assistant Knowledge Base Association
    op.create_table(
        "assistant_knowledge_bases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assistant_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assistant_id", "knowledge_base_id", name="uq_assistant_kb"),
    )
    op.create_index("ix_assistant_kbs_tenant_id", "assistant_knowledge_bases", ["tenant_id"])
    op.create_index("ix_assistant_kbs_assistant_id", "assistant_knowledge_bases", ["assistant_id"])
    op.create_index("ix_assistant_kbs_kb_id", "assistant_knowledge_bases", ["knowledge_base_id"])

    # 3. Conversations
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("assistant_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default="New Conversation"),
        sa.Column("status", sa.String(50), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_assistant_id", "conversations", ["assistant_id"])

    # 4. Messages
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("sender_type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # 5. Message Citations
    op.create_table(
        "message_citations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=True),
        sa.Column("document_name", sa.String(255), nullable=False),
        sa.Column("citation_num", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("citation_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_message_citations_tenant_id", "message_citations", ["tenant_id"])
    op.create_index("ix_message_citations_message_id", "message_citations", ["message_id"])


def downgrade() -> None:
    op.drop_table("message_citations")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("assistant_knowledge_bases")
    op.drop_column("assistants", "top_k")
    op.drop_column("assistants", "retrieval_mode")
    op.drop_column("assistants", "visibility")
    op.drop_column("assistants", "max_tokens")
    op.drop_column("assistants", "temperature")
    op.drop_column("assistants", "llm_provider")
