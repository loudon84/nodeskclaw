import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import alembic_context_version_options, alembic_schema_name, ALEMBIC_VERSION_NUM_LENGTH, settings  # noqa: E402
from app.db_metadata import agent_metadata  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = agent_metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **alembic_context_version_options(),
    )

    with context.begin_transaction():
        context.run_migrations()


def _ensure_agent_schema_and_version_table(connection: Connection) -> None:
    schema = alembic_schema_name()
    connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    connection.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS "{schema}".alembic_version (
                version_num VARCHAR({ALEMBIC_VERSION_NUM_LENGTH}) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            )
            """
        )
    )
    connection.execute(
        text(
            f"""
            ALTER TABLE "{schema}".alembic_version
            ALTER COLUMN version_num TYPE VARCHAR({ALEMBIC_VERSION_NUM_LENGTH})
            """
        )
    )
    connection.commit()


def do_run_migrations(connection: Connection) -> None:
    _ensure_agent_schema_and_version_table(connection)
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        **alembic_context_version_options(),
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
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
