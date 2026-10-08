"""Migración 003 (C-04): tablas de catálogo, btree_gist y uq_usuario_clinica_id."""

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR

TABLAS = ("profesional", "sillon_recurso", "prestacion", "profesional_sillon", "bloqueo")


@pytest.fixture()
def cfg(postgres_url):  # type: ignore[no-untyped-def]
    config = Config(ALEMBIC_INI)
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    return config


def _tablas(url: str) -> set[str]:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        ).all()
    engine.dispose()
    return {r[0] for r in rows}


def _scalar(url: str, sql: str):  # type: ignore[no-untyped-def]
    engine = create_engine(url)
    with engine.connect() as conn:
        value = conn.execute(text(sql)).scalar()
    engine.dispose()
    return value


def test_upgrade_head_crea_catalogo_extension_y_unique(postgres_url) -> None:  # type: ignore[no-untyped-def]
    assert set(TABLAS) <= _tablas(postgres_url)
    ext_sql = "SELECT count(*) FROM pg_extension WHERE extname='btree_gist'"
    assert _scalar(postgres_url, ext_sql) == 1
    assert (
        _scalar(
            postgres_url,
            "SELECT count(*) FROM pg_constraint WHERE conname='uq_usuario_clinica_id'",
        )
        == 1
    )


def test_downgrade_elimina_y_reupgrade_restaura(cfg, postgres_url) -> None:  # type: ignore[no-untyped-def]
    command.downgrade(cfg, "002_token_blacklist")
    try:
        assert not set(TABLAS) & _tablas(postgres_url)
        assert (
            _scalar(
                postgres_url,
                "SELECT count(*) FROM pg_constraint WHERE conname='uq_usuario_clinica_id'",
            )
            == 0
        )
        assert "usuario" in _tablas(postgres_url)
    finally:
        command.upgrade(cfg, "head")
    assert set(TABLAS) <= _tablas(postgres_url)
