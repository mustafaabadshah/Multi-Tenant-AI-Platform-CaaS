"""Embeddings, Vector Stores, and Secure Hybrid Retrieval schema

Revision ID: 0003_embeddings_and_vector_stores
Revises: 0002_document_ingestion_engine
Create Date: 2026-11-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_embeddings_and_vector_stores"
down_revision: str | None = "0002_document_ingestion_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Enable pgvector extension on PostgreSQL
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Add department and access control columns to knowledge_bases and documents
    op.add_column("knowledge_bases", sa.Column("department_id", sa.Uuid(), nullable=True))
    op.add_column("knowledge_bases", sa.Column("access_level", sa.String(50), nullable=False, server_default="tenant"))
    if is_postgres:
        op.create_foreign_key(
            "fk_kb_department",
            "knowledge_bases",
            "departments",
            ["department_id"],
            ["id"],
            ondelete="SET NULL",
        )
    else:
        # SQLite cannot ALTER ADD CONSTRAINT; rebuild the table in batch mode.
        with op.batch_alter_table("knowledge_bases", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_kb_department",
                "departments",
                ["department_id"],
                ["id"],
                ondelete="SET NULL",
            )
    op.create_index("ix_knowledge_bases_department_id", "knowledge_bases", ["department_id"])

    op.add_column("documents", sa.Column("department_id", sa.Uuid(), nullable=True))
    op.add_column("documents", sa.Column("access_level", sa.String(50), nullable=False, server_default="tenant"))
    if is_postgres:
        op.create_foreign_key(
            "fk_doc_department",
            "documents",
            "departments",
            ["department_id"],
            ["id"],
            ondelete="SET NULL",
        )
    else:
        with op.batch_alter_table("documents", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_doc_department",
                "departments",
                ["department_id"],
                ["id"],
                ondelete="SET NULL",
            )
    op.create_index("ix_documents_department_id", "documents", ["department_id"])

    # 3. Retrieval & Vector Store Configurations
    op.create_table(
        "retrieval_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("retrieval_mode", sa.String(50), nullable=False, server_default="hybrid"),
        sa.Column("vector_store", sa.String(50), nullable=False, server_default="pgvector"),
        sa.Column("embedding_provider", sa.String(50), nullable=False, server_default="omniroute"),
        sa.Column("embedding_model", sa.String(100), nullable=False, server_default="text-embedding-3-small"),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False, server_default="1536"),
        sa.Column("similarity_metric", sa.String(20), nullable=False, server_default="cosine"),
        sa.Column("top_k", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("rrf_k", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("rerank_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("rerank_provider", sa.String(50), nullable=True),
        sa.Column("embedding_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("encrypted_api_key", sa.String(1024), nullable=True),
        sa.Column("settings_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("knowledge_base_id", name="uq_retrieval_config_kb"),
    )
    op.create_index("ix_retrieval_configs_tenant_id", "retrieval_configs", ["tenant_id"])
    op.create_index("ix_retrieval_configs_kb_id", "retrieval_configs", ["knowledge_base_id"])

    # 4. Chunk Embeddings
    op.create_table(
        "chunk_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("embedding_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("vector", Vector(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id", "embedding_version", name="uq_chunk_embedding_version"),
    )
    op.create_index("ix_chunk_embeddings_tenant_id", "chunk_embeddings", ["tenant_id"])
    op.create_index("ix_chunk_embeddings_kb_id", "chunk_embeddings", ["knowledge_base_id"])
    op.create_index("ix_chunk_embeddings_doc_id", "chunk_embeddings", ["document_id"])
    op.create_index("ix_chunk_embeddings_chunk_id", "chunk_embeddings", ["chunk_id"])
    op.create_index("ix_chunk_embeddings_version", "chunk_embeddings", ["embedding_version"])
    op.create_index("ix_chunk_embeddings_hash", "chunk_embeddings", ["content_hash"])

    # 5. Embedding Jobs
    op.create_table(
        "embedding_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_base_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("embedding_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("stage", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("job_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_embedding_jobs_tenant_id", "embedding_jobs", ["tenant_id"])
    op.create_index("ix_embedding_jobs_kb_id", "embedding_jobs", ["knowledge_base_id"])
    op.create_index("ix_embedding_jobs_status", "embedding_jobs", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.drop_table("embedding_jobs")
    op.drop_table("chunk_embeddings")
    op.drop_table("retrieval_configs")

    if is_postgres:
        op.drop_constraint("fk_doc_department", "documents", type_="foreignkey")
    else:
        with op.batch_alter_table("documents", schema=None) as batch_op:
            batch_op.drop_constraint("fk_doc_department", type_="foreignkey")
    op.drop_index("ix_documents_department_id", table_name="documents")
    op.drop_column("documents", "access_level")
    op.drop_column("documents", "department_id")

    if is_postgres:
        op.drop_constraint("fk_kb_department", "knowledge_bases", type_="foreignkey")
    else:
        with op.batch_alter_table("knowledge_bases", schema=None) as batch_op:
            batch_op.drop_constraint("fk_kb_department", type_="foreignkey")
    op.drop_index("ix_knowledge_bases_department_id", table_name="knowledge_bases")
    op.drop_column("knowledge_bases", "access_level")
    op.drop_column("knowledge_bases", "department_id")
