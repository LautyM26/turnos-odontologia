"""GET /api/agenda/turnos y /api/agenda/bloqueos (C-07 D1): escenarios de ``agenda-view``.

PG16 real, datos sintéticos. Cada test usa un día propio de 2033-09. P está vinculado a
``odonto@test.test``; Q no tiene usuario.
"""

import itertools
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.agenda.models import Bloqueo
from app.domain.agenda.turnos import Turno
from tests.integration.conftest import bearer, make_test_client

RECEPCION = "recepcion@test.test"
ODONTO = "odonto@test.test"
_dias = itertools.count(0)


def _dia() -> datetime:
    return datetime(2033, 9, 1, tzinfo=UTC) + timedelta(days=next(_dias))


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return make_test_client(session_factory, monkeypatch)


def _turno(session_factory, td, inicio, prof=None, sillon=None, clinica="a", **over):  # type: ignore[no-untyped-def]
    if clinica == "a":
        cols = {"profesional_id": prof or td["p"], "sillon_id": sillon or td["s1"],
                "paciente_id": td["pac_a"], "prestacion_id": td["prest_a"]}  # fmt: skip
    else:
        cols = {"profesional_id": td["prof_b"], "sillon_id": td["sillon_b"],
                "paciente_id": td["pac_b"], "prestacion_id": td["prest_b"]}  # fmt: skip
    with session_factory() as session:
        t = Turno(
            clinica_id=td[clinica], duracion_min=30, inicio=inicio,
            fin=inicio + timedelta(minutes=30), **cols, **over,
        )  # fmt: skip
        session.add(t)
        session.commit()
        return t.id


def _bloqueo(session_factory, clinica_id, inicio, fin, **alcance):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        b = Bloqueo(clinica_id=clinica_id, inicio=inicio, fin=fin, motivo="sintetico", **alcance)
        session.add(b)
        session.commit()
        return b.id


def _get(client, ruta, h, dia, **params):  # type: ignore[no-untyped-def]
    q = {"desde": dia.isoformat(), "hasta": (dia + timedelta(days=1)).isoformat(), **params}
    return client.get(f"/api/agenda/{ruta}", params=q, headers=h)


def test_dia_de_la_recepcion_ordenado_con_nombres_y_sobreturno(  # type: ignore[no-untyped-def]
    client, session_factory, turnos_data
) -> None:
    td, dia = turnos_data, _dia()
    t1 = _turno(session_factory, td, dia.replace(hour=13), estado="confirmado")
    t2 = _turno(
        session_factory, td, dia.replace(hour=13, minute=15), prof=td["q"], sillon=td["s2"],
        es_sobreturno=True, motivo_sobreturno="urgencia sintetica",
    )  # fmt: skip
    resp = _get(client, "turnos", bearer(client, RECEPCION), dia)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [t["id"] for t in body] == [t1, t2]
    assert body[0]["estado"] == "confirmado" and body[0]["paciente_nombre"].count(",") == 1
    assert body[0]["prestacion_nombre"] and body[1]["es_sobreturno"] is True
    assert {"dni", "email", "telefono"}.isdisjoint(body[0])


def test_filtros_por_profesional_y_sillon(client, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    tp = _turno(session_factory, td, dia.replace(hour=13))
    tq = _turno(session_factory, td, dia.replace(hour=14), prof=td["q"], sillon=td["s2"])
    h = bearer(client, RECEPCION)
    assert [t["id"] for t in _get(client, "turnos", h, dia, profesional_id=td["p"]).json()] == [tp]
    assert [t["id"] for t in _get(client, "turnos", h, dia, sillon_id=td["s2"]).json()] == [tq]


def test_cancelado_incluido_y_baja_excluida(client, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    cancelado = _turno(session_factory, td, dia.replace(hour=13), estado="cancelado")
    _turno(session_factory, td, dia.replace(hour=14), is_active=False)
    body = _get(client, "turnos", bearer(client, RECEPCION), dia).json()
    assert [(t["id"], t["estado"]) for t in body] == [(cancelado, "cancelado")]


@pytest.mark.parametrize("ruta", ["turnos", "bloqueos"])
def test_ventana_invalida_422(client, turnos_data, ruta) -> None:  # type: ignore[no-untyped-def]
    dia, h = _dia(), bearer(client, RECEPCION)
    largo = client.get(
        f"/api/agenda/{ruta}",
        params={"desde": dia.isoformat(), "hasta": (dia + timedelta(days=8)).isoformat()},
        headers=h,
    )
    invertida = client.get(
        f"/api/agenda/{ruta}",
        params={"desde": dia.isoformat(), "hasta": (dia - timedelta(hours=1)).isoformat()},
        headers=h,
    )
    assert largo.status_code == 422 and invertida.status_code == 422


def test_bloqueos_por_alcance(client, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    clinica = _bloqueo(session_factory, td["a"], dia, dia + timedelta(days=1))
    almuerzo = _bloqueo(session_factory, td["a"], dia.replace(hour=16), dia.replace(hour=17),
                        profesional_id=td["p"])  # fmt: skip
    sillon = _bloqueo(session_factory, td["a"], dia.replace(hour=18), dia.replace(hour=19),
                      sillon_id=td["s2"])  # fmt: skip
    otro_prof = _bloqueo(session_factory, td["a"], dia.replace(hour=20), dia.replace(hour=21),
                         profesional_id=td["q"])  # fmt: skip
    h = bearer(client, RECEPCION)
    todos = {b["id"]: b["alcance"] for b in _get(client, "bloqueos", h, dia).json()}
    assert todos == {clinica: "clinica", almuerzo: "profesional", sillon: "sillon",
                     otro_prof: "profesional"}  # fmt: skip
    de_p = {b["id"] for b in _get(client, "bloqueos", h, dia, profesional_id=td["p"]).json()}
    assert de_p == {clinica, almuerzo, sillon}


def test_odontologo_su_agenda_otra_y_sin_profesional(client, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    propio = _turno(session_factory, td, dia.replace(hour=13))
    _turno(session_factory, td, dia.replace(hour=14), prof=td["q"], sillon=td["s2"])
    h = bearer(client, ODONTO)
    ok = _get(client, "turnos", h, dia, profesional_id=td["p"])
    assert ok.status_code == 200 and [t["id"] for t in ok.json()] == [propio]
    assert _get(client, "turnos", h, dia, profesional_id=td["q"]).status_code == 403
    assert _get(client, "bloqueos", h, dia, profesional_id=td["q"]).status_code == 403
    assert _get(client, "turnos", h, dia).status_code == 422


def test_sin_token_401(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    dia = _dia()
    assert _get(client, "turnos", {}, dia).status_code == 401
    assert _get(client, "bloqueos", {}, dia).status_code == 401


def test_aislamiento_entre_clinicas(client, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    _turno(session_factory, td, dia.replace(hour=13), clinica="b")
    _bloqueo(session_factory, td["b"], dia, dia + timedelta(days=1))
    h = bearer(client, RECEPCION)
    assert _get(client, "turnos", h, dia).json() == []
    assert _get(client, "bloqueos", h, dia).json() == []
