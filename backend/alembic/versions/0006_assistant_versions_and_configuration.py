"""Add assistant configuration columns and assistant_versions table

Revision ID: 0006_assistant_versions_and_configuration
Revises: 0005_add_assistant_byok_encrypted_key
Create Date: 2026-11-08 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_assistant_versions_and_configuration"
down_revision: str | None = "0005_add_assistant_byok_encrypted_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add configuration columns to assistants table
    with op.batch_alter_table("assistants") as batch_op:
        batch_op.add_column(
            sa.Column("template_id", sa.String(100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("audience_level", sa.String(50), nullable=False, server_default="general")
        )
        batch_op.add_column(
            sa.Column("response_style", sa.String(50), nullable=False, server_default="balanced")
        )
        batch_op.add_column(
            sa.Column("uncertainty_behavior", sa.String(50), nullable=False, server_default="admit")
        )
        batch_op.add_column(
            sa.Column("citation_style", sa.String(50), nullable=False, server_default="strict")
        )
        batch_op.add_column(
            sa.Column("current_version_num", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.create_index("ix_assistants_template_id", ["template_id"])

    # 2. Create assistant_versions table if not already created
    op.create_table(
        "assistant_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assistant_id", sa.Uuid(), nullable=False),
        sa.Column("version_num", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("config_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("change_summary", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assistant_id", "version_num", name="uq_assistant_version_num"),
    )
    op.create_index("ix_assistant_versions_tenant_id", "assistant_versions", ["tenant_id"])
    op.create_index("ix_assistant_versions_assistant_id", "assistant_versions", ["assistant_id"])
    op.create_index("ix_assistant_versions_actor_id", "assistant_versions", ["actor_id"])


def downgrade() -> None:
    op.drop_table("assistant_versions")
    with op.batch_alter_table("assistants") as batch_op:
        batch_op.drop_index("ix_assistants_template_id")
        batch_op.drop_column("current_version_num")
        batch_op.drop_column("citation_style")
        batch_op.drop_column("uncertainty_behavior")
        batch_op.drop_column("response_style")
        batch_op.drop_column("audience_level")
        batch_op.drop_column("template_id")
