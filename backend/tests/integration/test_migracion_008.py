"""Migración 008 (C-09): ``odontograma`` y ``evolucion`` append-only. PG16 real, sin datos."""

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from alembic import command
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR

TABLAS = ("odontograma", "evolucion")
TRIGGERS = {f"trg_{t}_append_only_{k}" for t in TABLAS for k in ("row", "truncate")}


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


def test_upgrade_crea_tablas_indices_y_triggers(postgres_url) -> None:  # type: ignore[no-untyped-def]
    assert set(TABLAS) <= _tablas(postgres_url)
    assert TRIGGERS <= _triggers(postgres_url)
    odo = _indices(postgres_url, "odontograma")
    assert "(clinica_id, paciente_id, version)" in odo
    assert "USING gin (piezas jsonb_path_ops)" in odo
    evo = _indices(postgres_url, "evolucion")
    assert "(clinica_id, paciente_id, id DESC)" in evo
    assert "uq_evolucion_corrige_a" in evo and "WHERE (corrige_a_id IS NOT NULL)" in evo
    constraints = set(_all(postgres_url, "SELECT conname FROM pg_constraint"))
    assert {
        "uq_odontograma_clinica_paciente_version",
        "uq_evolucion_clinica_paciente_id",
        "fk_odontograma_paciente",
        "fk_odontograma_autor_usuario_id",
        "fk_evolucion_paciente",
        "fk_evolucion_autor_usuario_id",
        "fk_evolucion_profesional",
        "fk_evolucion_corrige_a",
    } <= constraints


@pytest.mark.parametrize(
    ("tabla", "columna"),
    [("odontograma", "created_at"), ("evolucion", "fecha_hora")],
)
def test_columnas_de_tiempo_son_timestamptz(postgres_url, tabla, columna) -> None:  # type: ignore[no-untyped-def]
    tipo = _all(
        postgres_url,
        "SELECT data_type FROM information_schema.columns "
        f"WHERE table_name='{tabla}' AND column_name='{columna}'",  # noqa: S608
    )
    assert tipo == ["timestamp with time zone"]


def test_checks_de_auditoria_ampliados_con_nombre_real(postgres_url) -> None:  # type: ignore[no-untyped-def]
    entidad = _check_def(postgres_url, "ck_auditoria_hc_entidad_valida")
    accion = _check_def(postgres_url, "ck_auditoria_hc_accion_valida")
    assert "odontograma" in entidad and "evolucion" in entidad
    assert "corregir" in accion


def test_un_unico_head() -> None:
    script = ScriptDirectory(str(BACKEND_DIR / "alembic"))
    # El head vigente lo fija la última migración (ver test_migracion_009); acá solo el encadenado.
    assert "008_odontograma_evolucion" in {r.revision for r in script.walk_revisions()}
    assert len(script.get_heads()) == 1
    assert script.get_revision("008_odontograma_evolucion").down_revision == "006_turno_transicion"


def test_downgrade_borra_conserva_funcion_restaura_checks_y_reupgrade(cfg, postgres_url) -> None:  # type: ignore[no-untyped-def]
    command.downgrade(cfg, "006_turno_transicion")
    try:
        assert not (set(TABLAS) & _tablas(postgres_url))
        assert not (TRIGGERS & _triggers(postgres_url))
        # fn_rechazar_mutacion() es de la 004: sobrevive.
        assert _all(postgres_url, "SELECT 1 FROM pg_proc WHERE proname='fn_rechazar_mutacion'")
        entidad = _check_def(postgres_url, "ck_auditoria_hc_entidad_valida")
        accion = _check_def(postgres_url, "ck_auditoria_hc_accion_valida")
        assert "odontograma" not in entidad and "evolucion" not in entidad
        assert "corregir" not in accion
    finally:
        command.upgrade(cfg, "head")
    assert set(TABLAS) <= _tablas(postgres_url)
    assert TRIGGERS <= _triggers(postgres_url)
    assert "odontograma" in _check_def(postgres_url, "ck_auditoria_hc_entidad_valida")
