"""M20.2: Assistant tools configuration and security bounds

Revision ID: 0016_m20_2_assistant_tools_config
Revises: 0015_m20_mcp_agentic_runtime
Create Date: 2026-11-16

Introduces:
- `assistants.tools_config`: JSON configuration field storing enabled tool IDs,
  allowed MCP connections, execution limits, and approval policies.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_m20_2_assistant_tools_config"
down_revision: str | None = "0015_m20_mcp_agentic_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assistants") as batch_op:
        batch_op.add_column(
            sa.Column("tools_config", sa.JSON(), nullable=True, server_default="{}")
        )


def downgrade() -> None:
    with op.batch_alter_table("assistants") as batch_op:
        batch_op.drop_column("tools_config")
