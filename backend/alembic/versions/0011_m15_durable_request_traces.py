"""M15: Durable request traces and workspace observability policies

Revision ID: 0011_m15_durable_request_traces
Revises: 0010_m10_remediation_schema_alignment
Create Date: 2026-11-14

Introduces persistent telemetry storage:
- `request_traces`: durable AI request records, lifecycle spans, retrieval metadata, and safe I/O previews.
- `observability_policies`: tenant-level configuration for capture mode and data retention.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_m15_durable_request_traces"
down_revision: str | None = "0010_m10_remediation_schema_alignment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. request_traces table
    op.create_table(
        "request_traces",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("trace_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assistant_id", sa.Uuid(), sa.ForeignKey("assistants.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assistant_name", sa.String(100), nullable=False, server_default="Assistant"),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("traffic_type", sa.String(50), nullable=False, server_default="internal"),
        sa.Column("status", sa.String(20), nullable=False, server_default="RUNNING"),
        sa.Column("error_category", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("credential_source", sa.String(50), nullable=False, server_default="byok"),
        sa.Column("retrieval_mode", sa.String(50), nullable=True),
        sa.Column("retrieved_chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_token_estimated", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("pricing_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("total_duration_ms", sa.Float(), nullable=True),
        sa.Column("ttft_ms", sa.Float(), nullable=True),
        sa.Column("spans_data", sa.JSON(), nullable=False),
        sa.Column("retrieval_metadata", sa.JSON(), nullable=True),
        sa.Column("input_preview", sa.Text(), nullable=True),
        sa.Column("output_preview", sa.Text(), nullable=True),
        sa.Column("has_preview", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_request_traces_trace_id", "request_traces", ["trace_id"], unique=True)
    op.create_index("ix_request_traces_tenant_id", "request_traces", ["tenant_id"])
    op.create_index("ix_request_traces_assistant_id", "request_traces", ["assistant_id"])
    op.create_index("ix_request_traces_conversation_id", "request_traces", ["conversation_id"])
    op.create_index("ix_request_traces_status", "request_traces", ["status"])
    op.create_index("ix_request_traces_created_at", "request_traces", ["created_at"])
    op.create_index(
        "ix_request_traces_tenant_created",
        "request_traces",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_request_traces_tenant_status",
        "request_traces",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_request_traces_tenant_assistant",
        "request_traces",
        ["tenant_id", "assistant_id"],
    )
    op.create_index(
        "ix_request_traces_tenant_traffic",
        "request_traces",
        ["tenant_id", "traffic_type"],
    )

    # 2. observability_policies table
    op.create_table(
        "observability_policies",
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("capture_mode", sa.String(20), nullable=False, server_default="METADATA_ONLY"),
        sa.Column("max_preview_length", sa.Integer(), nullable=False, server_default="250"),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("observability_policies")
    op.drop_table("request_traces")
