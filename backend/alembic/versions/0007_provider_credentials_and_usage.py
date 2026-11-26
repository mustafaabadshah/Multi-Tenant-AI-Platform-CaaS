"""Add provider_credentials and provider_usage_logs tables for BYOK Vault and Quota Enforcement

Revision ID: 0007_provider_credentials_and_usage
Revises: 0006_assistant_versions_and_configuration
Create Date: 2026-11-09 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_provider_credentials_and_usage"
down_revision: str | None = "0006_assistant_versions_and_configuration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create provider_credentials table
    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("encrypted_api_key", sa.String(1024), nullable=False),
        sa.Column("api_key_masked", sa.String(100), nullable=False),
        sa.Column("base_url", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(50), nullable=False, server_default="HEALTHY"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider_name", "display_name", name="uq_tenant_provider_display"),
    )
    op.create_index("ix_provider_credentials_tenant_id", "provider_credentials", ["tenant_id"])
    op.create_index("ix_provider_credentials_provider_name", "provider_credentials", ["provider_name"])

    # 2. Create provider_usage_logs table
    op.create_table(
        "provider_usage_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("assistant_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_estimated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_usage_logs_tenant_id", "provider_usage_logs", ["tenant_id"])
    op.create_index("ix_provider_usage_logs_provider", "provider_usage_logs", ["provider"])
    op.create_index("ix_provider_usage_logs_created_at", "provider_usage_logs", ["created_at"])

    # 3. Add daily_request_limit to tenant_quotas table
    with op.batch_alter_table("tenant_quotas") as batch_op:
        batch_op.add_column(
            sa.Column("daily_request_limit", sa.Integer(), nullable=False, server_default="1000")
        )


def downgrade() -> None:
    with op.batch_alter_table("tenant_quotas") as batch_op:
        batch_op.drop_column("daily_request_limit")

    op.drop_index("ix_provider_usage_logs_created_at", table_name="provider_usage_logs")
    op.drop_index("ix_provider_usage_logs_provider", table_name="provider_usage_logs")
    op.drop_index("ix_provider_usage_logs_tenant_id", table_name="provider_usage_logs")
    op.drop_table("provider_usage_logs")

    op.drop_index("ix_provider_credentials_provider_name", table_name="provider_credentials")
    op.drop_index("ix_provider_credentials_tenant_id", table_name="provider_credentials")
    op.drop_table("provider_credentials")
