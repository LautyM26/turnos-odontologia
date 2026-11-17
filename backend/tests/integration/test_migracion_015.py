"""Migración 015 (C-16): lista de espera y ofertas. PG16 real, sintético."""

from datetime import UTC, datetime, timedelta
from itertools import count

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.domain.agenda.turnos import Turno
from app.domain.lista_espera.models import ListaEspera, OfertaListaEspera
from tests.integration.conftest import ALEMBIC_INI, BACKEND_DIR, paciente_sintetico

TEXTOS = {"recordatorio_24h", "confirmacion", "cancelacion", "reprogramacion", "oferta_hueco",
          "oferta_aceptada", "oferta_no_disponible"}  # fmt: skip
_dia = count(1)


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


def _paciente(session_factory, clinica_id: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        p = paciente_sintetico(clinica_id)
        s.add(p)
        s.commit()
        return p.id


def _cancelado(session_factory, td, clinica: str = "a") -> int:  # type: ignore[no-untyped-def]
    inicio = datetime(2035, 1, 1, 10, tzinfo=UTC) + timedelta(days=next(_dia))
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


def _entrada(td, paciente_id: int, **kw) -> ListaEspera:  # type: ignore[no-untyped-def]
    cols = {"clinica_id": td["a"], "paciente_id": paciente_id, "prestacion_id": td["prest_a"]}
    cols.update(kw)
    return ListaEspera(**cols)


def _guardar(session_factory, obj):  # type: ignore[no-untyped-def]
    with session_factory() as s:
        s.add(obj)
        s.commit()
        return obj.id


def _oferta(td, entrada_id: int, turno_id: int, **kw) -> OfertaListaEspera:  # type: ignore[no-untyped-def]
    inicio = datetime(2035, 6, 1, 10, tzinfo=UTC)
    cols = {"clinica_id": td["a"], "lista_espera_id": entrada_id, "turno_liberado_id": turno_id,
            "inicio": inicio, "fin": inicio + timedelta(minutes=30), "profesional_id": td["p"],
            "sillon_id": td["s1"], "prestacion_id": td["prest_a"],
            "expira_at": inicio - timedelta(hours=3)}  # fmt: skip
    cols.update(kw)
    return OfertaListaEspera(**cols)


def test_tablas_indices_y_textos(postgres_url) -> None:  # type: ignore[no-untyped-def]
    tablas = set(_all(postgres_url, "SELECT tablename FROM pg_tables WHERE schemaname='public'"))
    assert {"lista_espera", "oferta_lista_espera"} <= tablas
    assert set(_all(postgres_url, "SELECT clave FROM plantilla_wa")) == TEXTOS
    indices = set(_all(postgres_url, "SELECT indexname FROM pg_indexes"))
    assert {"ix_lista_espera_cola", "uq_lista_espera_activa", "uq_oferta_pendiente_por_hueco",
            "uq_oferta_pendiente_por_entrada"} <= indices  # fmt: skip


def test_entrada_valida_y_defaults(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    pid = _paciente(session_factory, turnos_data["a"])
    with session_factory() as s:
        e = _entrada(turnos_data, pid)
        s.add(e)
        s.commit()
        s.refresh(e)
        assert (e.estado, e.prioridad) == ("en_cola", 0)


@pytest.mark.parametrize("over", [{"estado": "volando"}, {"prioridad": 11}, {"prioridad": -1}],
                         ids=["estado", "prioridad_alta", "prioridad_negativa"])  # fmt: skip
def test_checks_de_entrada(session_factory, turnos_data, over) -> None:  # type: ignore[no-untyped-def]
    pid = _paciente(session_factory, turnos_data["a"])
    _falla(session_factory, _entrada(turnos_data, pid, **over), "23514")


def test_entrada_activa_duplicada_23505(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    pid = _paciente(session_factory, turnos_data["a"])
    _guardar(session_factory, _entrada(turnos_data, pid))
    _guardar(session_factory, _entrada(turnos_data, pid, estado="salido"))  # inactiva convive
    _falla(session_factory, _entrada(turnos_data, pid), "23505")


def test_referencias_de_otra_clinica_23503(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    pid = _paciente(session_factory, turnos_data["a"])
    _falla(session_factory, _entrada(turnos_data, pid, prestacion_id=turnos_data["prest_b"]),
           "23503")  # fmt: skip
    t_b = _cancelado(session_factory, turnos_data, "b")
    _falla(session_factory, _entrada(turnos_data, pid, turno_a_adelantar_id=t_b), "23503")


def test_unicidades_de_ofertas(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    e1 = _guardar(session_factory, _entrada(td, _paciente(session_factory, td["a"])))
    e2 = _guardar(session_factory, _entrada(td, _paciente(session_factory, td["a"])))
    hueco, otro = _cancelado(session_factory, td), _cancelado(session_factory, td)
    _guardar(session_factory, _oferta(td, e1, hueco))
    _falla(session_factory, _oferta(td, e2, hueco), "23505")  # 2 pendientes por hueco
    _falla(session_factory, _oferta(td, e1, otro), "23505")  # 2 pendientes por entrada
    with session_factory() as s:
        s.execute(text("UPDATE oferta_lista_espera SET estado='expirada' WHERE lista_espera_id=:e"),
                  {"e": e1})  # fmt: skip
        s.commit()
    _falla(session_factory, _oferta(td, e1, hueco), "23505")  # mismo hueco, misma entrada
    _guardar(session_factory, _oferta(td, e2, hueco))  # el hueco rota a otra entrada


def test_checks_de_oferta(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    e = _guardar(session_factory, _entrada(td, _paciente(session_factory, td["a"])))
    hueco = _cancelado(session_factory, td)
    _falla(session_factory, _oferta(td, e, hueco, estado="volando"), "23514")
    _falla(session_factory, _oferta(td, e, hueco, turno_creado_id=hueco), "23514")  # sin aceptar


def test_un_unico_head_y_015_encadenada_a_la_014() -> None:
    script = ScriptDirectory(str(BACKEND_DIR / "alembic"))
    assert len(script.get_heads()) == 1
    assert script.get_revision("015_lista_espera").down_revision == "014_whatsapp"


def test_downgrade_a_014_y_reupgrade_en_base_limpia() -> None:
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("+psycopg2", "+psycopg")
        config = Config(ALEMBIC_INI)
        config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        command.downgrade(config, "014_whatsapp")
        tablas = set(_all(url, "SELECT tablename FROM pg_tables WHERE schemaname='public'"))
        assert not {"lista_espera", "oferta_lista_espera"} & tablas
        assert len(_all(url, "SELECT clave FROM plantilla_wa")) == 5
        command.upgrade(config, "head")
        assert set(_all(url, "SELECT clave FROM plantilla_wa")) == TEXTOS
