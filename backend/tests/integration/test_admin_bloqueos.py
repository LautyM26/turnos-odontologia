"""Endpoints admin de bloqueos (C-04): alcance unico, validacion de rango, ventana y baja."""

from datetime import UTC, datetime

import pytest

from app.domain.agenda.bloqueos import bloqueos_solapados
from tests.integration.conftest import bearer, make_test_client


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return make_test_client(session_factory, monkeypatch)


@pytest.fixture()
def admin(client, auth_data):  # type: ignore[no-untyped-def]
    return bearer(client, auth_data["admin_email"])


def _body(dia: int, h_ini: int = 10, h_fin: int = 11, **extra) -> dict:  # type: ignore[no-untyped-def]
    return {
        "inicio": f"2033-05-{dia:02d}T{h_ini:02d}:00:00Z",
        "fin": f"2033-05-{dia:02d}T{h_fin:02d}:00:00Z",
        "motivo": "bloqueo sintetico",
    } | extra


def _crear(client, admin, body):  # type: ignore[no-untyped-def]
    resp = client.post("/api/admin/bloqueos", json=body, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_admin_crea_bloqueo_de_clinica_profesional_y_sillon(client, admin, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    clinica = _crear(client, admin, _body(1))
    assert clinica["profesional_id"] is None and clinica["sillon_id"] is None
    assert clinica["is_active"] is True and "clinica_id" not in clinica
    prof = _crear(client, admin, _body(1, profesional_id=catalogo_data["prof_p"]))
    assert prof["profesional_id"] == catalogo_data["prof_p"]
    sillon = _crear(client, admin, _body(1, sillon_id=catalogo_data["sillones"][0]))
    assert sillon["sillon_id"] == catalogo_data["sillones"][0]
    assert sillon["inicio"].startswith("2033-05-01T10:00:00")


def test_profesional_y_sillon_a_la_vez_422(client, admin, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    body = _body(2, profesional_id=catalogo_data["prof_p"], sillon_id=catalogo_data["sillones"][0])
    assert client.post("/api/admin/bloqueos", json=body, headers=admin).status_code == 422


def test_referencias_de_otra_clinica_inactivas_o_inexistentes_422(  # type: ignore[no-untyped-def]
    client, admin, catalogo_data
) -> None:
    for extra in (
        {"profesional_id": catalogo_data["prof_b"]},
        {"sillon_id": catalogo_data["sillon_b"]},
        {"profesional_id": 99999999},
    ):
        resp = client.post("/api/admin/bloqueos", json=_body(2, **extra), headers=admin)
        assert resp.status_code == 422, extra


def test_rangos_invalidos_422(client, admin) -> None:  # type: ignore[no-untyped-def]
    casos = [
        {"inicio": "2033-05-03T11:00:00Z", "fin": "2033-05-03T11:00:00Z"},  # fin == inicio
        {"inicio": "2033-05-03T11:00:00Z", "fin": "2033-05-03T10:00:00Z"},  # fin < inicio
        {"inicio": "2033-05-03T10:00:00", "fin": "2033-05-03T11:00:00"},  # naive
        {"inicio": "2033-05-01T00:00:00Z", "fin": "2033-06-10T00:00:00Z"},  # 40 dias
    ]
    for caso in casos:
        body = {"motivo": "m"} | caso
        assert client.post("/api/admin/bloqueos", json=body, headers=admin).status_code == 422


def test_campos_no_declarados_422(client, admin, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    for extra in ({"clinica_id": catalogo_data["b"]}, {"rango": "x"}, {"is_active": False}):
        resp = client.post("/api/admin/bloqueos", json=_body(2, **extra), headers=admin)
        assert resp.status_code == 422


def test_lista_con_ventana_devuelve_solo_superpuestos(client, admin, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    prof = catalogo_data["prof_q"]
    dentro = _crear(client, admin, _body(10, 10, 11, profesional_id=prof))["id"]
    borde = _crear(client, admin, _body(10, 11, 12, profesional_id=prof))["id"]
    fuera = _crear(client, admin, _body(20, 10, 11, profesional_id=prof))["id"]
    url = (
        "/api/admin/bloqueos?limit=200&desde=2033-05-10T10:30:00Z&hasta=2033-05-10T11:00:00Z"
        f"&profesional_id={prof}"
    )
    ids = {b["id"] for b in client.get(url, headers=admin).json()["items"]}
    assert dentro in ids
    assert borde not in ids  # [11,12) es contiguo a la ventana [10:30, 11)
    assert fuera not in ids
    todos = client.get(f"/api/admin/bloqueos?limit=200&profesional_id={prof}", headers=admin)
    assert {dentro, borde, fuera} <= {b["id"] for b in todos.json()["items"]}


def test_lista_no_incluye_bloqueos_de_otra_clinica(client, admin, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    lista = client.get("/api/admin/bloqueos?limit=200", headers=admin).json()["items"]
    ids = {b["id"] for b in lista}
    assert catalogo_data["bloqueo_b"] not in ids
    assert client.get(
        f"/api/admin/bloqueos/{catalogo_data['bloqueo_b']}", headers=admin
    ).status_code == 404


def test_patch_de_rango_revalida(client, admin) -> None:  # type: ignore[no-untyped-def]
    bid = _crear(client, admin, _body(4))["id"]
    ok = client.patch(
        f"/api/admin/bloqueos/{bid}", json={"fin": "2033-05-04T12:00:00Z"}, headers=admin
    )
    assert ok.status_code == 200 and ok.json()["fin"].startswith("2033-05-04T12:00:00")
    ok2 = client.patch(f"/api/admin/bloqueos/{bid}", json={"motivo": "nuevo"}, headers=admin)
    assert ok2.json()["motivo"] == "nuevo" and ok2.json()["fin"].startswith("2033-05-04T12:00:00")
    for malo in (
        {"fin": "2033-05-04T09:00:00Z"},  # antes del inicio existente
        {"inicio": "2033-05-04T12:00:00Z"},  # igual al fin existente
        {"fin": "2033-07-04T12:00:00Z"},  # mas de 31 dias
        {"fin": "2033-05-04T12:00:00"},  # naive
    ):
        resp = client.patch(f"/api/admin/bloqueos/{bid}", json=malo, headers=admin)
        assert resp.status_code == 422, malo
    assert client.get(f"/api/admin/bloqueos/{bid}", headers=admin).json()["fin"].startswith(
        "2033-05-04T12:00:00"
    )


def test_delete_204_y_deja_de_solaparse(client, admin, catalogo_data, session_factory) -> None:  # type: ignore[no-untyped-def]
    prof = catalogo_data["prof_q"]
    bid = _crear(client, admin, _body(5, profesional_id=prof))["id"]
    ini, fin = datetime(2033, 5, 5, 10, 15, tzinfo=UTC), datetime(2033, 5, 5, 10, 45, tzinfo=UTC)
    with session_factory() as session:
        antes = bloqueos_solapados(session, catalogo_data["a"], ini, fin, prof, None)
        assert bid in {b.id for b in antes}
    assert client.delete(f"/api/admin/bloqueos/{bid}", headers=admin).status_code == 204
    with session_factory() as session:
        despues = bloqueos_solapados(session, catalogo_data["a"], ini, fin, prof, None)
        assert bid not in {b.id for b in despues}
    assert client.get(f"/api/admin/bloqueos/{bid}", headers=admin).status_code == 404
    inactivos = client.get(
        f"/api/admin/bloqueos?limit=200&incluir_inactivos=true&profesional_id={prof}", headers=admin
    )
    assert bid in {b["id"] for b in inactivos.json()["items"]}


def test_ajeno_404_en_patch_y_delete(client, admin, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    ajeno = catalogo_data["bloqueo_b"]
    assert client.patch(
        f"/api/admin/bloqueos/{ajeno}", json={"motivo": "x"}, headers=admin
    ).status_code == 404
    assert client.delete(f"/api/admin/bloqueos/{ajeno}", headers=admin).status_code == 404


def test_recepcionista_y_odontologo_403_y_sin_token_401(client) -> None:  # type: ignore[no-untyped-def]
    for email in ("recepcion@test.test", "odonto@test.test"):
        h = bearer(client, email)
        assert client.post("/api/admin/bloqueos", json=_body(6), headers=h).status_code == 403
        assert client.get("/api/admin/bloqueos", headers=h).status_code == 403
    assert client.get("/api/admin/bloqueos").status_code == 401
