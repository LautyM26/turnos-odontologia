"""POST /api/turnos con sobreturno (C-05c, RN-AG-04): un test por escenario de la spec.

PG16 real vía testcontainers; fechas futuras 2032 y datos sintéticos. Cada test usa un día
propio para no interferir con los demás tests del módulo.
"""

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.api.turnos import get_ahora
from app.domain.agenda.models import Bloqueo
from app.domain.agenda.turnos import Turno
from tests.integration.conftest import bearer, make_test_client

RECEPCION = "recepcion@test.test"
ODONTO = "odonto@test.test"
MOTIVO = "urgencia, dolor agudo"
_dias = itertools.count(0)


def _dia() -> datetime:
    return datetime(2032, 2, 1, tzinfo=UTC) + timedelta(days=next(_dias))


def _cliente(session_factory, monkeypatch, ahora: datetime):  # type: ignore[no-untyped-def]
    cli = make_test_client(session_factory, monkeypatch)
    cli.app.dependency_overrides[get_ahora] = lambda: ahora
    return cli


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return _cliente(session_factory, monkeypatch, datetime(2032, 1, 1, tzinfo=UTC))


def _post(client, headers, td, inicio, **over):  # type: ignore[no-untyped-def]
    body = {
        "profesional_id": td["p"], "sillon_id": td["s1"], "paciente_id": td["pac_a"],
        "prestacion_id": td["prest_a"], "inicio": inicio.isoformat(),
    }  # fmt: skip
    body.update(over)
    return client.post("/api/turnos", json=body, headers=headers)


def _n_turnos(session_factory, inicio: datetime) -> int:
    with session_factory() as session:
        stmt = select(func.count()).select_from(Turno).where(Turno.inicio == inicio)
        return int(session.scalar(stmt))


def test_recepcionista_da_un_sobreturno_sobre_un_horario_ocupado(  # type: ignore[no-untyped-def]
    client, session_factory, turnos_data
) -> None:
    td, h = turnos_data, bearer(client, RECEPCION)
    inicio = _dia().replace(hour=10)
    assert _post(client, h, td, inicio).status_code == 201
    resp = _post(client, h, td, inicio, sobreturno=True, motivo_sobreturno=MOTIVO)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["estado"] == "reservado"
    assert body["es_sobreturno"] is True
    assert body["motivo_sobreturno"] == MOTIVO
    assert _n_turnos(session_factory, inicio) == 2


@pytest.mark.parametrize(
    "extra",
    [
        {"sobreturno": True},
        {"sobreturno": True, "motivo_sobreturno": "   "},
        {"motivo_sobreturno": MOTIVO},
    ],
    ids=["sobreturno_sin_motivo", "motivo_en_blanco", "motivo_sin_sobreturno"],
)
def test_sobreturno_y_motivo_van_juntos_422_sin_fila(  # type: ignore[no-untyped-def]
    client, session_factory, turnos_data, extra
) -> None:
    inicio = _dia().replace(hour=10)
    resp = _post(client, bearer(client, RECEPCION), turnos_data, inicio, **extra)
    assert resp.status_code == 422
    assert _n_turnos(session_factory, inicio) == 0


def test_sobreturno_sobre_un_feriado_409(client, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    with session_factory() as session:
        session.add(
            Bloqueo(clinica_id=td["a"], inicio=dia, fin=dia + timedelta(days=1), motivo="feriado")
        )
        session.commit()
    inicio = dia.replace(hour=10)
    resp = _post(
        client, bearer(client, RECEPCION), td, inicio, sobreturno=True, motivo_sobreturno=MOTIVO
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Horario no disponible"
    assert _n_turnos(session_factory, inicio) == 0


def test_un_sobreturno_no_ocupa_el_horario(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, h = turnos_data, bearer(client, RECEPCION)
    inicio = _dia().replace(hour=12)
    sobre = _post(client, h, td, inicio, sobreturno=True, motivo_sobreturno=MOTIVO)
    assert sobre.status_code == 201
    normal = _post(client, h, td, inicio)
    assert normal.status_code == 201, normal.text
    assert normal.json()["es_sobreturno"] is False


def test_sobreturno_superpuesto_pasa_a_asistido(  # type: ignore[no-untyped-def]
    client, session_factory, monkeypatch, turnos_data
) -> None:
    td, h = turnos_data, bearer(client, RECEPCION)
    inicio = _dia().replace(hour=10)
    normal = _post(client, h, td, inicio).json()["id"]
    sobre = _post(client, h, td, inicio, sobreturno=True, motivo_sobreturno=MOTIVO).json()["id"]
    assert client.post(
        f"/api/turnos/{normal}/transicion", json={"estado": "confirmado"}, headers=h
    ).status_code == 200  # fmt: skip
    despues = _cliente(session_factory, monkeypatch, inicio + timedelta(minutes=5))
    h2 = bearer(despues, RECEPCION)
    for turno_id in (normal, sobre):
        resp = despues.post(
            f"/api/turnos/{turno_id}/transicion", json={"estado": "asistido"}, headers=h2
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["estado"] == "asistido"


def test_odontologo_no_puede_dar_sobreturno_403(client, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    inicio = _dia().replace(hour=10)
    resp = _post(
        client, bearer(client, ODONTO), turnos_data, inicio,
        sobreturno=True, motivo_sobreturno=MOTIVO,
    )  # fmt: skip
    assert resp.status_code == 403
    assert _n_turnos(session_factory, inicio) == 0
