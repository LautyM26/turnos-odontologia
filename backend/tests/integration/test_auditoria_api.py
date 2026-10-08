"""Consulta de auditoría HC solo admin, sin escritura por API (C-08 9.1)."""

import pytest
from sqlalchemy import func, select

from app.domain.auditoria.models import AuditoriaHC
from tests.integration.conftest import alta_paciente, bearer


@pytest.fixture()
def paciente(client, auth_data):  # type: ignore[no-untyped-def]
    """Paciente de A con 1 alta + consentimiento + 4 versiones de ficha (eventos varios)."""
    hr = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, hr).json()["id"]
    client.patch(f"/api/pacientes/{pid}", json={"consentimiento_datos": True}, headers=hr)
    ho = bearer(client, "odonto@test.test")
    for n in range(4):
        client.put(
            f"/api/pacientes/{pid}/ficha",
            json={"version_esperada": n, "alergias": f"v{n}"},
            headers=ho,
        )
    return pid


def _total(session_factory) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(AuditoriaHC))


def test_admin_ve_eventos_del_paciente_en_orden_descendente(  # type: ignore[no-untyped-def]
    client, paciente, auth_data
) -> None:
    h = bearer(client, auth_data["admin_email"])
    resp = client.get(f"/api/pacientes/{paciente}/auditoria", headers=h)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [i["accion"] for i in items] == [
        "actualizar", "actualizar", "actualizar", "crear",  # fichas v4..v1
        "consentimiento_otorgado", "crear",
    ]  # fmt: skip
    ids = [i["id"] for i in items]
    assert ids == sorted(ids, reverse=True)
    assert all(i["paciente_id"] == paciente for i in items)
    assert resp.json()["next_cursor"] is None


def test_paginacion_por_cursor_descendente_sin_repetidos(  # type: ignore[no-untyped-def]
    client, paciente, auth_data
) -> None:
    h = bearer(client, auth_data["admin_email"])
    url = f"/api/pacientes/{paciente}/auditoria"
    vistos: list[int] = []
    cursor = None
    while True:
        params = {"limit": 4}
        if cursor is not None:
            params["after_id"] = cursor
        cuerpo = client.get(url, params=params, headers=h).json()
        vistos += [i["id"] for i in cuerpo["items"]]
        cursor = cuerpo["next_cursor"]
        if cursor is None:
            break
    assert len(vistos) == len(set(vistos)) == 6
    assert vistos == sorted(vistos, reverse=True)


@pytest.mark.parametrize("limit", [0, 201, -3])
def test_limit_fuera_de_rango_422(client, paciente, auth_data, limit) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, auth_data["admin_email"])
    resp = client.get(f"/api/pacientes/{paciente}/auditoria", params={"limit": limit}, headers=h)
    assert resp.status_code == 422


def test_sin_eventos_de_otra_clinica_y_404_si_paciente_ajeno(  # type: ignore[no-untyped-def]
    client, paciente, auth_data
) -> None:
    hb = bearer(client, "admin-b@test.test")
    assert client.get(f"/api/pacientes/{paciente}/auditoria", headers=hb).status_code == 404
    pb = alta_paciente(client, hb).json()["id"]
    items = client.get(f"/api/pacientes/{pb}/auditoria", headers=hb).json()["items"]
    assert [i["accion"] for i in items] == ["crear"]
    assert all(i["paciente_id"] == pb for i in items)


@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE"])
def test_metodos_de_escritura_405_sin_cambiar_el_conteo(  # type: ignore[no-untyped-def]
    client, session_factory, paciente, auth_data, metodo
) -> None:
    h = bearer(client, auth_data["admin_email"])
    antes = _total(session_factory)
    resp = client.request(metodo, f"/api/pacientes/{paciente}/auditoria", json={}, headers=h)
    assert resp.status_code == 405
    assert _total(session_factory) == antes


def test_ninguna_ruta_expone_escritura_de_auditoria(client) -> None:  # type: ignore[no-untyped-def]
    paths = client.app.openapi()["paths"]
    rutas = {ruta: ops for ruta, ops in paths.items() if "auditoria" in ruta}
    assert rutas, "debe existir la consulta de auditoría"
    for ruta, ops in rutas.items():
        assert set(ops) <= {"get", "head"}, ruta
