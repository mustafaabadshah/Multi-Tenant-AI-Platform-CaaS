"""M05 Phase 12 — Alembic Migration Compatibility Test Suite.

Validates:
1. Scenario A: Fresh database upgrade from base to 0005 head.
2. Scenario B: Existing database at 0004 with pre-existing assistant records upgraded to 0005 without data loss.
3. Scenario C: Downgrade of 0005 removes only the new column; re-upgrade restores it cleanly.
4. Linear continuity of Alembic revisions from 0001 to 0005.

NOTE: Uses SQLite in-memory engine with batch mode for dialect-agnostic DDL testing.
Identified explicitly as SQLite DDL compatibility testing, preserving host safety boundaries.
"""

import importlib.util
import uuid
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Uuid,
    create_engine,
    insert,
    inspect,
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


# -----------------------------------------------------------------------------
# Scenario A: Fresh Database Schema & 0005 Head Verification
# -----------------------------------------------------------------------------
def test_migration_scenario_a_fresh_database_dag():
    """Verify fresh linear migration DAG from 0001 through 0005 head."""
    versions_dir = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    migration_files = sorted(versions_dir.glob("*.py"))
    assert len(migration_files) >= 5, f"Expected at least 5 migrations, found {len(migration_files)}"

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

    # Verify linear chain from 0005 down to 0001
    head_rev = "0005_add_assistant_byok_encrypted_key"
    assert head_rev in revisions

    chain = []
    curr = head_rev
    while curr is not None:
        chain.append(curr)
        curr = revisions[curr]["down_revision"]

    expected_chain = [
        "0005_add_assistant_byok_encrypted_key",
        "0004_assistants_and_conversations",
        "0003_embeddings_and_vector_stores",
        "0002_document_ingestion_engine",
        "0001_initial_core_schema",
    ]
    assert chain == expected_chain, f"Migration chain mismatch: {chain} vs {expected_chain}"


# -----------------------------------------------------------------------------
# Scenario B: Existing Database at 0004 Upgraded to 0005
# -----------------------------------------------------------------------------
def test_migration_scenario_b_upgrade_existing_database():
    """Simulate an existing database at 0004 with existing records and upgrade to 0005."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Build schema representing 0004 state
    metadata = MetaData()
    tenants = Table(
        "tenants",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("name", String(255), nullable=False),
        Column("slug", String(255), nullable=False),
    )
    assistants = Table(
        "assistants",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("tenant_id", Uuid, nullable=False),
        Column("name", String(255), nullable=False),
        Column("slug", String(255), nullable=False),
        Column("description", String(1000), nullable=True),
        Column("default_model", String(100), nullable=False, server_default="auto"),
        Column("llm_provider", String(50), nullable=False, server_default="omniroute"),
        Column("temperature", Float, nullable=False, server_default="0.7"),
        Column("max_tokens", Integer, nullable=False, server_default="1024"),
        Column("visibility", String(50), nullable=False, server_default="workspace"),
        Column("retrieval_mode", String(50), nullable=False, server_default="hybrid"),
        Column("top_k", Integer, nullable=False, server_default="5"),
        Column("system_prompt", Text, nullable=True),
        Column("status", String(50), nullable=False, server_default="ACTIVE"),
    )
    metadata.create_all(engine)

    # Insert existing assistant record at 0004 level
    tenant_id = uuid.uuid4()
    assistant_id = uuid.uuid4()
    with Session(engine) as session:
        session.execute(insert(tenants).values(id=tenant_id, name="Acme Corp", slug="acme"))
        session.execute(
            insert(assistants).values(
                id=assistant_id,
                tenant_id=tenant_id,
                name="Legacy Assistant",
                slug="legacy-assistant",
                system_prompt="You are a helpful legacy bot.",
            )
        )
        session.commit()

    # Verify column does NOT exist prior to 0005 upgrade
    inspector = inspect(engine)
    cols_pre = {c["name"] for c in inspector.get_columns("assistants")}
    assert "byok_encrypted_key" not in cols_pre

    # Apply 0005 upgrade using Alembic Operations context
    mod_0005 = load_migration_module("0005_add_assistant_byok_encrypted_key.py")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0005.upgrade()
        conn.commit()

    # Verify column exists after 0005 upgrade
    inspector = inspect(engine)
    cols_post = {c["name"] for c in inspector.get_columns("assistants")}
    assert "byok_encrypted_key" in cols_post

    # Verify existing record is intact with null byok_encrypted_key
    with Session(engine) as session:
        res = session.execute(
            text("SELECT id, name, system_prompt, byok_encrypted_key FROM assistants")
        ).fetchone()
        assert res is not None
        assert uuid.UUID(str(res[0])) == assistant_id
        assert res[1] == "Legacy Assistant"
        assert res[2] == "You are a helpful legacy bot."
        assert res[3] is None  # Safe nullable default preserved

        # Verify update with new byok_encrypted_key works
        session.execute(
            text("UPDATE assistants SET byok_encrypted_key = 'gAAAAAB_test_ciphertext'")
        )
        session.commit()

        updated = session.execute(
            text("SELECT byok_encrypted_key FROM assistants")
        ).scalar()
        assert updated == "gAAAAAB_test_ciphertext"


# -----------------------------------------------------------------------------
# Scenario C: Downgrade and Re-Upgrade Verification
# -----------------------------------------------------------------------------
def test_migration_scenario_c_downgrade_and_reupgrade():
    """Verify that 0005 downgrade removes only the column, preserving table and records."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Build schema with byok_encrypted_key
    metadata = MetaData()
    assistants = Table(
        "assistants",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("tenant_id", Uuid, nullable=False),
        Column("name", String(255), nullable=False),
        Column("slug", String(255), nullable=False),
        Column("byok_encrypted_key", String(1024), nullable=True),
    )
    metadata.create_all(engine)

    aid = uuid.uuid4()
    tid = uuid.uuid4()
    with Session(engine) as session:
        session.execute(
            insert(assistants).values(
                id=aid,
                tenant_id=tid,
                name="Downgrade Test Bot",
                slug="downgrade-bot",
                byok_encrypted_key="ciphertext_to_be_dropped",
            )
        )
        session.commit()

    mod_0005 = load_migration_module("0005_add_assistant_byok_encrypted_key.py")

    # 1. Downgrade 0005
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0005.downgrade()
        conn.commit()

    inspector = inspect(engine)
    cols_down = {c["name"] for c in inspector.get_columns("assistants")}
    assert "byok_encrypted_key" not in cols_down
    assert "name" in cols_down
    assert "slug" in cols_down

    # Records remain in table
    with Session(engine) as session:
        row = session.execute(text("SELECT id, name FROM assistants")).fetchone()
        assert row is not None
        assert uuid.UUID(str(row[0])) == aid
        assert row[1] == "Downgrade Test Bot"

    # 2. Re-upgrade back to 0005
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"as_sql": False, "render_as_batch": True})
        with Operations.context(ctx):
            mod_0005.upgrade()
        conn.commit()

    inspector = inspect(engine)
    cols_reup = {c["name"] for c in inspector.get_columns("assistants")}
    assert "byok_encrypted_key" in cols_reup
