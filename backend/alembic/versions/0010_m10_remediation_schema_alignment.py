"""M10 remediation: align migration chain with models (missing tables, indexes, quota column)

Revision ID: 0010_m10_remediation_schema_alignment
Revises: 0009_m09_security_and_evaluation
Create Date: 2026-11-11

The migration chain (0001-0009) omitted nine model tables and several indexes
that the lifespan `create_all()` silently created. This forward-compatible
migration brings Alembic-managed databases to parity with the models and
removes the unused `tenant_quotas.daily_request_limit` column that was added by
migration `0007_provider_credentials_and_usage` but is absent from the model.

Accepted residual drift (functionally equivalent, intentionally NOT touched):
- cosmetic index renames (e.g. ix_chunk_embeddings_doc_id vs ..._document_id);
- unique-constraint vs unique-index representations;
- SQLite type rendering (VECTOR as NUMERIC, Float vs Double).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_m10_remediation_schema_alignment"
down_revision: str | None = "0009_m09_security_and_evaluation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_primary_key() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True, nullable=False)


def _tenant_fk() -> sa.Column:
    return sa.Column(
        "tenant_id",
        sa.Uuid(),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ------------------------------------------------------------------
    # 1. Create missing tables (declared in models, absent from 0001-0009)
    # ------------------------------------------------------------------
    op.create_table(
        "provider_connections",
        _uuid_primary_key(),
        _tenant_fk(),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column(
            "base_url",
            sa.String(255),
            nullable=False,
            server_default="http://localhost:20128/v1",
        ),
        sa.Column("api_key_hash", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        *_timestamps(),
    )
    op.create_index("ix_provider_connections_tenant_id", "provider_connections", ["tenant_id"])

    op.create_table(
        "embedding_configs",
        _uuid_primary_key(),
        _tenant_fk(),
        sa.Column("model_name", sa.String(100), nullable=False, server_default="text-embedding-3-small"),
        sa.Column("dimensions", sa.Integer(), nullable=False, server_default="1536"),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="32"),
        *_timestamps(),
    )
    op.create_index("ix_embedding_configs_tenant_id", "embedding_configs", ["tenant_id"])

    op.create_table(
        "vector_store_configs",
        _uuid_primary_key(),
        _tenant_fk(),
        sa.Column(
            "store_type",
            sa.String(50),
            nullable=False,
            server_default="postgresql_pgvector",
        ),
        sa.Column("endpoint", sa.String(255), nullable=True),
        sa.Column("collection_name", sa.String(100), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_vector_store_configs_tenant_id", "vector_store_configs", ["tenant_id"])

    op.create_table(
        "resource_permissions",
        _uuid_primary_key(),
        _tenant_fk(),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("permission", sa.String(100), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            "resource_type",
            "resource_id",
            "permission",
            name="uq_resource_permission",
        ),
    )
    op.create_index("ix_resource_permissions_tenant_id", "resource_permissions", ["tenant_id"])
    op.create_index("ix_resource_permissions_user_id", "resource_permissions", ["user_id"])

    op.create_table(
        "usage_records",
        _uuid_primary_key(),
        _tenant_fk(),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_usage_records_tenant_id", "usage_records", ["tenant_id"])
    op.create_index("ix_usage_records_metric_name", "usage_records", ["metric_name"])
    op.create_index("ix_usage_records_recorded_at", "usage_records", ["recorded_at"])

    op.create_table(
        "assistant_prompts",
        _uuid_primary_key(),
        sa.Column(
            "assistant_id",
            sa.Uuid(),
            sa.ForeignKey("assistants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prompt_type", sa.String(50), nullable=False, server_default="SYSTEM"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        *_timestamps(),
    )
    op.create_index("ix_assistant_prompts_assistant_id", "assistant_prompts", ["assistant_id"])

    op.create_table(
        "invitations",
        _uuid_primary_key(),
        _tenant_fk(),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "role_id",
            sa.Uuid(),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            sa.Uuid(),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("token", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_invitations_tenant_id", "invitations", ["tenant_id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])
    op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)

    op.create_table(
        "assistant_memberships",
        _uuid_primary_key(),
        sa.Column(
            "assistant_id",
            sa.Uuid(),
            sa.ForeignKey("assistants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            sa.Uuid(),
            sa.ForeignKey("departments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "group_id",
            sa.Uuid(),
            sa.ForeignKey("employee_groups.id", ondelete="CASCADE"),
            nullable=True,
        ),
        *_timestamps(),
    )
    op.create_index("ix_assistant_memberships_assistant_id", "assistant_memberships", ["assistant_id"])

    op.create_table(
        "message_attachments",
        _uuid_primary_key(),
        _tenant_fk(),
        sa.Column(
            "message_id",
            sa.Uuid(),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_message_attachments_tenant_id", "message_attachments", ["tenant_id"])
    op.create_index("ix_message_attachments_message_id", "message_attachments", ["message_id"])

    # ------------------------------------------------------------------
    # 2. Add missing indexes on existing tables
    # ------------------------------------------------------------------
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])
    op.create_index("ix_tenant_memberships_role_id", "tenant_memberships", ["role_id"])
    op.create_index("ix_tenant_memberships_department_id", "tenant_memberships", ["department_id"])
    op.create_index("ix_tenant_quotas_tenant_id", "tenant_quotas", ["tenant_id"], unique=True)
    op.create_index("ix_employee_groups_department_id", "employee_groups", ["department_id"])
    op.create_index("ix_employee_groups_tenant_id", "employee_groups", ["tenant_id"])
    op.create_index("ix_group_memberships_group_id", "group_memberships", ["group_id"])
    op.create_index("ix_group_memberships_membership_id", "group_memberships", ["membership_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_assistants_slug", "assistants", ["slug"])
    op.create_index("ix_provider_usage_logs_assistant_id", "provider_usage_logs", ["assistant_id"])
    op.create_index("ix_provider_usage_logs_user_id", "provider_usage_logs", ["user_id"])
    op.create_index("ix_ingestion_jobs_document_version_id", "ingestion_jobs", ["document_version_id"])
    op.create_index("ix_embedding_jobs_document_id", "embedding_jobs", ["document_id"])
    op.create_index("ix_document_chunks_document_version_id", "document_chunks", ["document_version_id"])
    op.create_index("ix_chunk_embeddings_document_version_id", "chunk_embeddings", ["document_version_id"])
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index(
        "ix_assistant_publications_assistant_id",
        "assistant_publications",
        ["assistant_id"],
        unique=True,
    )
    op.create_index(
        "ix_public_chat_sessions_publication_id",
        "public_chat_sessions",
        ["publication_id"],
    )

    # ------------------------------------------------------------------
    # 3. Drop unused quota column (added by 0007, absent from model)
    # ------------------------------------------------------------------
    if is_postgres:
        op.drop_column("tenant_quotas", "daily_request_limit")
    else:
        with op.batch_alter_table("tenant_quotas", schema=None) as batch_op:
            batch_op.drop_column("daily_request_limit")


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.add_column(
            "tenant_quotas",
            sa.Column("daily_request_limit", sa.Integer(), nullable=False, server_default="1000"),
        )
    else:
        with op.batch_alter_table("tenant_quotas", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("daily_request_limit", sa.Integer(), nullable=False, server_default="1000")
            )

    op.drop_index("ix_public_chat_sessions_publication_id", table_name="public_chat_sessions")
    op.drop_index("ix_assistant_publications_assistant_id", table_name="assistant_publications")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_index("ix_chunk_embeddings_document_version_id", table_name="chunk_embeddings")
    op.drop_index("ix_document_chunks_document_version_id", table_name="document_chunks")
    op.drop_index("ix_embedding_jobs_document_id", table_name="embedding_jobs")
    op.drop_index("ix_ingestion_jobs_document_version_id", table_name="ingestion_jobs")
    op.drop_index("ix_provider_usage_logs_user_id", table_name="provider_usage_logs")
    op.drop_index("ix_provider_usage_logs_assistant_id", table_name="provider_usage_logs")
    op.drop_index("ix_assistants_slug", table_name="assistants")
    op.drop_index("ix_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_group_memberships_membership_id", table_name="group_memberships")
    op.drop_index("ix_group_memberships_group_id", table_name="group_memberships")
    op.drop_index("ix_employee_groups_tenant_id", table_name="employee_groups")
    op.drop_index("ix_employee_groups_department_id", table_name="employee_groups")
    op.drop_index("ix_tenant_quotas_tenant_id", table_name="tenant_quotas")
    op.drop_index("ix_tenant_memberships_department_id", table_name="tenant_memberships")
    op.drop_index("ix_tenant_memberships_role_id", table_name="tenant_memberships")
    op.drop_index("ix_role_permissions_permission_id", table_name="role_permissions")
    op.drop_index("ix_role_permissions_role_id", table_name="role_permissions")
    op.drop_index("ix_roles_tenant_id", table_name="roles")

    op.drop_table("message_attachments")
    op.drop_table("assistant_memberships")
    op.drop_table("invitations")
    op.drop_table("assistant_prompts")
    op.drop_table("usage_records")
    op.drop_table("resource_permissions")
    op.drop_table("vector_store_configs")
    op.drop_table("embedding_configs")
    op.drop_table("provider_connections")
