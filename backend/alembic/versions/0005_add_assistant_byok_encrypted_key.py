"""Add byok_encrypted_key to assistants table

Revision ID: 0005_add_assistant_byok_encrypted_key
Revises: 0004_assistants_and_conversations
Create Date: 2026-11-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_add_assistant_byok_encrypted_key"
down_revision: str | None = "0004_assistants_and_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add optional BYOK encrypted key column to assistants table
    with op.batch_alter_table("assistants") as batch_op:
        batch_op.add_column(
            sa.Column("byok_encrypted_key", sa.String(1024), nullable=True),
        )


def downgrade() -> None:
    # Remove BYOK encrypted key column
    with op.batch_alter_table("assistants") as batch_op:
        batch_op.drop_column("byok_encrypted_key")
