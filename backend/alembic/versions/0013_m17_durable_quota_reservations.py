"""M17: Durable quota reservations and concurrency enforcement

Revision ID: 0013_m17_durable_quota_reservations
Revises: 0012_m16_auth_sessions_and_invitations
Create Date: 2026-11-15

Introduces:
- `quota_reservations`: PostgreSQL-backed atomic quota reservation table to replace process-local in-memory state.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_m17_durable_quota_reservations"
down_revision: str | None = "0012_m16_auth_sessions_and_invitations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quota_reservations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tokens_reserved", sa.Integer(), server_default="500", nullable=False),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_quota_reservations_tenant_id", "quota_reservations", ["tenant_id"])
    op.create_index("ix_quota_reservations_status", "quota_reservations", ["status"])
    op.create_index("ix_quota_reservations_tenant_status", "quota_reservations", ["tenant_id", "status"])
    op.create_index("ix_quota_reservations_expires_at", "quota_reservations", ["expires_at"])
    op.create_index("ix_quota_reservations_created_at", "quota_reservations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_quota_reservations_created_at", table_name="quota_reservations")
    op.drop_index("ix_quota_reservations_expires_at", table_name="quota_reservations")
    op.drop_index("ix_quota_reservations_tenant_status", table_name="quota_reservations")
    op.drop_index("ix_quota_reservations_status", table_name="quota_reservations")
    op.drop_index("ix_quota_reservations_tenant_id", table_name="quota_reservations")
    op.drop_table("quota_reservations")
