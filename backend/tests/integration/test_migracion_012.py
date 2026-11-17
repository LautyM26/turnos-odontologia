"""Migración 012 (C-05d): ``franja_horaria`` y ``clinica.zona_horaria``. PG16 real, sintético."""

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.domain.agenda.models import FranjaHoraria
from app.infrastructure.persistence.repository import BaseRepository
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR

CONSTRAINTS = {
    "pk_franja_horaria",
    "fk_franja_horaria_clinica_id",
    "fk_franja_horaria_profesional",
    "ck_franja_horaria_dia_valido",
    "ck_franja_horaria_rango_valido",
}


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


def _zona(url: str) -> list:
    return _all(
        url,
        "SELECT column_default FROM information_schema.columns "
        "WHERE table_name='clinica' AND column_name='zona_horaria'",
    )


def test_upgrade_crea_tabla_constraints_indice_y_columna(postgres_url) -> None:  # type: ignore[no-untyped-def]
    assert "franja_horaria" in _tablas(postgres_url)
    nombres = set(
        _all(
            postgres_url,
            "SELECT conname FROM pg_constraint WHERE conrelid='franja_horaria'::regclass",
        )
    )
    assert nombres >= CONSTRAINTS
    indices = " | ".join(
        _all(postgres_url, "SELECT indexdef FROM pg_indexes WHERE tablename='franja_horaria'")
    )
    assert "(clinica_id, profesional_id, dia_semana)" in indices
    assert "America/Argentina/Buenos_Aires" in _zona(postgres_url)[0]


@pytest.mark.parametrize(
    ("dia", "ini", "fin"),
    [(1, 600, 600), (1, 700, 600), (1, 0, 1441), (1, -5, 60), (0, 0, 60), (8, 0, 60)],
    ids=["ini_igual_fin", "ini_mayor", "fin_1441", "ini_negativo", "dia_0", "dia_8"],
)
def test_checks_rechazan_franjas_invalidas_23514(  # type: ignore[no-untyped-def]
    session_factory, catalogo_data, dia, ini, fin
) -> None:
    with session_factory() as session:
        session.add(
            FranjaHoraria(
                clinica_id=catalogo_data["a"],
                profesional_id=catalogo_data["prof_p"],
                dia_semana=dia,
                inicio_min=ini,
                fin_min=fin,
            )  # fmt: skip
        )
        with pytest.raises(IntegrityError) as exc:
            session.commit()
        session.rollback()
    assert exc.value.orig.sqlstate == "23514"


def test_franja_de_otra_clinica_no_es_visible(session_factory, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    """Regla dura 10: el repositorio de A no ve franjas de B (0 filas)."""
    with session_factory() as session:
        session.add(
            FranjaHoraria(
                clinica_id=catalogo_data["b"],
                profesional_id=catalogo_data["prof_b"],
                dia_semana=2,
                inicio_min=540,
                fin_min=780,
            )  # fmt: skip
        )
        session.commit()
        assert BaseRepository(session, FranjaHoraria, catalogo_data["a"]).list() == []
        assert len(BaseRepository(session, FranjaHoraria, catalogo_data["b"]).list()) == 1


def test_fk_compuesta_rechaza_profesional_de_otra_clinica_23503(  # type: ignore[no-untyped-def]
    session_factory, catalogo_data
) -> None:
    with session_factory() as session:
        session.add(
            FranjaHoraria(
                clinica_id=catalogo_data["a"],
                profesional_id=catalogo_data["prof_b"],
                dia_semana=1,
                inicio_min=540,
                fin_min=600,
            )  # fmt: skip
        )
        with pytest.raises(IntegrityError) as exc:
            session.commit()
        session.rollback()
    assert exc.value.orig.sqlstate == "23503"


def test_downgrade_a_011_y_reupgrade(cfg, postgres_url) -> None:  # type: ignore[no-untyped-def]
    with create_engine(postgres_url).begin() as conn:  # sin filas: el downgrade borra la tabla
        conn.execute(text("DELETE FROM franja_horaria"))
    command.downgrade(cfg, "011_sobreturno_huecos")
    try:
        assert "franja_horaria" not in _tablas(postgres_url)
        assert _zona(postgres_url) == []
    finally:
        command.upgrade(cfg, "head")
    assert "franja_horaria" in _tablas(postgres_url)
    assert _zona(postgres_url)


def test_un_unico_head_y_012_encadenada_a_la_011() -> None:
    script = ScriptDirectory(str(BACKEND_DIR / "alembic"))
    assert len(script.get_heads()) == 1
    assert script.get_revision("012_horario_atencion").down_revision == "011_sobreturno_huecos"
