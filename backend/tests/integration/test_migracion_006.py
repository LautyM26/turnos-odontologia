"""Migración 006 (C-05b): historial append-only ``turno_transicion``. PG16 real, sin datos."""

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR

TRIGGERS = ("trg_turno_transicion_append_only_row", "trg_turno_transicion_append_only_truncate")


@pytest.fixture()
def cfg(postgres_url):  # type: ignore[no-untyped-def]
    config = Config(ALEMBIC_INI)
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    return config


def _all(url: str, sql: str) -> list:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = [r[0] for r in conn.execute(text(sql)).all()]
    engine.dispose()
    return rows


def _tablas(url: str) -> set[str]:
    return set(
        _all(url, "SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    )


def _triggers(url: str) -> set[str]:
    return set(_all(url, "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"))


def _funcion_existe(url: str) -> bool:
    return bool(_all(url, "SELECT 1 FROM pg_proc WHERE proname='fn_rechazar_mutacion'"))


def test_upgrade_crea_tabla_indice_constraints_y_triggers(postgres_url) -> None:  # type: ignore[no-untyped-def]
    assert "turno_transicion" in _tablas(postgres_url)
    assert set(TRIGGERS) <= _triggers(postgres_url)
    indices = " | ".join(
        _all(postgres_url, "SELECT indexdef FROM pg_indexes WHERE tablename='turno_transicion'")
    )
    assert "(clinica_id, turno_id, id)" in indices
    constraints = set(_all(postgres_url, "SELECT conname FROM pg_constraint"))
    assert {
        "uq_turno_clinica_id",
        "fk_turno_transicion_turno",
        "fk_turno_transicion_actor_usuario_id",
        "fk_turno_transicion_clinica_id",
    } <= constraints


def test_created_at_es_timestamptz(postgres_url) -> None:  # type: ignore[no-untyped-def]
    tipo = _all(
        postgres_url,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name='turno_transicion' AND column_name='created_at'",
    )
    assert tipo == ["timestamp with time zone"]


def test_downgrade_elimina_006_conserva_funcion_y_reupgrade_restaura(cfg, postgres_url) -> None:  # type: ignore[no-untyped-def]
    command.downgrade(cfg, "005_turnos")
    try:
        assert "turno_transicion" not in _tablas(postgres_url)
        assert not (set(TRIGGERS) & _triggers(postgres_url))
        assert "uq_turno_clinica_id" not in set(
            _all(postgres_url, "SELECT conname FROM pg_constraint")
        )
        assert "turno" in _tablas(postgres_url)
        assert _funcion_existe(postgres_url)  # pertenece a la 004
    finally:
        command.upgrade(cfg, "head")
    assert "turno_transicion" in _tablas(postgres_url)
    assert set(TRIGGERS) <= _triggers(postgres_url)
