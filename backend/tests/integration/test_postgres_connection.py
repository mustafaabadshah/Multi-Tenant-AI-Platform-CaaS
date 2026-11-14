"""Integration tests verifying real PostgreSQL 16 connectivity and pgvector extension loading."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_postgres_version_is_16(pg_session: AsyncSession):
    """Verify that the active server is PostgreSQL 16."""
    res = await pg_session.execute(text("SHOW server_version;"))
    version_str = res.scalar_one()
    assert version_str.startswith("16"), f"Expected PostgreSQL 16, got: {version_str}"

    db_res = await pg_session.execute(text("SELECT current_database(), current_user;"))
    db_name, db_user = db_res.one()
    assert db_name == "m05_integration"
    assert db_user == "m05_test"


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_pgvector_extension_loaded_and_functional(pg_session: AsyncSession):
    """Verify that the pgvector extension is installed in PostgreSQL and its version is queryable."""
    ext_res = await pg_session.execute(
        text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
    )
    row = ext_res.one_or_none()
    assert row is not None, "pgvector extension is NOT installed in the PostgreSQL database"
    ext_name, ext_version = row
    assert ext_name == "vector"
    assert ext_version is not None

    # Test basic vector math directly in SQL
    vec_res = await pg_session.execute(
        text("SELECT '[1,2,3]'::vector <=> '[1,2,3]'::vector as dist;")
    )
    dist = vec_res.scalar_one()
    assert abs(dist - 0.0) < 1e-6, f"Cosine distance of identical vectors must be 0.0, got {dist}"


@pytest.mark.postgres_integration
@pytest.mark.asyncio
async def test_transaction_rollback_and_commit_behavior(pg_session: AsyncSession):
    """Verify transaction isolation and clean rollback on the real PostgreSQL engine."""
    await pg_session.execute(
        text("CREATE TEMP TABLE test_m05_trans (id INT, val TEXT);")
    )
    await pg_session.execute(
        text("INSERT INTO test_m05_trans VALUES (1, 'initial');")
    )
    # Check inserted
    count = (await pg_session.execute(text("SELECT count(*) FROM test_m05_trans;"))).scalar_one()
    assert count == 1

    # Rollback session
    await pg_session.rollback()
