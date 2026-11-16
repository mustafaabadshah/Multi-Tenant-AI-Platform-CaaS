"""M16: Durable authentication sessions, refresh token rotation, and invitation lifecycle

Revision ID: 0012_m16_auth_sessions_and_invitations
Revises: 0011_m15_durable_request_traces
Create Date: 2026-11-15

Introduces:
- `auth_sessions`: durable server-side session entity for refresh token rotation, replay detection, and logout revocation.
- `invitations` updates: `invited_by_id` and `is_cancelled` columns to support full invitation lifecycle and revocation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_m16_auth_sessions_and_invitations"
down_revision: str | None = "0011_m15_durable_request_traces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. auth_sessions table
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(64), nullable=False),
        sa.Column("previous_refresh_token_hash", sa.String(64), nullable=True),
        sa.Column("session_family_id", sa.Uuid(), nullable=False),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(100), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(100), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_user_revoked", "auth_sessions", ["user_id", "is_revoked"])
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["refresh_token_hash"])
    op.create_index("ix_auth_sessions_prev_token_hash", "auth_sessions", ["previous_refresh_token_hash"])
    op.create_index("ix_auth_sessions_family", "auth_sessions", ["session_family_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])

    # 2. Add columns to invitations
    with op.batch_alter_table("invitations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "invited_by_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_invitations_invited_by_id_users"),
                nullable=True,
            ),
        )
        batch_op.add_column(
            sa.Column("is_cancelled", sa.Boolean(), server_default=sa.false(), nullable=False),
        )


def downgrade() -> None:
    with op.batch_alter_table("invitations") as batch_op:
        batch_op.drop_column("is_cancelled")
        batch_op.drop_column("invited_by_id")

    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_family", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_prev_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_revoked", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
