"""Add assistant_id to api_keys, conversation_id to public_chat_sessions, and evaluation tables for M09

Revision ID: 0009_m09_security_and_evaluation
Revises: 0008_assistant_publishing_and_api_keys
Create Date: 2026-11-10 01:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_m09_security_and_evaluation"
down_revision: str | None = "0008_assistant_publishing_and_api_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add assistant_id to api_keys table
    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.add_column(sa.Column("assistant_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_api_keys_assistant_id",
            "assistants",
            ["assistant_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_api_keys_assistant_id", ["assistant_id"])

    # 2. Add conversation_id to public_chat_sessions table
    with op.batch_alter_table("public_chat_sessions") as batch_op:
        batch_op.add_column(sa.Column("conversation_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_public_chat_sessions_conversation_id",
            "conversations",
            ["conversation_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_public_chat_sessions_conversation_id", ["conversation_id"])

    # 3. Create eval_datasets table
    op.create_table(
        "eval_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_datasets_tenant_id", "eval_datasets", ["tenant_id"])

    # 4. Create eval_dataset_items table
    op.create_table(
        "eval_dataset_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("expected_chunk_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_unanswerable", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_adversarial", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("item_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["eval_datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_dataset_items_dataset_id", "eval_dataset_items", ["dataset_id"])

    # 5. Create eval_runs table
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assistant_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("eval_type", sa.String(50), nullable=False, server_default="deterministic"),
        sa.Column("judge_provider", sa.String(100), nullable=True),
        sa.Column("judge_model", sa.String(100), nullable=True),
        sa.Column("metrics_summary", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assistant_id"], ["assistants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dataset_id"], ["eval_datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_runs_assistant_id", "eval_runs", ["assistant_id"])
    op.create_index("ix_eval_runs_dataset_id", "eval_runs", ["dataset_id"])
    op.create_index("ix_eval_runs_status", "eval_runs", ["status"])
    op.create_index("ix_eval_runs_tenant_id", "eval_runs", ["tenant_id"])

    # 6. Create eval_run_results table
    op.create_table(
        "eval_run_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("generated_answer", sa.Text(), nullable=True),
        sa.Column("retrieved_chunks", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("citations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("recall_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("mrr_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("faithfulness_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("citation_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["eval_dataset_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["eval_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eval_run_results_item_id", "eval_run_results", ["item_id"])
    op.create_index("ix_eval_run_results_run_id", "eval_run_results", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_eval_run_results_run_id", table_name="eval_run_results")
    op.drop_index("ix_eval_run_results_item_id", table_name="eval_run_results")
    op.drop_table("eval_run_results")

    op.drop_index("ix_eval_runs_tenant_id", table_name="eval_runs")
    op.drop_index("ix_eval_runs_status", table_name="eval_runs")
    op.drop_index("ix_eval_runs_dataset_id", table_name="eval_runs")
    op.drop_index("ix_eval_runs_assistant_id", table_name="eval_runs")
    op.drop_table("eval_runs")

    op.drop_index("ix_eval_dataset_items_dataset_id", table_name="eval_dataset_items")
    op.drop_table("eval_dataset_items")

    op.drop_index("ix_eval_datasets_tenant_id", table_name="eval_datasets")
    op.drop_table("eval_datasets")

    with op.batch_alter_table("public_chat_sessions") as batch_op:
        batch_op.drop_index("ix_public_chat_sessions_conversation_id")
        batch_op.drop_column("conversation_id")

    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.drop_index("ix_api_keys_assistant_id")
        batch_op.drop_column("assistant_id")
