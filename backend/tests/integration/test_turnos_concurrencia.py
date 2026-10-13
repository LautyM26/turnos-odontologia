"""Concurrencia sobre el mismo hueco (KB07 Flujo 1, doble clic): gana una sola escritura.

Cada request usa su propio TestClient (sesión nueva por request vía override de ``get_session``)
y un ``threading.Barrier`` para que todos disparen a la vez. La garantía final la dan las
exclusion constraints GiST + el mapeo 23P01 -> 409. PG16 real, datos sintéticos.
"""

import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.api.turnos import get_ahora
from app.domain.agenda.turnos import Turno
from tests.integration.conftest import bearer, make_test_client

RECEPCION = "recepcion@test.test"
AHORA = datetime(2031, 1, 1, tzinfo=UTC)


def _disparar(session_factory, monkeypatch, headers, bodies):  # type: ignore[no-untyped-def]
    """Lanza ``len(bodies)`` POST simultáneos; devuelve la lista de status codes."""
    clientes = []
    for _ in bodies:
        cli = make_test_client(session_factory, monkeypatch)
        cli.app.dependency_overrides[get_ahora] = lambda: AHORA
        clientes.append(cli)
    barrera = threading.Barrier(len(bodies))

    def _una(cli, body):  # type: ignore[no-untyped-def]
        barrera.wait(timeout=30)
        return cli.post("/api/turnos", json=body, headers=headers)

    with ThreadPoolExecutor(max_workers=len(bodies)) as pool:
        respuestas = list(pool.map(_una, clientes, bodies))
    return respuestas


def _activos(session_factory, **filtros) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        stmt = select(func.count()).select_from(Turno).where(Turno.is_active.is_(True))
        for campo, valor in filtros.items():
            stmt = stmt.where(getattr(Turno, campo) == valor)
        return int(session.scalar(stmt))


def _body(td, inicio, **over):  # type: ignore[no-untyped-def]
    body = {
        "profesional_id": td["p"], "sillon_id": td["s1"], "paciente_id": td["pac_a"],
        "prestacion_id": td["prest_a"], "inicio": inicio.isoformat(),
    }  # fmt: skip
    body.update(over)
    return body


def test_cinco_pedidos_identicos_un_201_y_cuatro_409(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, turnos_data
) -> None:
    td = turnos_data
    inicio = datetime(2031, 8, 4, 10, tzinfo=UTC)
    headers = bearer(make_test_client(session_factory, monkeypatch), RECEPCION)
    respuestas = _disparar(session_factory, monkeypatch, headers, [_body(td, inicio)] * 5)
    codigos = Counter(r.status_code for r in respuestas)
    assert codigos == Counter({201: 1, 409: 4}), [r.text for r in respuestas]
    assert _activos(session_factory, profesional_id=td["p"], inicio=inicio) == 1


def test_dos_pedidos_que_compiten_solo_por_el_sillon(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, turnos_data
) -> None:
    td = turnos_data
    inicio = datetime(2031, 8, 5, 10, tzinfo=UTC)
    otro = datetime(2031, 8, 5, 10, 15, tzinfo=UTC)  # rango superpuesto, otro profesional
    headers = bearer(make_test_client(session_factory, monkeypatch), RECEPCION)
    bodies = [_body(td, inicio), _body(td, otro, profesional_id=td["q"])]
    codigos = Counter(
        r.status_code for r in _disparar(session_factory, monkeypatch, headers, bodies)
    )
    assert codigos == Counter({201: 1, 409: 1})
    assert (
        _activos(session_factory, profesional_id=td["p"], inicio=inicio)
        + _activos(session_factory, profesional_id=td["q"], inicio=otro)
        == 1
    )
