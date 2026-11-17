"""GET /api/agenda/huecos (C-05c D6): contrato HTTP, validación y RBAC. PG16 real, sintético."""

import itertools
from datetime import UTC, datetime, timedelta

import pytest

from app.api.turnos import get_ahora
from app.domain.agenda.models import Bloqueo
from tests.integration.conftest import bearer, make_test_client

RECEPCION = "recepcion@test.test"
ODONTO = "odonto@test.test"  # vinculado a P
_dias = itertools.count(0)


def _dia() -> datetime:
    return datetime(2032, 5, 1, tzinfo=UTC) + timedelta(days=next(_dias))


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    cli = make_test_client(session_factory, monkeypatch)
    cli.app.dependency_overrides[get_ahora] = lambda: datetime(2032, 1, 1, tzinfo=UTC)
    return cli


def _get(client, headers, td, desde, hasta, **over):  # type: ignore[no-untyped-def]
    params = {
        "profesional_id": td["p"], "prestacion_id": td["prest_a"],
        "desde": desde.isoformat() if isinstance(desde, datetime) else desde,
        "hasta": hasta.isoformat() if isinstance(hasta, datetime) else hasta,
    }  # fmt: skip
    params.update(over)
    return client.get("/api/agenda/huecos", params=params, headers=headers)


def test_recepcionista_consulta_huecos_200(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    resp = _get(client, bearer(client, RECEPCION), td, dia.replace(hour=9), dia.replace(hour=10))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [datetime.fromisoformat(h["inicio"]).minute for h in body] == [0, 15, 30]
    assert body[0]["sillon_ids"] == sorted([td["s1"], td["s2"]])
    assert datetime.fromisoformat(body[0]["fin"]) == dia.replace(hour=9, minute=30)


def test_lista_vacia_200(client, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    with session_factory() as session:
        session.add(
            Bloqueo(clinica_id=td["a"], inicio=dia, fin=dia + timedelta(days=1), motivo="feriado")
        )
        session.commit()
    resp = _get(client, bearer(client, RECEPCION), td, dia.replace(hour=9), dia.replace(hour=12))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.parametrize(
    "caso",
    ["ventana_mayor_a_7_dias", "hasta_antes_de_desde", "desde_sin_zona", "prestacion_inactiva",
     "profesional_de_otra_clinica"],
)  # fmt: skip
def test_consulta_invalida_422(client, turnos_data, caso) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    desde, hasta, over = dia.replace(hour=9), dia.replace(hour=12), {}
    if caso == "ventana_mayor_a_7_dias":
        hasta = desde + timedelta(days=8)
    elif caso == "hasta_antes_de_desde":
        hasta = desde - timedelta(hours=1)
    elif caso == "desde_sin_zona":
        desde = desde.replace(tzinfo=None).isoformat()
    elif caso == "prestacion_inactiva":
        over = {"prestacion_id": td["prest_inactiva"]}
    else:
        over = {"profesional_id": td["prof_b"]}
    resp = _get(client, bearer(client, RECEPCION), td, desde, hasta, **over)
    assert resp.status_code == 422, resp.text


def test_odontologo_consulta_su_agenda_200(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    resp = _get(client, bearer(client, ODONTO), td, dia.replace(hour=9), dia.replace(hour=10))
    assert resp.status_code == 200


def test_odontologo_consulta_otra_agenda_403(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    resp = _get(
        client, bearer(client, ODONTO), td, dia.replace(hour=9), dia.replace(hour=10),
        profesional_id=td["q"],
    )  # fmt: skip
    assert resp.status_code == 403


def test_sin_autenticacion_401(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    resp = _get(client, {}, td, dia.replace(hour=9), dia.replace(hour=10))
    assert resp.status_code == 401
