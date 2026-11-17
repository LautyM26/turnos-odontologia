"""Migración 016 (C-17): conversación del chatbot y textos base. PG16 real, sintético."""

from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.domain.agenda.turnos import Turno
from app.domain.reprogramacion.models import ConversacionWA
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR

NUEVOS = {"reprogramacion_opciones", "reprogramacion_confirmar", "reprogramacion_hecha",
          "reprogramacion_sin_cambios", "reprogramacion_vencida"}  # fmt: skip


def _all(url: str, sql: str) -> list:
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = [r[0] for r in conn.execute(text(sql)).all()]
    engine.dispose()
    return rows


def _falla(session_factory, obj, sqlstate: str) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        session.add(obj)
        with pytest.raises(IntegrityError) as exc:
            session.commit()
        session.rollback()
    assert exc.value.orig.sqlstate == sqlstate


def _turno(session_factory, td, clinica: str = "a") -> int:  # type: ignore[no-untyped-def]
    inicio = datetime(2037, 1, 5, 10, tzinfo=UTC)
    if clinica == "a":
        refs = {"profesional_id": td["p"], "sillon_id": td["s1"], "paciente_id": td["pac_a"],
                "prestacion_id": td["prest_a"]}  # fmt: skip
    else:
        refs = {"profesional_id": td["prof_b"], "sillon_id": td["sillon_b"],
                "paciente_id": td["pac_b"], "prestacion_id": td["prest_b"]}  # fmt: skip
    with session_factory() as s:
        t = Turno(clinica_id=td[clinica], duracion_min=30, inicio=inicio, estado="cancelado",
                  fin=inicio + timedelta(minutes=30), **refs)  # fmt: skip
        s.add(t)
        s.commit()
        return t.id


def _conv(td, turno_id: int, tel: str = "+5491100000101", **kw) -> ConversacionWA:  # type: ignore[no-untyped-def]
    cols = {"clinica_id": td["a"], "paciente_id": td["pac_a"], "telefono": tel,
            "turno_id": turno_id, "opciones": [], "expira_at": datetime(2037, 1, 1, tzinfo=UTC)}
    cols.update(kw)
    return ConversacionWA(**cols)


def test_tabla_indice_y_textos(postgres_url) -> None:  # type: ignore[no-untyped-def]
    assert "conversacion_wa" in _all(
        postgres_url, "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    )
    claves = set(_all(postgres_url, "SELECT clave FROM plantilla_wa"))
    assert len(claves) == 12 and NUEVOS <= claves
    assert "uq_conversacion_wa_abierta" in _all(postgres_url, "SELECT indexname FROM pg_indexes")


@pytest.mark.parametrize(
    "over",
    [{"estado": "volando"}, {"estado": "cerrada"}, {"resultado": "reprogramado"},
     {"estado": "cerrada", "resultado": "otro"}, {"opciones": {"no": "lista"}}],
    ids=["estado", "cerrada_sin_resultado", "resultado_abierta", "resultado", "opciones"],
)  # fmt: skip
def test_checks(session_factory, turnos_data, over) -> None:  # type: ignore[no-untyped-def]
    _falla(session_factory, _conv(turnos_data, _turno(session_factory, turnos_data), **over),
           "23514")  # fmt: skip


def test_una_abierta_por_numero(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    tid = _turno(session_factory, td)
    with session_factory() as s:
        s.add(_conv(td, tid, tel="+5491100000102", estado="cerrada", resultado="sin_cambios"))
        s.add(_conv(td, tid, tel="+5491100000102"))  # una cerrada convive con una abierta
        s.commit()
    _falla(session_factory, _conv(td, tid, tel="+5491100000102"), "23505")


def test_turno_de_otra_clinica_23503(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    _falla(session_factory, _conv(turnos_data, _turno(session_factory, turnos_data, "b"),
                                  tel="+5491100000103"), "23503")  # fmt: skip


def test_un_unico_head_y_016_encadenada_a_la_015() -> None:
    script = ScriptDirectory(str(BACKEND_DIR / "alembic"))
    assert len(script.get_heads()) == 1
    assert script.get_revision("016_reprogramacion").down_revision == "015_lista_espera"


def test_downgrade_a_015_y_reupgrade_en_base_limpia() -> None:
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("+psycopg2", "+psycopg")
        config = Config(ALEMBIC_INI)
        config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        command.downgrade(config, "015_lista_espera")
        assert "conversacion_wa" not in _all(
            url, "SELECT tablename FROM pg_tables WHERE schemaname='public'"
        )
        assert len(_all(url, "SELECT clave FROM plantilla_wa")) == 7
        command.upgrade(config, "head")
        assert NUEVOS <= set(_all(url, "SELECT clave FROM plantilla_wa"))
