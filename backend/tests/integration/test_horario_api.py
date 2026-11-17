"""PUT /api/admin/profesionales/{id}/horario y GET /api/catalogo/profesionales/{id}/horario (C-05d).

PG16 real, datos sintéticos. Usa solo ``catalogo_data`` (sin el horario de día completo de
``turnos_data``); cada test parte reemplazando el horario que necesita.
"""

import pytest

from tests.integration.conftest import bearer, make_test_client

RECEPCION = "recepcion@test.test"
ODONTO = "odonto@test.test"
LUN_VIE_PARTIDO = [
    {"dia_semana": d, "inicio": i, "fin": f}
    for d in range(1, 6)
    for i, f in (("09:00", "13:00"), ("15:00", "19:00"))
]


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return make_test_client(session_factory, monkeypatch)


def _put(client, headers, prof_id, franjas):  # type: ignore[no-untyped-def]
    return client.put(
        f"/api/admin/profesionales/{prof_id}/horario", json={"franjas": franjas}, headers=headers
    )


def _get(client, headers, prof_id):  # type: ignore[no-untyped-def]
    return client.get(f"/api/catalogo/profesionales/{prof_id}/horario", headers=headers)


def _admin(client, auth_data):  # type: ignore[no-untyped-def]
    return bearer(client, auth_data["admin_email"])


def test_horario_partido_de_lunes_a_viernes_200(client, auth_data, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    resp = _put(client, _admin(client, auth_data), catalogo_data["prof_q"], LUN_VIE_PARTIDO)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["profesional_id"] == catalogo_data["prof_q"]
    assert body["zona_horaria"] == "America/Argentina/Buenos_Aires"
    assert len(body["franjas"]) == 10
    assert body["franjas"][:2] == [
        {"dia_semana": 1, "inicio": "09:00", "fin": "13:00"},
        {"dia_semana": 1, "inicio": "15:00", "fin": "19:00"},
    ]


def test_franjas_superpuestas_422_y_horario_previo_intacto(  # type: ignore[no-untyped-def]
    client, auth_data, catalogo_data
) -> None:
    h, q = _admin(client, auth_data), catalogo_data["prof_q"]
    assert _put(client, h, q, LUN_VIE_PARTIDO).status_code == 200
    malo = [{"dia_semana": 1, "inicio": "09:00", "fin": "13:00"},
            {"dia_semana": 1, "inicio": "12:00", "fin": "16:00"}]  # fmt: skip
    assert _put(client, h, q, malo).status_code == 422
    assert len(_get(client, h, q).json()["franjas"]) == 10


@pytest.mark.parametrize(
    "franja",
    [
        {"dia_semana": 1, "inicio": "13:00", "fin": "09:00"},
        {"dia_semana": 1, "inicio": "09:00", "fin": "24:30"},
        {"dia_semana": 1, "inicio": "9:00", "fin": "13:00"},
        {"dia_semana": 9, "inicio": "09:00", "fin": "13:00"},
    ],
    ids=["inicio_mayor", "fuera_de_rango", "formato", "dia"],
)
def test_franja_invalida_422(client, auth_data, catalogo_data, franja) -> None:  # type: ignore[no-untyped-def]
    resp = _put(client, _admin(client, auth_data), catalogo_data["prof_q"], [franja])
    assert resp.status_code == 422


def test_dia_completo_y_reemplazo_total(client, auth_data, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    h, q = _admin(client, auth_data), catalogo_data["prof_q"]
    _put(client, h, q, [{"dia_semana": 1, "inicio": "09:00", "fin": "13:00"}])
    resp = _put(client, h, q, [{"dia_semana": 2, "inicio": "10:00", "fin": "14:00"},
                               {"dia_semana": 6, "inicio": "00:00", "fin": "24:00"}])  # fmt: skip
    assert resp.status_code == 200
    assert resp.json()["franjas"] == [
        {"dia_semana": 2, "inicio": "10:00", "fin": "14:00"},
        {"dia_semana": 6, "inicio": "00:00", "fin": "24:00"},
    ]


def test_lista_vacia_deja_sin_horario(client, auth_data, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    h, q = _admin(client, auth_data), catalogo_data["prof_q"]
    _put(client, h, q, LUN_VIE_PARTIDO)
    resp = _put(client, h, q, [])
    assert resp.status_code == 200
    assert resp.json()["franjas"] == []


def test_recepcion_no_edita_horarios_403(client, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    resp = _put(client, bearer(client, RECEPCION), catalogo_data["prof_q"], LUN_VIE_PARTIDO)
    assert resp.status_code == 403


def test_profesional_de_otra_clinica_404(client, auth_data, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    h, b = _admin(client, auth_data), catalogo_data["prof_b"]
    assert _put(client, h, b, LUN_VIE_PARTIDO).status_code == 404
    assert _get(client, h, b).status_code == 404
    admin_b = bearer(client, "admin-b@test.test")
    assert _get(client, admin_b, b).json()["franjas"] == []  # el de B quedó intacto


def test_profesional_inexistente_404(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    assert _put(client, _admin(client, auth_data), 999_999, []).status_code == 404


def test_recepcionista_y_odontologo_consultan_el_horario(  # type: ignore[no-untyped-def]
    client, auth_data, catalogo_data
) -> None:
    q = catalogo_data["prof_q"]
    _put(client, _admin(client, auth_data), q, LUN_VIE_PARTIDO)
    for email in (RECEPCION, ODONTO):
        resp = _get(client, bearer(client, email), q)
        assert resp.status_code == 200, email
        assert resp.json()["zona_horaria"] == "America/Argentina/Buenos_Aires"
        assert len(resp.json()["franjas"]) == 10


def test_sin_token_401(client, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    assert _get(client, {}, catalogo_data["prof_q"]).status_code == 401
    assert _put(client, {}, catalogo_data["prof_q"], []).status_code == 401
