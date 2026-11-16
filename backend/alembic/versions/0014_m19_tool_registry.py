"""M19: Tool registry and custom HTTP integrations

Revision ID: 0014_m19_tool_registry
Revises: 0013_m17_durable_quota_reservations
Create Date: 2026-11-15

Introduces:
- `tools`: general tool abstraction entity supporting Built-in, Custom HTTP, and MCP tools with schema validation, risk classification, and tenant isolation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_m19_tool_registry"
down_revision: str | None = "0013_m17_durable_quota_reservations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tools",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("namespace", sa.String(50), server_default="default", nullable=False),
        sa.Column("tool_type", sa.String(30), server_default="CUSTOM_HTTP", nullable=False),
        sa.Column("risk_level", sa.String(20), server_default="READ_ONLY", nullable=False),
        sa.Column("requires_approval", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.String(20), server_default="1.0.0", nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False),
        sa.Column("http_config", sa.JSON(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default="15", nullable=False),
        sa.Column("max_response_bytes", sa.Integer(), server_default="1048576", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tool_tenant_name"),
    )

    op.create_index("ix_tools_tenant_id", "tools", ["tenant_id"])
    op.create_index("ix_tools_user_id", "tools", ["user_id"])
    op.create_index("ix_tools_tool_type", "tools", ["tool_type"])
    op.create_index("ix_tools_tenant_type", "tools", ["tenant_id", "tool_type"])


def downgrade() -> None:
    op.drop_index("ix_tools_tenant_type", table_name="tools")
    op.drop_index("ix_tools_tool_type", table_name="tools")
    op.drop_index("ix_tools_user_id", table_name="tools")
    op.drop_index("ix_tools_tenant_id", table_name="tools")
    op.drop_table("tools")
