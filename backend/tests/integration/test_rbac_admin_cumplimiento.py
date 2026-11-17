"""RBAC y aislamiento de /api/admin/usuarios y /api/admin/exportacion (C-18 4.4)."""

import pytest
from sqlalchemy import func, select

from app.domain.auditoria.models import AuditoriaAdmin
from tests.integration.conftest import bearer

pytestmark = pytest.mark.usefixtures("auth_data")

RUTAS = [
    ("GET", "/api/admin/usuarios", None),
    ("POST", "/api/admin/usuarios", {"email": "x@example.com", "nombre": "X",
                                     "password": "clave-sintetica-1", "roles": ["admin"]}),
    ("PATCH", "/api/admin/usuarios/1/roles", {"roles": ["admin"]}),
    ("GET", "/api/admin/exportacion?formato=csv", None),
]  # fmt: skip


def _n_eventos(session_factory) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(select(func.count()).select_from(AuditoriaAdmin))


@pytest.mark.parametrize("email", ["odonto@test.test", "recepcion@test.test", "multi@test.test"])
def test_no_admin_403_en_todas_las_rutas_sin_efectos(client, session_factory, email) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, email)
    antes = _n_eventos(session_factory)
    for metodo, url, cuerpo in RUTAS:
        assert client.request(metodo, url, json=cuerpo, headers=h).status_code == 403, url
    assert _n_eventos(session_factory) == antes


def test_sin_token_401(client) -> None:  # type: ignore[no-untyped-def]
    for metodo, url, cuerpo in RUTAS:
        assert client.request(metodo, url, json=cuerpo).status_code == 401, url


def test_admin_de_a_sobre_usuario_de_b_404_y_roles_de_b_intactos(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    ha = bearer(client, auth_data["admin_email"])
    hb = bearer(client, "admin-b@test.test")
    id_b = client.get("/api/admin/usuarios", headers=hb).json()["items"][0]["id"]
    url = f"/api/admin/usuarios/{id_b}/roles"
    r = client.patch(url, json={"roles": ["recepcionista"]}, headers=ha)
    assert r.status_code == 404
    assert client.get("/api/admin/usuarios", headers=hb).json()["items"][0]["roles"] == ["admin"]


def test_usuario_inexistente_404(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, auth_data["admin_email"])
    r = client.patch("/api/admin/usuarios/999999/roles", json={"roles": ["admin"]}, headers=h)
    assert r.status_code == 404


def test_ninguna_ruta_escribe_o_borra_eventos_administrativos(client) -> None:  # type: ignore[no-untyped-def]
    for ruta, metodos in client.app.openapi()["paths"].items():
        if "auditoria-admin" in ruta or "auditoria_admin" in ruta:
            raise AssertionError(f"ruta inesperada de auditoría admin: {ruta}")
        if ruta.startswith(("/api/admin/usuarios", "/api/admin/exportacion")):
            assert not ({"delete", "put"} & set(metodos)), ruta
