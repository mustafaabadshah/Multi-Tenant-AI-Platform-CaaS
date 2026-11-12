"""Pytest fixtures for live PostgreSQL 16 & pgvector integration testing."""

import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.constants import SystemRole, TenantType
from app.core.security import hash_password
from app.database.base import Base
from app.models.department import Department
from app.models.membership import TenantMembership
from app.models.tenant import Tenant
from app.models.user import User

# Dedicated isolated PostgreSQL 16 M05 test database connection string
POSTGRES_TEST_URL = os.environ.get(
    "M05_POSTGRES_TEST_URL",
    "postgresql+asyncpg://m05_test:m05_test_password_secure_local@127.0.0.1:55432/m05_integration",
)


async def is_postgres_online() -> bool:
    """Verify whether live PostgreSQL 16 instance is reachable."""
    try:
        temp_engine = create_async_engine(
            POSTGRES_TEST_URL,
            echo=False,
            pool_pre_ping=True,
            connect_args={"timeout": 3},
        )
        async with temp_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await temp_engine.dispose()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def postgres_available():
    import asyncio
    online = asyncio.run(is_postgres_online())
    if not online:
        pytest.skip(
            f"Live PostgreSQL 16 instance is NOT reachable at {POSTGRES_TEST_URL}. "
            "To execute: start the isolated M05 container with `docker compose -f docker-compose.m05-postgres.yml up -d`."
        )
    return True


@pytest_asyncio.fixture(scope="session")
async def pg_engine(postgres_available):
    engine = create_async_engine(
        POSTGRES_TEST_URL,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
    # Ensure pgvector extension and schema tables exist
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = async_sessionmaker(
        pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def pg_seed_tenants(pg_session: AsyncSession) -> dict:
    """Seeds two completely distinct tenants in PostgreSQL for cross-tenant isolation testing."""
    # Seed roles if not present
    from app.repositories.role_repository import RoleRepository

    role_repo = RoleRepository(pg_session)
    await role_repo.seed_system_roles_and_permissions()

    owner_role = (await pg_session.execute(
        text("SELECT id FROM roles WHERE name = :name"),
        {"name": SystemRole.TENANT_OWNER.value},
    )).scalar_one()

    emp_role = (await pg_session.execute(
        text("SELECT id FROM roles WHERE name = :name"),
        {"name": SystemRole.EMPLOYEE.value},
    )).scalar_one()

    # 1. Tenant A
    user_a = User(
        id=uuid.uuid4(),
        email=f"alice_{uuid.uuid4().hex[:6]}@companya.com",
        hashed_password=hash_password("Password123!"),
        full_name="Alice Owner",
    )
    pg_session.add(user_a)
    await pg_session.flush()

    tenant_a = Tenant(
        id=uuid.uuid4(),
        name="Company A",
        slug=f"company-a-{uuid.uuid4().hex[:6]}",
        type=TenantType.ORGANIZATION.value,
        status="ACTIVE",
    )
    pg_session.add(tenant_a)
    await pg_session.flush()

    membership_a = TenantMembership(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        user_id=user_a.id,
        role_id=owner_role,
        status="ACTIVE",
    )
    pg_session.add(membership_a)

    dept_a = Department(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        name="Engineering",
    )
    pg_session.add(dept_a)

    # 2. Tenant B
    user_b = User(
        id=uuid.uuid4(),
        email=f"bob_{uuid.uuid4().hex[:6]}@companyb.com",
        hashed_password=hash_password("Password123!"),
        full_name="Bob Owner",
    )
    pg_session.add(user_b)
    await pg_session.flush()

    tenant_b = Tenant(
        id=uuid.uuid4(),
        name="Company B",
        slug=f"company-b-{uuid.uuid4().hex[:6]}",
        type=TenantType.ORGANIZATION.value,
        status="ACTIVE",
    )
    pg_session.add(tenant_b)
    await pg_session.flush()

    membership_b = TenantMembership(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        user_id=user_b.id,
        role_id=owner_role,
        status="ACTIVE",
    )
    pg_session.add(membership_b)

    dept_b = Department(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        name="Marketing",
    )
    pg_session.add(dept_b)

    await pg_session.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_a": user_a,
        "user_b": user_b,
        "dept_a": dept_a,
        "dept_b": dept_b,
        "owner_role_id": owner_role,
        "emp_role_id": emp_role,
    }
