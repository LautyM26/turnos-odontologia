"""POST /api/turnos/{id}/transicion (C-05b): un test por escenario de la spec.

PG16 real vía testcontainers; turnos sintéticos en 2031 con reloj fijo (``get_ahora``).
Cada turno usa un día propio para no chocar con las exclusion constraints de otros tests.
Fixtures: P está vinculado a ``odonto@test.test``; Q no tiene usuario (otra agenda).
"""

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.api.turnos import get_ahora
from app.domain.agenda.turnos import Turno, TurnoTransicion
from tests.integration.conftest import bearer, make_test_client

RECEPCION = "recepcion@test.test"
ODONTO = "odonto@test.test"
_dias = itertools.count(0)


def _inicio() -> datetime:
    return datetime(2031, 10, 1, 10, tzinfo=UTC) + timedelta(days=next(_dias))


def _cliente(session_factory, monkeypatch, ahora: datetime):  # type: ignore[no-untyped-def]
    cli = make_test_client(session_factory, monkeypatch)
    cli.app.dependency_overrides[get_ahora] = lambda: ahora
    return cli


def _turno(session_factory, td, estado="reservado", clinica="a", prof=None):  # type: ignore[no-untyped-def]
    """Inserta un turno sintético directo en la base; devuelve (id, inicio)."""
    inicio = _inicio()
    if clinica == "a":
        cols = {"profesional_id": prof or td["p"], "sillon_id": td["s1"],
                "paciente_id": td["pac_a"], "prestacion_id": td["prest_a"]}  # fmt: skip
    else:
        cols = {"profesional_id": td["prof_b"], "sillon_id": td["sillon_b"],
                "paciente_id": td["pac_b"], "prestacion_id": td["prest_b"]}  # fmt: skip
    with session_factory() as session:
        turno = Turno(
            clinica_id=td[clinica], duracion_min=30, inicio=inicio,
            fin=inicio + timedelta(minutes=30), estado=estado, **cols,
        )  # fmt: skip
        session.add(turno)
        session.commit()
        return turno.id, inicio


def _estado(session_factory, turno_id: int) -> str:
    with session_factory() as session:
        return session.scalar(select(Turno.estado).where(Turno.id == turno_id))


def _historial(session_factory, turno_id: int) -> list[TurnoTransicion]:
    with session_factory() as session:
        return list(
            session.scalars(
                select(TurnoTransicion).where(TurnoTransicion.turno_id == turno_id)
            ).all()
        )


def _transicion(cli, headers, turno_id, **body):  # type: ignore[no-untyped-def]
    return cli.post(f"/api/turnos/{turno_id}/transicion", json=body, headers=headers)


@pytest.fixture()
def antes(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    """Cliente con reloj en 2031-01-01: todos los turnos de prueba son futuros."""
    return _cliente(session_factory, monkeypatch, datetime(2031, 1, 1, tzinfo=UTC))


@pytest.fixture()
def despues(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    """Cliente con reloj en 2032: todos los turnos de prueba ya empezaron."""
    return _cliente(session_factory, monkeypatch, datetime(2032, 1, 1, tzinfo=UTC))


# --- Transición de estado explícita (happy path) -----------------------------------------


def test_recepcionista_confirma_un_turno_reservado(antes, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, inicio = _turno(session_factory, turnos_data)
    resp = _transicion(antes, bearer(antes, RECEPCION), turno_id, estado="confirmado")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["estado"] == "confirmado"
    assert body["id"] == turno_id
    assert datetime.fromisoformat(body["inicio"]) == inicio
    assert body["profesional_id"] == turnos_data["p"]


def test_turno_confirmado_pasa_a_asistido(despues, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data, "confirmado")
    resp = _transicion(despues, bearer(despues, RECEPCION), turno_id, estado="asistido")
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "asistido"


def test_turno_reservado_sin_confirmar_pasa_a_ausente(
    despues, session_factory, turnos_data
) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data)
    resp = _transicion(despues, bearer(despues, RECEPCION), turno_id, estado="ausente")
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "ausente"


# --- Transiciones no permitidas (error de negocio) ---------------------------------------


def test_turno_cancelado_no_puede_confirmarse(antes, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data, "cancelado")
    resp = _transicion(antes, bearer(antes, RECEPCION), turno_id, estado="confirmado")
    assert resp.status_code == 422
    assert "cancelado" in resp.json()["detail"]
    assert _estado(session_factory, turno_id) == "cancelado"


def test_asistido_no_vuelve_a_reservado(despues, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data, "asistido")
    resp = _transicion(despues, bearer(despues, RECEPCION), turno_id, estado="reservado")
    assert resp.status_code == 422
    assert _estado(session_factory, turno_id) == "asistido"


def test_repetir_el_estado_actual_422(antes, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data, "confirmado")
    resp = _transicion(antes, bearer(antes, RECEPCION), turno_id, estado="confirmado")
    assert resp.status_code == 422
    assert _historial(session_factory, turno_id) == []


def test_campo_extra_en_el_cuerpo(antes, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data)
    resp = _transicion(
        antes, bearer(antes, RECEPCION), turno_id, estado="confirmado",
        inicio="2031-01-01T10:00:00Z",
    )  # fmt: skip
    assert resp.status_code == 422
    assert _estado(session_factory, turno_id) == "reservado"


# --- Asistencia y ausencia solo desde el inicio (borde) ----------------------------------


def test_ausente_antes_de_la_hora(antes, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data, "confirmado")
    resp = _transicion(antes, bearer(antes, RECEPCION), turno_id, estado="ausente")
    assert resp.status_code == 422
    assert "inicio" in resp.json()["detail"]
    assert _estado(session_factory, turno_id) == "confirmado"


def test_asistido_exactamente_a_la_hora_de_inicio(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, turnos_data
) -> None:
    turno_id, inicio = _turno(session_factory, turnos_data)
    cli = _cliente(session_factory, monkeypatch, inicio)
    resp = _transicion(cli, bearer(cli, RECEPCION), turno_id, estado="asistido")
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "asistido"


def test_confirmar_y_cancelar_no_tienen_ventana_horaria(
    antes, session_factory, turnos_data
) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data)
    headers = bearer(antes, RECEPCION)
    assert _transicion(antes, headers, turno_id, estado="confirmado").status_code == 200
    assert _transicion(antes, headers, turno_id, estado="cancelado").status_code == 200


# --- Historial auditado ------------------------------------------------------------------


def test_transicion_registrada_en_el_historial(  # type: ignore[no-untyped-def]
    antes, session_factory, turnos_data, auth_data
) -> None:
    turno_id, _ = _turno(session_factory, turnos_data)
    resp = _transicion(
        antes, bearer(antes, RECEPCION), turno_id, estado="cancelado",
        motivo="paciente avisó por teléfono",
    )  # fmt: skip
    assert resp.status_code == 200, resp.text
    historial = _historial(session_factory, turno_id)
    assert len(historial) == 1
    fila = historial[0]
    assert (fila.desde, fila.hacia) == ("reservado", "cancelado")
    assert fila.actor_usuario_id == auth_data["user_ids"][RECEPCION]
    assert fila.motivo == "paciente avisó por teléfono"
    assert fila.clinica_id == turnos_data["a"]
    assert fila.created_at.tzinfo is not None
    # Fecha del servidor (now() de PG), no el reloj inyectado de 2031.
    assert abs(fila.created_at - datetime.now(UTC)) < timedelta(minutes=5)


def test_transicion_rechazada_no_deja_historial(antes, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data, "confirmado")
    assert (
        _transicion(antes, bearer(antes, RECEPCION), turno_id, estado="ausente").status_code == 422
    )
    assert (
        _transicion(antes, bearer(antes, ODONTO), turno_id, estado="cancelado").status_code == 403
    )
    assert _historial(session_factory, turno_id) == []


# --- Cancelado libera el hueco -----------------------------------------------------------


def test_reservar_el_hueco_de_un_turno_cancelado(antes, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    turno_id, inicio = _turno(session_factory, td)
    headers = bearer(antes, RECEPCION)
    body = {
        "profesional_id": td["p"], "sillon_id": td["s1"], "paciente_id": td["pac_a"],
        "prestacion_id": td["prest_a"], "inicio": inicio.isoformat(),
    }  # fmt: skip
    assert antes.post("/api/turnos", json=body, headers=headers).status_code == 409
    assert _transicion(antes, headers, turno_id, estado="cancelado").status_code == 200
    assert antes.post("/api/turnos", json=body, headers=headers).status_code == 201


# --- Permisos por rol --------------------------------------------------------------------


def test_odontologo_marca_asistido_en_su_agenda(despues, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data, "confirmado")
    resp = _transicion(despues, bearer(despues, ODONTO), turno_id, estado="asistido")
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "asistido"


def test_odontologo_intenta_confirmar(antes, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data)
    resp = _transicion(antes, bearer(antes, ODONTO), turno_id, estado="confirmado")
    assert resp.status_code == 403
    assert _estado(session_factory, turno_id) == "reservado"


def test_odontologo_sobre_la_agenda_de_otro_profesional(
    despues, session_factory, turnos_data
) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data, "confirmado", prof=turnos_data["q"])
    resp = _transicion(despues, bearer(despues, ODONTO), turno_id, estado="ausente")
    assert resp.status_code == 403
    assert _estado(session_factory, turno_id) == "confirmado"


def test_admin_puede_cualquier_transicion(antes, session_factory, turnos_data, auth_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data)
    resp = _transicion(antes, bearer(antes, auth_data["admin_email"]), turno_id, estado="cancelado")
    assert resp.status_code == 200


def test_sin_autenticacion(antes, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data)
    assert (
        antes.post(f"/api/turnos/{turno_id}/transicion", json={"estado": "confirmado"}).status_code
        == 401
    )


# --- Aislamiento por clínica -------------------------------------------------------------


def test_turno_de_otra_clinica(antes, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_b, _ = _turno(session_factory, turnos_data, clinica="b")
    resp = _transicion(antes, bearer(antes, RECEPCION), turno_b, estado="cancelado")
    assert resp.status_code == 404
    assert _estado(session_factory, turno_b) == "reservado"


def test_turno_inexistente_404(antes) -> None:  # type: ignore[no-untyped-def]
    resp = _transicion(antes, bearer(antes, RECEPCION), 999_999_999, estado="cancelado")
    assert resp.status_code == 404


def test_turno_dado_de_baja_404(antes, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id, _ = _turno(session_factory, turnos_data)
    with session_factory() as session:
        session.get(Turno, turno_id).is_active = False
        session.commit()
    resp = _transicion(antes, bearer(antes, RECEPCION), turno_id, estado="cancelado")
    assert resp.status_code == 404
    with session_factory() as session:
        n = session.scalar(
            select(func.count())
            .select_from(TurnoTransicion)
            .where(TurnoTransicion.turno_id == turno_id)
        )
    assert n == 0
