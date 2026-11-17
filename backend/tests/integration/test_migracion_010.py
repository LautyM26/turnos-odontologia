"""Migración 010 (C-19): receta_externa inmutable y CHECK de auditoría con 'receta'. PG16 real."""

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from alembic import command
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR

TRIGGERS = {"trg_receta_externa_append_only_row", "trg_receta_externa_append_only_truncate"}


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


def _indices(url: str, tabla: str) -> str:
    return " | ".join(
        _all(url, f"SELECT indexdef FROM pg_indexes WHERE tablename='{tabla}'")  # noqa: S608
    )


def _check_def(url: str, nombre: str) -> str:
    filas = _all(
        url,
        f"SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname='{nombre}'",  # noqa: S608
    )
    assert len(filas) == 1, f"constraint {nombre} no encontrada (o duplicada)"
    return filas[0]


def test_upgrade_crea_tabla_indices_constraints_y_triggers(postgres_url) -> None:  # type: ignore[no-untyped-def]
    assert "receta_externa" in _tablas(postgres_url)
    assert TRIGGERS <= _triggers(postgres_url)
    idx = _indices(postgres_url, "receta_externa")
    assert "(clinica_id, paciente_id, id DESC)" in idx
    assert "UNIQUE" in idx and "(clinica_id, clave_idempotencia)" in idx
    assert "(clinica_id, partner, id_externo)" in idx
    constraints = set(_all(postgres_url, "SELECT conname FROM pg_constraint"))
    assert {
        "fk_receta_externa_evolucion",
        "fk_receta_externa_paciente",
        "fk_receta_externa_autor_usuario_id",
        "fk_receta_externa_profesional",
    } <= constraints
    fk = _check_def(postgres_url, "fk_receta_externa_evolucion")
    assert "evolucion" in fk and "clinica_id" in fk and "paciente_id" in fk


def test_emitida_en_es_timestamptz(postgres_url) -> None:  # type: ignore[no-untyped-def]
    tipo = _all(
        postgres_url,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name='receta_externa' AND column_name='emitida_en'",
    )
    assert tipo == ["timestamp with time zone"]


def test_check_de_auditoria_hc_incluye_receta(postgres_url) -> None:  # type: ignore[no-untyped-def]
    entidad = _check_def(postgres_url, "ck_auditoria_hc_entidad_valida")
    accion = _check_def(postgres_url, "ck_auditoria_hc_accion_valida")
    assert "receta" in entidad and "consentimiento" in entidad and "evolucion" in entidad
    assert "firmar" in accion and "corregir" in accion


def test_un_unico_head_y_encadenado_a_la_009() -> None:
    script = ScriptDirectory(str(BACKEND_DIR / "alembic"))
    assert len(script.get_heads()) == 1  # un único head; la 011 (C-05c) se encadena después
    assert script.get_revision("010_recetas_externas").down_revision == (
        "009_consentimientos_cumplimiento"
    )


def test_downgrade_borra_conserva_funcion_restaura_check_y_reupgrade(cfg, postgres_url) -> None:  # type: ignore[no-untyped-def]
    command.downgrade(cfg, "009_consentimientos_cumplimiento")
    try:
        assert "receta_externa" not in _tablas(postgres_url)
        assert not (TRIGGERS & _triggers(postgres_url))
        assert _all(postgres_url, "SELECT 1 FROM pg_proc WHERE proname='fn_rechazar_mutacion'")
        entidad = _check_def(postgres_url, "ck_auditoria_hc_entidad_valida")
        assert "receta" not in entidad and "consentimiento" in entidad
    finally:
        command.upgrade(cfg, "head")
    assert "receta_externa" in _tablas(postgres_url)
    assert TRIGGERS <= _triggers(postgres_url)
    assert "receta" in _check_def(postgres_url, "ck_auditoria_hc_entidad_valida")
