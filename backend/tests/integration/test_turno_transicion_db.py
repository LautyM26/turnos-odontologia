"""Historial ``turno_transicion`` en la base (C-05b): inmutable, por tenant. PG16 real.

Escenario de la spec: "Historial inmutable". Datos sintéticos, fechas 2031 (reglas 9 y 14).
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.domain.agenda.turnos import Turno, TurnoTransicion
from app.infrastructure.persistence.repository import BaseRepository


def _turno(session, td, clinica: str = "a"):  # type: ignore[no-untyped-def]
    inicio = datetime(2031, 9, 1, 10, tzinfo=UTC)
    cols = (
        {"profesional_id": td["p"], "sillon_id": td["s1"], "paciente_id": td["pac_a"],
         "prestacion_id": td["prest_a"]}
        if clinica == "a"
        else {"profesional_id": td["prof_b"], "sillon_id": td["sillon_b"],
              "paciente_id": td["pac_b"], "prestacion_id": td["prest_b"]}
    )  # fmt: skip
    turno = Turno(
        clinica_id=td[clinica], duracion_min=30, inicio=inicio + timedelta(days=_turno.n),
        fin=inicio + timedelta(days=_turno.n, minutes=30), estado="reservado", **cols,
    )  # fmt: skip
    _turno.n += 1
    session.add(turno)
    session.flush()
    return turno


_turno.n = 0  # type: ignore[attr-defined]


@pytest.fixture()
def fila(session_factory, auth_data, turnos_data):  # type: ignore[no-untyped-def]
    """Un turno de A con una transición registrada."""
    actor = auth_data["user_ids"]["recepcion@test.test"]
    with session_factory() as session:
        turno = _turno(session, turnos_data)
        tr = TurnoTransicion(
            clinica_id=turnos_data["a"], turno_id=turno.id, desde="reservado",
            hacia="cancelado", actor_usuario_id=actor, motivo="motivo sintetico",
        )  # fmt: skip
        session.add(tr)
        session.commit()
        return {"id": tr.id, "turno_id": turno.id}


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE turno_transicion SET hacia='confirmado' WHERE id=:id",
        "DELETE FROM turno_transicion WHERE id=:id",
        "TRUNCATE turno_transicion",
    ],
)
def test_update_delete_truncate_rechazados(session_factory, fila, sql) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        with pytest.raises(DBAPIError) as exc:
            session.execute(text(sql), {"id": fila["id"]})
        session.rollback()
    assert "append-only" in str(exc.value)
    with session_factory() as session:
        hacia = session.execute(
            text("SELECT hacia FROM turno_transicion WHERE id=:id"), {"id": fila["id"]}
        ).scalar()
    assert hacia == "cancelado"


def test_fk_compuesta_rechaza_turno_de_otra_clinica(  # type: ignore[no-untyped-def]
    session_factory, auth_data, turnos_data
) -> None:
    with session_factory() as session:
        turno_b = _turno(session, turnos_data, "b")
        session.commit()
        session.add(
            TurnoTransicion(
                clinica_id=turnos_data["a"],
                turno_id=turno_b.id,
                desde="reservado",
                hacia="cancelado",
                actor_usuario_id=auth_data["user_ids"]["recepcion@test.test"],
            )  # fmt: skip
        )
        with pytest.raises(IntegrityError) as exc:
            session.flush()
        session.rollback()
    assert exc.value.orig.sqlstate == "23503"


@pytest.mark.parametrize("cambio", [{"hacia": "inventado"}, {"motivo": "x" * 501}])
def test_checks_rechazan_valores_invalidos(  # type: ignore[no-untyped-def]
    session_factory, auth_data, turnos_data, cambio
) -> None:
    with session_factory() as session:
        turno = _turno(session, turnos_data)
        cols = {
            "clinica_id": turnos_data["a"], "turno_id": turno.id, "desde": "reservado",
            "hacia": "cancelado", "actor_usuario_id": auth_data["user_ids"]["recepcion@test.test"],
        }  # fmt: skip
        cols.update(cambio)
        session.add(TurnoTransicion(**cols))
        with pytest.raises(IntegrityError) as exc:
            session.flush()
        session.rollback()
    assert exc.value.orig.sqlstate == "23514"


def test_repositorio_de_otra_clinica_no_ve_el_historial(  # type: ignore[no-untyped-def]
    session_factory, fila, turnos_data
) -> None:
    """Sin ``is_active`` (inmutable): se consulta con ``include_inactive=True``."""
    with session_factory() as session:
        ajeno = BaseRepository(session, TurnoTransicion, turnos_data["b"])
        propio = BaseRepository(session, TurnoTransicion, turnos_data["a"])
        assert ajeno.get(fila["id"], include_inactive=True) is None
        assert propio.get(fila["id"], include_inactive=True) is not None
