"""API de la lista de espera (C-16 6.1, D7/D8). PG16 real, sintético."""

from datetime import timedelta

import pytest

from app.domain.agenda.turnos import Turno
from app.domain.lista_espera.models import OfertaListaEspera
from app.infrastructure.whatsapp.fake import FakeMensajeria
from tests.integration.conftest import bearer, make_test_client
from tests.integration.conftest_lista import escenario

URL = "/api/lista-espera"


@pytest.fixture()
def fake() -> FakeMensajeria:
    return FakeMensajeria()


@pytest.fixture()
def api(session_factory, monkeypatch, fake):  # type: ignore[no-untyped-def]
    from app.api.whatsapp import mensajeria_wa

    client = make_test_client(session_factory, monkeypatch)
    client.app.dependency_overrides[mensajeria_wa] = lambda: fake
    return client


def test_crud_de_entradas(api, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    h = bearer(api, "recepcion@test.test")
    pid, _ = e.paciente()
    r = api.post(URL, json={"paciente_id": pid, "prestacion_id": e.prest, "prioridad": 3},
                 headers=h)  # fmt: skip
    assert r.status_code == 201, r.text
    eid = r.json()["id"]
    assert r.json()["estado"] == "en_cola"
    assert api.post(URL, json={"paciente_id": pid, "prestacion_id": e.prest},
                    headers=h).status_code == 409  # fmt: skip
    assert api.post(URL, json={"paciente_id": turnos_data["pac_b"], "prestacion_id": e.prest},
                    headers=h).status_code == 422  # fmt: skip
    assert api.post(URL, json={"paciente_id": pid, "prestacion_id": e.prest, "x": 1},
                    headers=h).status_code == 422  # fmt: skip
    lista = api.get(f"{URL}?prestacion_id={e.prest}", headers=h).json()
    assert [x["id"] for x in lista] == [eid]
    r = api.patch(f"{URL}/{eid}", json={"prioridad": 9}, headers=h)
    assert r.status_code == 200 and r.json()["prioridad"] == 9
    assert api.delete(f"{URL}/{eid}", headers=h).status_code == 204
    assert api.get(f"{URL}?prestacion_id={e.prest}", headers=h).json() == []
    assert api.delete(f"{URL}/{eid}", headers=h).status_code == 404


def test_oferta_manual_201_409_422(api, session_factory, turnos_data, fake) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    e.ahora = e.ahora.replace(year=2099)  # la API usa la hora real: hueco bien en el futuro
    h = bearer(api, "recepcion@test.test")
    (p1, _), (p3, tel3) = e.paciente(), e.paciente()
    e1, e3 = e.entrada(p1, prioridad=10), e.entrada(p3)
    hueco = e.hueco(20)
    r = api.post(f"{URL}/{e3}/ofertar", json={"turno_liberado_id": hueco}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "pendiente" and r.json()["lista_espera_id"] == e3
    assert [t for _, tel, t in fake.enviados if tel == tel3]  # recibió el WhatsApp
    r = api.post(f"{URL}/{e1}/ofertar", json={"turno_liberado_id": hueco}, headers=h)
    assert r.status_code == 409
    no_hueco = e.turno(30, e.paciente()[0])  # reservado: no es un hueco liberado
    r = api.post(f"{URL}/{e1}/ofertar", json={"turno_liberado_id": no_hueco}, headers=h)
    assert r.status_code == 422


def test_bandeja_y_metricas(api, session_factory, turnos_data, auth_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    huecos = [e.hueco(20 + 24 * i) for i in range(3)]
    eid = e.entrada(e.paciente()[0])
    with session_factory() as s:
        t = s.get(Turno, huecos[0])
        nuevo = Turno(clinica_id=e.c, profesional_id=t.profesional_id, sillon_id=t.sillon_id,
                      paciente_id=t.paciente_id, prestacion_id=e.prest, duracion_min=30,
                      inicio=t.inicio, fin=t.fin, origen="lista_espera")  # fmt: skip
        s.add(nuevo)
        s.flush()
        s.add(OfertaListaEspera(
            clinica_id=e.c, lista_espera_id=eid, turno_liberado_id=t.id, inicio=t.inicio,
            fin=t.fin, profesional_id=t.profesional_id, sillon_id=t.sillon_id,
            prestacion_id=e.prest, estado="aceptada", expira_at=e.ahora + timedelta(minutes=30),
            turno_creado_id=nuevo.id,
        ))  # fmt: skip
        s.commit()
    h = bearer(api, auth_data["admin_email"])
    bandeja = api.get(f"{URL}/bandeja", headers=h).json()
    fila = next(b for b in bandeja if b["lista_espera_id"] == eid)
    assert fila["estado"] == "aceptada" and fila["paciente_nombre"] == "Paciente Sintetico"
    desde, hasta = (e.ahora + timedelta(days=1)).date(), (e.ahora + timedelta(days=3)).date()
    r = api.get(f"{URL}/metricas?desde={desde}&hasta={hasta}", headers=h)
    assert r.status_code == 200, r.text
    assert (r.json()["liberados"], r.json()["recuperados"], r.json()["perdidos"]) == (3, 1, 2)
    r = api.get(f"{URL}/metricas?desde={hasta}&hasta={desde}", headers=h)
    assert r.status_code == 422


def test_rbac_y_aislamiento(api, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    eid = e.entrada(e.paciente()[0])
    assert api.get(URL, headers=bearer(api, "odonto@test.test")).status_code == 403
    assert api.get(URL).status_code == 401
    hb = bearer(api, "recepcion-b@test.test")
    assert eid not in [x["id"] for x in api.get(URL, headers=hb).json()]
    assert api.patch(f"{URL}/{eid}", json={"prioridad": 1}, headers=hb).status_code == 404
    assert api.delete(f"{URL}/{eid}", headers=hb).status_code == 404
