"""Transiciones concurrentes sobre el mismo turno (C-05b D5): se serializan por bloqueo de fila.

Escenario de la spec "Dos cancelaciones simultáneas". Mismo patrón que
``test_turnos_concurrencia.py``: un TestClient por pedido y una ``threading.Barrier``.
"""

import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.api.turnos import get_ahora
from app.domain.agenda.servicio import ReferenciaInvalida
from app.domain.agenda.turnos import Turno, TurnoTransicion, transicionar_turno
from tests.integration.conftest import bearer, make_test_client

RECEPCION = "recepcion@test.test"
AHORA = datetime(2031, 1, 1, tzinfo=UTC)


def _turno(session_factory, td, inicio: datetime) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        turno = Turno(
            clinica_id=td["a"], profesional_id=td["p"], sillon_id=td["s2"],
            paciente_id=td["pac_a"], prestacion_id=td["prest_a"], duracion_min=30,
            inicio=inicio, fin=inicio + timedelta(minutes=30), estado="reservado",
        )  # fmt: skip
        session.add(turno)
        session.commit()
        return turno.id


def _disparar(session_factory, monkeypatch, turno_id: int, bodies: list[dict]):  # type: ignore[no-untyped-def]
    headers = bearer(make_test_client(session_factory, monkeypatch), RECEPCION)
    clientes = []
    for _ in bodies:
        cli = make_test_client(session_factory, monkeypatch)
        cli.app.dependency_overrides[get_ahora] = lambda: AHORA
        clientes.append(cli)
    barrera = threading.Barrier(len(bodies))

    def _una(cli, body):  # type: ignore[no-untyped-def]
        barrera.wait(timeout=30)
        return cli.post(f"/api/turnos/{turno_id}/transicion", json=body, headers=headers)

    with ThreadPoolExecutor(max_workers=len(bodies)) as pool:
        return list(pool.map(_una, clientes, bodies))


def _resultado(session_factory, turno_id: int) -> tuple[str, int]:
    with session_factory() as session:
        estado = session.scalar(select(Turno.estado).where(Turno.id == turno_id))
        filas = session.scalar(
            select(func.count())
            .select_from(TurnoTransicion)
            .where(TurnoTransicion.turno_id == turno_id)
        )
    return estado, int(filas)


def test_dos_cancelaciones_simultaneas(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    turno_id = _turno(session_factory, turnos_data, datetime(2031, 11, 3, 10, tzinfo=UTC))
    respuestas = _disparar(session_factory, monkeypatch, turno_id, [{"estado": "cancelado"}] * 2)
    assert Counter(r.status_code for r in respuestas) == Counter({200: 1, 422: 1}), [
        r.text for r in respuestas
    ]
    assert _resultado(session_factory, turno_id) == ("cancelado", 1)


def test_confirmar_y_cancelar_a_la_vez_quedan_ambas_en_orden(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, turnos_data
) -> None:
    """Ambas son válidas en cualquier orden (reservado→confirmado→cancelado o reservado→cancelado
    + confirmado rechazado): nunca se pierde un cambio y el historial coincide con los 200."""
    turno_id = _turno(session_factory, turnos_data, datetime(2031, 11, 4, 10, tzinfo=UTC))
    bodies = [{"estado": "confirmado"}, {"estado": "cancelado"}]
    respuestas = _disparar(session_factory, monkeypatch, turno_id, bodies)
    ok = sum(r.status_code == 200 for r in respuestas)
    estado, filas = _resultado(session_factory, turno_id)
    assert estado == "cancelado"
    assert filas == ok
    assert all(r.status_code in (200, 422) for r in respuestas)


def test_transicion_espera_el_lock_y_se_evalua_contra_el_estado_confirmado(  # type: ignore[no-untyped-def]
    session_factory, turnos_data, auth_data
) -> None:
    """Determinista (D5): una transacción retiene el lock de la fila con el turno ya cancelado
    sin confirmar; la transición concurrente debe ESPERAR y, al liberarse, ver ``cancelado`` y
    responder 422. Sin ``with_for_update`` leería ``reservado`` y pisaría el cambio."""
    td = turnos_data
    actor = auth_data["user_ids"][RECEPCION]
    turno_id = _turno(session_factory, td, datetime(2031, 11, 5, 10, tzinfo=UTC))
    resultado: dict = {}

    def _concurrente() -> None:
        with session_factory() as s2:
            try:
                transicionar_turno(s2, td["a"], turno_id, "cancelado", actor, None, AHORA)
                resultado["ok"] = True
            except ReferenciaInvalida as exc:
                resultado["error"] = exc

    with session_factory() as s1:
        turno = s1.scalars(select(Turno).where(Turno.id == turno_id).with_for_update()).one()
        turno.estado = "cancelado"
        s1.add(
            TurnoTransicion(
                clinica_id=td["a"],
                turno_id=turno_id,
                desde="reservado",
                hacia="cancelado",
                actor_usuario_id=actor,
            )
        )
        s1.flush()
        hilo = threading.Thread(target=_concurrente)
        hilo.start()
        time.sleep(1.0)
        assert hilo.is_alive(), "la transición concurrente no esperó el lock de la fila"
        s1.commit()
    hilo.join(timeout=30)
    assert not hilo.is_alive()
    assert "ok" not in resultado
    assert isinstance(resultado.get("error"), ReferenciaInvalida)
    assert _resultado(session_factory, turno_id) == ("cancelado", 1)
