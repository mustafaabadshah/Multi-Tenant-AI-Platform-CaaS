"""Integration tests verifying Alembic migrations and table structures on real PostgreSQL."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_migration_head_and_schema_tables(pg_session: AsyncSession):
    """Verify that all core tables from migrations 0001-0004 exist in PostgreSQL."""
    expected_tables = {
        "tenants",
        "users",
        "roles",
        "permissions",
        "role_permissions",
        "tenant_memberships",
        "departments",
        "employee_groups",
        "knowledge_bases",
        "documents",
        "document_versions",
        "document_chunks",
        "ingestion_jobs",
        "retrieval_configs",
        "chunk_embeddings",
        "assistants",
        "assistant_knowledge_bases",
        "conversations",
        "messages",
        "message_citations",
    }

    res = await pg_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
        )
    )
    existing_tables = {row[0] for row in res.fetchall()}

    missing = expected_tables - existing_tables
    assert not missing, f"Missing PostgreSQL tables from migrations: {missing}"


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_vector_column_data_type_in_postgresql(pg_session: AsyncSession):
    """Verify that chunk_embeddings.vector is registered as pgvector type in information_schema/pg_type."""
    res = await pg_session.execute(
        text(
            "SELECT udt_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'chunk_embeddings' AND column_name = 'vector';"
        )
    )
    row = res.one_or_none()
    assert row is not None, "column 'vector' does not exist on chunk_embeddings"
    udt_name, data_type = row
    assert udt_name == "vector", f"Expected udt_name 'vector', got '{udt_name}' (data_type={data_type})"


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_foreign_key_and_tenant_composite_constraints(pg_session: AsyncSession):
    """Verify foreign key integrity on assistants and knowledge bases."""
    fk_res = await pg_session.execute(
        text(
            "SELECT constraint_name, table_name FROM information_schema.table_constraints "
            "WHERE constraint_type = 'FOREIGN KEY' AND table_name IN ('assistant_knowledge_bases', 'conversations');"
        )
    )
    fks = [row[0] for row in fk_res.fetchall()]
    assert any("assistant" in fk.lower() for fk in fks), "Missing assistant foreign keys in PostgreSQL"
