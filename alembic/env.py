import sys
from pathlib import Path

from dotenv import load_dotenv

# First, try to load .env.local (for local launch)
# If it's not there, load .env (for Docker and as a fallback)
env_local_path = Path(__file__).parent.parent / ".env.local"
if env_local_path.exists():
    load_dotenv(dotenv_path=env_local_path)
else:
    load_dotenv()

sys.path.append(str(Path(__file__).parent.parent))

from aiogram_bot_template.db.models import Base

import os
import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Main migration logic."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations(connectable) -> None:
    """Utility function to run migrations in an async context."""
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Read the URL directly from the environment variable.
    db_url = os.getenv("DB__PG_LINK")

    if not db_url:
        # Fallback to alembic.ini for local development without Docker
        print("DB__PG_LINK not found in environment, falling back to alembic.ini")
        db_url = config.get_main_option("sqlalchemy.url")

    if not db_url:
        raise ValueError(
            "Database URL not found. Set DB__PG_LINK environment variable or configure sqlalchemy.url in alembic.ini"
        )

    connectable = create_async_engine(db_url)
    asyncio.run(run_async_migrations(connectable))


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
