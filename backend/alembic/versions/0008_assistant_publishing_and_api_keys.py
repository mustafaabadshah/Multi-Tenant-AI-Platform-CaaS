"""Add assistant_publications, api_keys, and public_chat_sessions tables for M08

Revision ID: 0008_assistant_publishing_and_api_keys
Revises: 0007_provider_credentials_and_usage
Create Date: 2026-11-09 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_assistant_publishing_and_api_keys"
down_revision: str | None = "0007_provider_credentials_and_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create assistant_publications table
    op.create_table(
        "assistant_publications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assistant_id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.String(64), nullable=False),
        sa.Column("visibility", sa.String(50), nullable=False, server_default="PRIVATE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allowed_domains", sa.Text(), nullable=True, server_default="[]"),
        sa.Column("custom_greeting", sa.Text(), nullable=True),
        sa.Column("brand_color", sa.String(20), nullable=False, server_default="#0284c7"),
        sa.Column("published_version_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["published_version_id"], ["assistant_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assistant_id", name="uq_publication_assistant_id"),
        sa.UniqueConstraint("public_id", name="uq_publication_public_id"),
    )
    op.create_index("ix_assistant_publications_tenant_id", "assistant_publications", ["tenant_id"])
    op.create_index("ix_assistant_publications_public_id", "assistant_publications", ["public_id"])

    # 2. Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False, server_default='["assistant:read", "assistant:chat"]'),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_tenant_id", "api_keys", ["tenant_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    # 3. Create public_chat_sessions table
    op.create_table(
        "public_chat_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("session_token", sa.String(64), nullable=False),
        sa.Column("client_ip_hash", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["publication_id"], ["assistant_publications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token", name="uq_public_chat_sessions_session_token"),
    )
    op.create_index("ix_public_chat_sessions_tenant_id", "public_chat_sessions", ["tenant_id"])
    op.create_index("ix_public_chat_sessions_session_token", "public_chat_sessions", ["session_token"])

    # 4. Add credential_source and traffic_type columns to provider_usage_logs
    op.add_column(
        "provider_usage_logs",
        sa.Column("credential_source", sa.String(50), nullable=False, server_default="byok"),
    )
    op.add_column(
        "provider_usage_logs",
        sa.Column("traffic_type", sa.String(50), nullable=False, server_default="internal"),
    )

    # 5. Make conversations.user_id nullable for public and developer sessions
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("provider_usage_logs", "traffic_type")
    op.drop_column("provider_usage_logs", "credential_source")
    op.drop_table("public_chat_sessions")
    op.drop_table("api_keys")
    op.drop_table("assistant_publications")
