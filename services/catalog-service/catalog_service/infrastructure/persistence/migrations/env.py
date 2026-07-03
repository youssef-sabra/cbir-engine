"""Alembic environment for catalog-service (version table:
alembic_version_catalog — see auth-service's env.py for why per-service
version tables are used against the shared local database)."""

import os

from alembic import context
from sqlalchemy import create_engine, pool

VERSION_TABLE = "alembic_version_catalog"

config = context.config


def _database_url() -> str:
    return os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url") or ""


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), literal_binds=True, version_table=VERSION_TABLE)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, version_table=VERSION_TABLE)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
