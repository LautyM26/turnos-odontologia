"""Migración 005 (C-05 recorte): tabla turno + exclusion constraints. PG16 real, sin datos."""

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR


@pytest.fixture()
def cfg(postgres_url):  # type: ignore[no-untyped-def]
    config = Config(ALEMBIC_INI)
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", postgres_url)
    return config


def _scalar(url: str, sql: str, **params):  # type: ignore[no-untyped-def]
    engine = create_engine(url)
    with engine.connect() as conn:
        value = conn.execute(text(sql), params).scalar()
    engine.dispose()
    return value


def _tablas(url: str) -> set[str]:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        ).all()
    engine.dispose()
    return {r[0] for r in rows}


def _constraints(url: str) -> set[str]:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT conname FROM pg_constraint")).all()
    engine.dispose()
    return {r[0] for r in rows}


INDICES = (
    "ON public.turno USING btree (clinica_id, profesional_id, inicio)",
    "ON public.turno USING btree (clinica_id, sillon_id, inicio)",
    "ON public.turno USING btree (clinica_id, paciente_id, inicio)",
    "ON public.turno USING btree (clinica_id, estado)",
)
EXCLUSIONES = ("ex_turno_profesional_rango", "ex_turno_sillon_rango")


def test_upgrade_head_crea_turno_exclusiones_indices_y_uq_prestacion(postgres_url) -> None:  # type: ignore[no-untyped-def]
    assert "turno" in _tablas(postgres_url)
    constraints = _constraints(postgres_url)
    assert set(EXCLUSIONES) <= constraints
    assert "uq_prestacion_clinica_id" in constraints
    defs = _scalar(
        postgres_url, "SELECT string_agg(indexdef, ' | ') FROM pg_indexes WHERE tablename='turno'"
    )
    for fragmento in INDICES:
        assert fragmento in defs, fragmento


def test_exclusiones_son_gist_sobre_rango_y_solo_turnos_activos(postgres_url) -> None:  # type: ignore[no-untyped-def]
    defs = _scalar(
        postgres_url,
        "SELECT string_agg(pg_get_constraintdef(oid), ' | ') FROM pg_constraint "
        "WHERE contype='x' AND conrelid='turno'::regclass",
    )
    assert defs.count("EXCLUDE USING gist") == 2
    assert "clinica_id WITH =, profesional_id WITH =, rango WITH &&" in defs
    assert "clinica_id WITH =, sillon_id WITH =, rango WITH &&" in defs
    assert defs.count("'reservado'") == 2
    assert "sobreturno" not in defs


def test_columnas_de_tiempo_son_timestamptz(postgres_url) -> None:  # type: ignore[no-untyped-def]
    tipos = _scalar(
        postgres_url,
        "SELECT string_agg(column_name || ':' || data_type, ',' ORDER BY column_name) "
        "FROM information_schema.columns WHERE table_name='turno' "
        "AND column_name IN ('inicio','fin','created_at','updated_at','deleted_at')",
    )
    assert tipos.count("timestamp with time zone") == 5


def test_downgrade_elimina_005_y_reupgrade_restaura(cfg, postgres_url) -> None:  # type: ignore[no-untyped-def]
    command.downgrade(cfg, "004_pacientes_ficha")
    try:
        assert "turno" not in _tablas(postgres_url)
        constraints = _constraints(postgres_url)
        assert not ({*EXCLUSIONES, "uq_prestacion_clinica_id"} & constraints)
        # 003/004 intactas, btree_gist se conserva.
        assert {"bloqueo", "paciente", "prestacion"} <= _tablas(postgres_url)
        sql_ext = "SELECT count(*) FROM pg_extension WHERE extname='btree_gist'"
        assert _scalar(postgres_url, sql_ext) == 1
    finally:
        command.upgrade(cfg, "head")
    assert "turno" in _tablas(postgres_url)
    assert {*EXCLUSIONES, "uq_prestacion_clinica_id"} <= _constraints(postgres_url)
