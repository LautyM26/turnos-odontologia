"""Bloqueos propios del odontologo (C-04): /api/profesionales/{id}/bloqueos."""

import pytest

from tests.integration.conftest import bearer, make_test_client


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return make_test_client(session_factory, monkeypatch)


def _body(dia: int = 1, **extra) -> dict:  # type: ignore[no-untyped-def]
    return {
        "inicio": f"2034-02-{dia:02d}T13:00:00Z",
        "fin": f"2034-02-{dia:02d}T14:00:00Z",
        "motivo": "curso sintetico",
    } | extra


def _url(pid: int, sufijo: str = "") -> str:
    return f"/api/profesionales/{pid}/bloqueos{sufijo}"


def test_odontologo_lista_crea_y_borra_los_propios(client, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    p = catalogo_data["prof_p"]
    creado = client.post(_url(p), json=_body(1), headers=h)
    assert creado.status_code == 201, creado.text
    assert creado.json()["profesional_id"] == p and creado.json()["sillon_id"] is None
    lista = client.get(_url(p), headers=h)
    assert lista.status_code == 200
    assert creado.json()["id"] in [b["id"] for b in lista.json()["items"]]
    assert {b["profesional_id"] for b in lista.json()["items"]} == {p}
    assert client.delete(_url(p, f"/{creado.json()['id']}"), headers=h).status_code == 204
    despues = client.get(_url(p), headers=h).json()["items"]
    assert creado.json()["id"] not in [b["id"] for b in despues]


def test_post_fuerza_el_profesional_del_path(client, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    p, q = catalogo_data["prof_p"], catalogo_data["prof_q"]
    # profesional_id distinto en el body no permite escribir en otra agenda.
    resp = client.post(_url(p), json=_body(2, profesional_id=q), headers=h)
    assert resp.status_code == 201 and resp.json()["profesional_id"] == p


def test_sillon_id_en_body_422(client, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    resp = client.post(
        _url(catalogo_data["prof_p"]), json=_body(3, sillon_id=catalogo_data["sillones"][0]),
        headers=h,
    )  # fmt: skip
    assert resp.status_code == 422


def test_agenda_ajena_403(client, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    q = catalogo_data["prof_q"]
    assert client.get(_url(q), headers=h).status_code == 403
    assert client.post(_url(q), json=_body(4), headers=h).status_code == 403
    assert client.delete(_url(q, "/1"), headers=h).status_code == 403


def test_borrar_bloqueo_que_no_es_del_profesional_404(client, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    admin = bearer(client, "admin@clinica-piloto.test")
    h = bearer(client, "odonto@test.test")
    q = catalogo_data["prof_q"]
    de_q = client.post(_url(q), json=_body(5), headers=admin).json()["id"]
    assert client.delete(_url(catalogo_data["prof_p"], f"/{de_q}"), headers=h).status_code == 404
    # Sigue vigente para Q.
    assert de_q in [b["id"] for b in client.get(_url(q), headers=admin).json()["items"]]
    assert client.delete(_url(catalogo_data["prof_p"], "/99999999"), headers=h).status_code == 404


def test_recepcionista_403_y_sin_token_401(client, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    p = catalogo_data["prof_p"]
    assert client.get(_url(p), headers=h).status_code == 403
    assert client.post(_url(p), json=_body(6), headers=h).status_code == 403
    assert client.get(_url(p)).status_code == 401


def test_admin_opera_cualquier_profesional_de_su_clinica_y_ajeno_404(  # type: ignore[no-untyped-def]
    client, catalogo_data
) -> None:
    h = bearer(client, "admin@clinica-piloto.test")
    q = catalogo_data["prof_q"]
    creado = client.post(_url(q), json=_body(7), headers=h)
    assert creado.status_code == 201 and creado.json()["profesional_id"] == q
    assert client.delete(_url(q, f"/{creado.json()['id']}"), headers=h).status_code == 204
    pb = catalogo_data["prof_b"]
    assert client.get(_url(pb), headers=h).status_code == 404
    assert client.post(_url(pb), json=_body(7), headers=h).status_code == 404
    assert client.delete(_url(pb, f"/{catalogo_data['bloqueo_b']}"), headers=h).status_code == 404


def test_rango_invalido_422(client, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "odonto@test.test")
    malo = _body(8) | {"fin": "2034-02-08T12:00:00Z"}
    assert client.post(_url(catalogo_data["prof_p"]), json=malo, headers=h).status_code == 422
