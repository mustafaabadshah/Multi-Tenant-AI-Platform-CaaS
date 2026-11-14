from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.constants import SystemRole, TenantType
from app.core.security import create_access_token, hash_password
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.repositories.role_repository import RoleRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.user_repository import UserRepository

# In-memory SQLite async test database
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    future=True,
)

test_async_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    # Force test configuration
    pass


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with test_async_session_maker() as session:
        # Seed system roles & permissions
        role_repo = RoleRepository(session)
        await role_repo.seed_system_roles_and_permissions()
        await session.commit()
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def enable_public_features(monkeypatch):
    """Opt-in fixture enabling public publishing and the developer API.

    Default-off behavior remains testable because this is not autouse.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "PUBLIC_PUBLISHING_ENABLED", True)
    monkeypatch.setattr(settings, "DEVELOPER_API_ENABLED", True)
    yield


@pytest.fixture
async def seed_data(db_session: AsyncSession):
    """Creates two distinct tenants (Company A and Company B) with distinct owners and employees."""
    user_repo = UserRepository(db_session)
    tenant_repo = TenantRepository(db_session)
    role_repo = RoleRepository(db_session)

    owner_role = await role_repo.get_by_name(SystemRole.TENANT_OWNER.value)
    employee_role = await role_repo.get_by_name(SystemRole.EMPLOYEE.value)
    assert owner_role is not None and employee_role is not None

    # 1. Company A Owner & Employee
    user_a_owner = await user_repo.create(
        email="owner_a@companya.com",
        hashed_password=hash_password("Password123!"),
        full_name="Alice Owner",
    )
    user_a_employee = await user_repo.create(
        email="emp_a@companya.com",
        hashed_password=hash_password("Password123!"),
        full_name="Andy Employee",
    )

    tenant_a, _ = await tenant_repo.create_tenant(
        name="Company A",
        tenant_type=TenantType.ORGANIZATION,
        owner_id=user_a_owner.id,
        owner_role=owner_role,
        slug="company-a",
        legal_name="Company A Inc",
    )

    # Add Andy to Tenant A as employee
    from app.repositories.member_repository import MemberRepository

    member_repo_a = MemberRepository(db_session, tenant_a.id)
    await member_repo_a.create(
        user_id=user_a_employee.id,
        role_id=employee_role.id,
        title="Software Engineer",
    )

    # 2. Company B Owner & Employee
    user_b_owner = await user_repo.create(
        email="owner_b@companyb.com",
        hashed_password=hash_password("Password123!"),
        full_name="Bob Owner",
    )
    user_b_employee = await user_repo.create(
        email="emp_b@companyb.com",
        hashed_password=hash_password("Password123!"),
        full_name="Betty Employee",
    )

    tenant_b, _ = await tenant_repo.create_tenant(
        name="Company B",
        tenant_type=TenantType.ORGANIZATION,
        owner_id=user_b_owner.id,
        owner_role=owner_role,
        slug="company-b",
        legal_name="Company B Ltd",
    )

    member_repo_b = MemberRepository(db_session, tenant_b.id)
    await member_repo_b.create(
        user_id=user_b_employee.id,
        role_id=employee_role.id,
        title="Data Analyst",
    )

    await db_session.commit()

    # Generate access tokens
    token_a_owner = create_access_token(
        str(user_a_owner.id),
        {"email": user_a_owner.email, "tenant_id": str(tenant_a.id)},
    )
    token_a_employee = create_access_token(
        str(user_a_employee.id),
        {"email": user_a_employee.email, "tenant_id": str(tenant_a.id)},
    )
    token_b_owner = create_access_token(
        str(user_b_owner.id),
        {"email": user_b_owner.email, "tenant_id": str(tenant_b.id)},
    )
    token_b_employee = create_access_token(
        str(user_b_employee.id),
        {"email": user_b_employee.email, "tenant_id": str(tenant_b.id)},
    )

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_a_owner": user_a_owner,
        "user_a_employee": user_a_employee,
        "user_b_owner": user_b_owner,
        "user_b_employee": user_b_employee,
        "token_a_owner": token_a_owner,
        "token_a_employee": token_a_employee,
        "token_b_owner": token_b_owner,
        "token_b_employee": token_b_employee,
    }
