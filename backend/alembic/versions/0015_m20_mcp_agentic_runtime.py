"""M20: Model Context Protocol (MCP) connections, human approvals, and tool invocation telemetry

Revision ID: 0015_m20_mcp_agentic_runtime
Revises: 0014_m19_tool_registry
Create Date: 2026-11-15

Introduces:
- `mcp_connections`: external remote MCP servers with encrypted credentials and capability/tool approval cache.
- `tool_approvals`: PostgreSQL-durable human-in-the-loop pending approval tokens for high-risk / mutating tool operations.
- `tool_invocation_logs`: persistent audit and execution telemetry for agentic tool runs.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_m20_mcp_agentic_runtime"
down_revision: str | None = "0014_m19_tool_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. MCP Connections
    op.create_table(
        "mcp_connections",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("server_url", sa.String(2000), nullable=False),
        sa.Column("auth_mode", sa.String(50), server_default="NONE", nullable=False),
        sa.Column("encrypted_credential", sa.Text(), nullable=True),
        sa.Column("connection_status", sa.String(50), server_default="CONNECTED", nullable=False),
        sa.Column("server_capabilities", sa.JSON(), nullable=False),
        sa.Column("approved_tools", sa.JSON(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mcp_connections_tenant_id", "mcp_connections", ["tenant_id"])
    op.create_index("ix_mcp_connections_user_id", "mcp_connections", ["user_id"])

    # 2. Tool Approvals
    op.create_table(
        "tool_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assistant_id", sa.Uuid(), sa.ForeignKey("assistants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_id", sa.String(255), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(50), server_default="PENDING", nullable=False),
        sa.Column("approval_token", sa.String(100), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tool_approvals_tenant_id", "tool_approvals", ["tenant_id"])
    op.create_index("ix_tool_approvals_conversation_id", "tool_approvals", ["conversation_id"])
    op.create_index("ix_tool_approvals_token", "tool_approvals", ["approval_token"], unique=True)
    op.create_index("ix_tool_approvals_status_expires", "tool_approvals", ["status", "expires_at"])

    # 3. Tool Invocation Logs
    op.create_table(
        "tool_invocation_logs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assistant_id", sa.Uuid(), sa.ForeignKey("assistants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trace_id", sa.String(100), nullable=True),
        sa.Column("tool_id", sa.String(255), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("tool_type", sa.String(50), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tool_invocation_logs_tenant_id", "tool_invocation_logs", ["tenant_id"])
    op.create_index("ix_tool_invocation_logs_trace_id", "tool_invocation_logs", ["trace_id"])
    op.create_index("ix_tool_invocation_logs_conversation", "tool_invocation_logs", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_tool_invocation_logs_conversation", table_name="tool_invocation_logs")
    op.drop_index("ix_tool_invocation_logs_trace_id", table_name="tool_invocation_logs")
    op.drop_index("ix_tool_invocation_logs_tenant_id", table_name="tool_invocation_logs")
    op.drop_table("tool_invocation_logs")

    op.drop_index("ix_tool_approvals_status_expires", table_name="tool_approvals")
    op.drop_index("ix_tool_approvals_token", table_name="tool_approvals")
    op.drop_index("ix_tool_approvals_conversation_id", table_name="tool_approvals")
    op.drop_index("ix_tool_approvals_tenant_id", table_name="tool_approvals")
    op.drop_table("tool_approvals")

    op.drop_index("ix_mcp_connections_user_id", table_name="mcp_connections")
    op.drop_index("ix_mcp_connections_tenant_id", table_name="mcp_connections")
    op.drop_table("mcp_connections")
