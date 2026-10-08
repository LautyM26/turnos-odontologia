"""Alembic environment. Reads DATABASE_URL from settings (never hardcoded)."""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
for path in (ROOT_DIR, BACKEND_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _database_url() -> str:
    override = config.get_main_option("sqlalchemy.url")
    if override:
        return override
    try:
        from app.infrastructure.settings import Settings
    except ImportError:
        from backend.app.infrastructure.settings import Settings

    return Settings().database_url


target_metadata = None

try:  # C-02: metadata core para `alembic check` y autogenerate-compare.
    from app.domain.auth.models import TokenBlacklist  # noqa: F401
    from app.domain.core.models import Clinica, Rol, Usuario, UsuarioRol  # noqa: F401
    from app.infrastructure.persistence.base import Base

    target_metadata = Base.metadata
except ImportError:  # pragma: no cover - pre-C-02 fallback
    target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    context.configure(url=_database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
