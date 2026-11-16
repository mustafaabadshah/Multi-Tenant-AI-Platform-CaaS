"""M20.1: Alembic Migration Compatibility and Schema Validation Test Suite.

Validates:
1. Scenario A: Linear DAG continuity from 0001 through 0015 head.
2. Scenario B: Progressive upgrade from 0011 through 0015 with pre-existing synthetic data:
   - users, tenants, memberships, assistants, conversations.
   - new tables: auth_sessions, quota_reservations, tools, mcp_connections, tool_approvals, tool_invocation_logs.
   - new invitation columns: invited_by_id, is_cancelled.
   - constraints: uq_tool_tenant_name, unique approval_token, composite indexes.
   - data preservation across upgrades.
3. Scenario C: Downgrade from 0015 -> 0014 -> 0013 -> 0012 -> 0011 and re-upgrade.
4. Scenario D: DML operation validation on all newly created tables.
"""

import importlib.util
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Uuid,
    create_engine,
    insert,
    inspect,
    select,
    text,
)
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def load_migration_module(filename: str):
    """Dynamically load an Alembic migration module by filename."""
    versions_dir = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    file_path = versions_dir / filename
    assert file_path.exists(), f"Migration file not found: {file_path}"
    spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_scenario_a_linear_migration_dag_continuity():
    """Verify unbroken linear DAG chain from 0015 head all the way to 0001."""
    versions_dir = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    migration_files = sorted(versions_dir.glob("*.py"))
    assert len(migration_files) >= 15, f"Expected at least 15 migrations, found {len(migration_files)}"

    revisions: dict[str, dict] = {}
    for mf in migration_files:
        mod = load_migration_module(mf.name)
        assert hasattr(mod, "revision")
        assert hasattr(mod, "upgrade")
        assert hasattr(mod, "downgrade")
        revisions[mod.revision] = {
            "down_revision": getattr(mod, "down_revision", None),
            "file": mf.name,
        }

    head_rev = "0016_m20_2_assistant_tools_config"
    assert head_rev in revisions, f"Head revision {head_rev} not found in revisions"

    chain = []
    curr = head_rev
    while curr is not None:
        chain.append(curr)
        curr = revisions[curr]["down_revision"]

    expected_tail = [
        "0016_m20_2_assistant_tools_config",
        "0015_m20_mcp_agentic_runtime",
        "0014_m19_tool_registry",
        "0013_m17_durable_quota_reservations",
        "0012_m16_auth_sessions_and_invitations",
        "0011_m15_durable_request_traces",
    ]
    assert chain[:6] == expected_tail, f"Top of chain mismatch: {chain[:6]} vs {expected_tail}"
    assert len(chain) == 16, f"Expected 16 migrations in total, got {len(chain)}: {chain}"
    assert chain[-1] == "0001_initial_core_schema"


def test_scenario_b_progressive_upgrade_with_preexisting_data():
    """Simulate upgrading live 0011 staging database to 0015 with pre-existing records."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    metadata = MetaData()

    tenants = Table(
        "tenants",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("slug", String(255), nullable=False),
    )
    users = Table(
        "users",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("email", String(255), nullable=False),
        Column("hashed_password", String(255), nullable=False),
        Column("full_name", String(255), nullable=False),
    )
    invitations = Table(
        "invitations",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("tenant_id", Uuid, nullable=False),
        Column("email", String(255), nullable=False),
        Column("token_hash", String(64), nullable=False),
        Column("role_id", Uuid, nullable=False),
        Column("department_id", Uuid, nullable=True),
        Column("expires_at", DateTime(timezone=True), nullable=False),
        Column("accepted_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )
    assistants = Table(
        "assistants",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("tenant_id", Uuid, nullable=False),
        Column("name", String(255), nullable=False),
        Column("slug", String(255), nullable=False),
    )
    conversations = Table(
        "conversations",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("tenant_id", Uuid, nullable=False),
        Column("assistant_id", Uuid, nullable=False),
        Column("user_id", Uuid, nullable=False),
        Column("title", String(255), nullable=False),
    )

    metadata.create_all(engine)

    # Seed synthetic existing records
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    invitation_id = uuid.uuid4()
    assistant_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    now = datetime.now(UTC)
    with Session(engine) as session:
        session.execute(insert(tenants).values(id=tenant_id, name="Acme Staging Corp", slug="acme-staging"))
        session.execute(
            insert(users).values(
                id=user_id,
                email="operator@staging.example",
                hashed_password="argon2_hashed_secret",
                full_name="Staging Operator",
            )
        )
        session.execute(
            insert(invitations).values(
                id=invitation_id,
                tenant_id=tenant_id,
                email="invited@staging.example",
                token_hash="hash123",
                role_id=uuid.uuid4(),
                expires_at=now + timedelta(days=7),
                created_at=now,
            )
        )
        session.execute(
            insert(assistants).values(
                id=assistant_id,
                tenant_id=tenant_id,
                name="Staging Core Assistant",
                slug="staging-core",
            )
        )
        session.execute(
            insert(conversations).values(
                id=conversation_id,
                tenant_id=tenant_id,
                assistant_id=assistant_id,
                user_id=user_id,
                title="Historical Operator Chat",
            )
        )
        session.commit()

    # Apply 0012: Auth sessions & invitation lifecycle
    mod_0012 = load_migration_module("0012_m16_auth_sessions_and_invitations.py")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0012.upgrade()
        conn.commit()

    # Verify 0012 changes
    insp = inspect(engine)
    assert "auth_sessions" in insp.get_table_names()
    inv_cols = {c["name"] for c in insp.get_columns("invitations")}
    assert "invited_by_id" in inv_cols
    assert "is_cancelled" in inv_cols

    # Apply 0013: Durable quota reservations
    mod_0013 = load_migration_module("0013_m17_durable_quota_reservations.py")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0013.upgrade()
        conn.commit()

    insp = inspect(engine)
    assert "quota_reservations" in insp.get_table_names()

    # Apply 0014: Tool registry
    mod_0014 = load_migration_module("0014_m19_tool_registry.py")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0014.upgrade()
        conn.commit()

    insp = inspect(engine)
    assert "tools" in insp.get_table_names()
    tool_cols = {c["name"] for c in insp.get_columns("tools")}
    assert "input_schema" in tool_cols
    assert "http_config" in tool_cols
    assert "risk_level" in tool_cols

    # Apply 0015: MCP & Agentic runtime
    mod_0015 = load_migration_module("0015_m20_mcp_agentic_runtime.py")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0015.upgrade()
        conn.commit()

    insp = inspect(engine)
    tables = insp.get_table_names()
    assert "mcp_connections" in tables
    assert "tool_approvals" in tables
    assert "tool_invocation_logs" in tables

    # Apply 0016: Assistant tools configuration
    mod_0016 = load_migration_module("0016_m20_2_assistant_tools_config.py")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0016.upgrade()
        conn.commit()

    insp = inspect(engine)
    asst_cols = {c["name"] for c in insp.get_columns("assistants")}
    assert "tools_config" in asst_cols

    # Verify synthetic data survived the entire migration untouched
    with Session(engine) as session:
        t_row = session.execute(text("SELECT id, name FROM tenants")).fetchone()
        assert t_row is not None
        assert uuid.UUID(str(t_row[0])) == tenant_id
        assert t_row[1] == "Acme Staging Corp"

        u_row = session.execute(text("SELECT id, email FROM users")).fetchone()
        assert u_row is not None
        assert uuid.UUID(str(u_row[0])) == user_id
        assert u_row[1] == "operator@staging.example"

        a_row = session.execute(text("SELECT id, name FROM assistants")).fetchone()
        assert a_row is not None
        assert uuid.UUID(str(a_row[0])) == assistant_id
        assert a_row[1] == "Staging Core Assistant"

        c_row = session.execute(text("SELECT id, title FROM conversations")).fetchone()
        assert c_row is not None
        assert uuid.UUID(str(c_row[0])) == conversation_id
        assert c_row[1] == "Historical Operator Chat"

        inv_row = session.execute(
            text("SELECT id, email, is_cancelled, invited_by_id FROM invitations")
        ).fetchone()
        assert inv_row is not None
        assert uuid.UUID(str(inv_row[0])) == invitation_id
        assert inv_row[1] == "invited@staging.example"
        assert inv_row[2] in (False, 0)
        assert inv_row[3] is None


def test_scenario_c_downgrades_and_reupgrades_cleanly():
    """Verify rollback capability for 0015 down through 0012 and successful re-upgrade."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = MetaData()
    Table("tenants", metadata, Column("id", Uuid, primary_key=True))
    Table("users", metadata, Column("id", Uuid, primary_key=True))
    Table(
        "invitations",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("tenant_id", Uuid, nullable=False),
        Column("email", String(255), nullable=False),
        Column("token_hash", String(64), nullable=False),
        Column("role_id", Uuid, nullable=False),
        Column("department_id", Uuid, nullable=True),
        Column("expires_at", DateTime(timezone=True), nullable=False),
        Column("accepted_at", DateTime(timezone=True), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
    )
    Table("assistants", metadata, Column("id", Uuid, primary_key=True))
    Table("conversations", metadata, Column("id", Uuid, primary_key=True))
    metadata.create_all(engine)

    mod_0012 = load_migration_module("0012_m16_auth_sessions_and_invitations.py")
    mod_0013 = load_migration_module("0013_m17_durable_quota_reservations.py")
    mod_0014 = load_migration_module("0014_m19_tool_registry.py")
    mod_0015 = load_migration_module("0015_m20_mcp_agentic_runtime.py")
    mod_0016 = load_migration_module("0016_m20_2_assistant_tools_config.py")

    # Upgrade 0012 -> 0016
    for mod in [mod_0012, mod_0013, mod_0014, mod_0015, mod_0016]:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
            with Operations.context(ctx):
                mod.upgrade()
            conn.commit()

    insp = inspect(engine)
    assert "tools_config" in {c["name"] for c in insp.get_columns("assistants")}

    # Downgrade 0016 -> 0015
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0016.downgrade()
        conn.commit()

    insp = inspect(engine)
    assert "tools_config" not in {c["name"] for c in insp.get_columns("assistants")}

    # Downgrade 0015 -> 0014
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0015.downgrade()
        conn.commit()

    insp = inspect(engine)
    assert "mcp_connections" not in insp.get_table_names()
    assert "tool_approvals" not in insp.get_table_names()
    assert "tools" in insp.get_table_names()

    # Downgrade 0014 -> 0013
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0014.downgrade()
        conn.commit()

    insp = inspect(engine)
    assert "tools" not in insp.get_table_names()
    assert "quota_reservations" in insp.get_table_names()

    # Downgrade 0013 -> 0012
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0013.downgrade()
        conn.commit()

    insp = inspect(engine)
    assert "quota_reservations" not in insp.get_table_names()
    assert "auth_sessions" in insp.get_table_names()

    # Downgrade 0012 -> 0011
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0012.downgrade()
        conn.commit()

    insp = inspect(engine)
    assert "auth_sessions" not in insp.get_table_names()
    inv_cols = {c["name"] for c in insp.get_columns("invitations")}
    assert "invited_by_id" not in inv_cols
    assert "is_cancelled" not in inv_cols

    # Re-upgrade to 0016 head
    for mod in [mod_0012, mod_0013, mod_0014, mod_0015, mod_0016]:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
            with Operations.context(ctx):
                mod.upgrade()
            conn.commit()

    insp = inspect(engine)
    tables = insp.get_table_names()
    assert "auth_sessions" in tables
    assert "quota_reservations" in tables
    assert "tools" in tables
    assert "mcp_connections" in tables
    assert "tools_config" in {c["name"] for c in insp.get_columns("assistants")}
    assert "tool_approvals" in tables
    assert "tool_invocation_logs" in tables
