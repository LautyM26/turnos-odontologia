"""Migración 011 (C-05c): marca de sobreturno y exclusion constraints sin sobreturnos. PG16 real."""

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR

CHECKS = {"ck_turno_sobreturno_coherente", "ck_turno_motivo_sobreturno_largo"}


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


def _columnas(url: str) -> dict[str, str]:
    filas = _all(
        url,
        "SELECT column_name || ':' || data_type || ':' || is_nullable "
        "FROM information_schema.columns WHERE table_name='turno' "
        "AND column_name IN ('es_sobreturno','motivo_sobreturno')",
    )
    return {f.split(":")[0]: f for f in filas}


def _checks(url: str) -> set[str]:
    return set(_all(url, "SELECT conname FROM pg_constraint WHERE conrelid='turno'::regclass"))


def _exclusiones(url: str) -> list[str]:
    return _all(
        url,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE contype='x' AND conrelid='turno'::regclass",
    )


def test_upgrade_agrega_columnas_checks_y_predicado_sin_sobreturnos(postgres_url) -> None:  # type: ignore[no-untyped-def]
    cols = _columnas(postgres_url)
    assert cols["es_sobreturno"] == "es_sobreturno:boolean:NO"
    assert cols["motivo_sobreturno"] == "motivo_sobreturno:text:YES"
    assert CHECKS <= _checks(postgres_url)
    defs = _exclusiones(postgres_url)
    assert len(defs) == 2
    assert all("NOT es_sobreturno" in d for d in defs)


def test_downgrade_a_010_y_reupgrade(cfg, postgres_url) -> None:  # type: ignore[no-untyped-def]
    command.downgrade(cfg, "010_recetas_externas")
    try:
        assert _columnas(postgres_url) == {}
        assert not (CHECKS & _checks(postgres_url))
        defs = _exclusiones(postgres_url)
        assert len(defs) == 2
        assert not any("es_sobreturno" in d for d in defs)
    finally:
        command.upgrade(cfg, "head")
    assert all("NOT es_sobreturno" in d for d in _exclusiones(postgres_url))


def test_un_unico_head_encadenado_a_la_010() -> None:
    from alembic.script import ScriptDirectory

    script = ScriptDirectory(str(BACKEND_DIR / "alembic"))
    assert script.get_heads() == ["011_sobreturno_huecos"]
    assert script.get_revision("011_sobreturno_huecos").down_revision == "010_recetas_externas"
