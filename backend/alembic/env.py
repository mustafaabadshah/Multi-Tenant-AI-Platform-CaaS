import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings
from app.models import Base

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.DATABASE_SYNC_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _ensure_version_table_capacity(connection: Connection) -> None:
    """Widen alembic_version.version_num on PostgreSQL.

    Alembic creates the version table with VARCHAR(32), but several revision IDs in
    this repository are longer than 32 characters. Pre-create the table when absent
    and widen an existing one; both statements are idempotent. SQLite is untouched.
    """
    if connection.dialect.name != "postgresql":
        return
    # Commit this DDL immediately so Alembic's own migration transaction still owns
    # (and commits) the migration work instead of inheriting an implicit transaction.
    with connection.begin():
        connection.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS alembic_version ("
            "version_num VARCHAR(255) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        )
        connection.exec_driver_sql(
            "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255)"
        )


def do_run_migrations(connection: Connection) -> None:
    # Must run before context.configure so Alembic finds a sufficiently wide version table.
    _ensure_version_table_capacity(connection)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    override_url = config.get_main_option("sqlalchemy.url")
    target_url = override_url or settings.DATABASE_URL
    if target_url.startswith("sqlite:///") and not target_url.startswith("sqlite+aiosqlite:///"):
        target_url = target_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    configuration["sqlalchemy.url"] = target_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
