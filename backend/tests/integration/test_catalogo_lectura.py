"""Lectura del catalogo para el staff (C-04): /api/catalogo/*."""

import pytest

from app.api.deps import is_public_path
from tests.integration.conftest import bearer, crear_usuario, make_test_client

RUTAS = ("profesionales", "sillones", "prestaciones")


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return make_test_client(session_factory, monkeypatch)


@pytest.mark.parametrize("email", ["admin@clinica-piloto.test", "recepcion@test.test",
                                    "odonto@test.test"])
def test_staff_lista_solo_activos_de_su_clinica(client, catalogo_data, email) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, email)
    por_ruta = {}
    for ruta in RUTAS:
        resp = client.get(f"/api/catalogo/{ruta}", headers=h)
        assert resp.status_code == 200, resp.text
        por_ruta[ruta] = resp.json()
        assert "clinica_id" not in str(resp.json())
        assert {i["is_active"] for i in resp.json()["items"]} == {True}
    ids = lambda ruta: {i["id"] for i in por_ruta[ruta]["items"]}  # noqa: E731
    assert set(catalogo_data["sillones"]) <= ids("sillones")
    assert catalogo_data["sillon_b"] not in ids("sillones")
    assert {catalogo_data["prof_p"], catalogo_data["prof_q"]} <= ids("profesionales")
    assert catalogo_data["prof_b"] not in ids("profesionales")
    assert catalogo_data["prest_a"] in ids("prestaciones")
    assert catalogo_data["prest_b"] not in ids("prestaciones")


def test_prestaciones_incluyen_duracion(client, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    items = client.get("/api/catalogo/prestaciones", headers=h).json()["items"]
    fila = next(i for i in items if i["id"] == catalogo_data["prest_a"])
    assert fila["duracion_min"] == 30 and fila["precio_referencia"] == "1000.00"


def test_inactivos_excluidos_y_sin_parametro_para_verlos(  # type: ignore[no-untyped-def]
    client, catalogo_data, session_factory
) -> None:
    from app.domain.agenda.models import SillonRecurso

    with session_factory() as session:
        s = SillonRecurso(
            clinica_id=catalogo_data["a"], nombre="Sillon baja lectura", tipo="box", is_active=False
        )
        session.add(s)
        session.commit()
        sid = s.id
    h = bearer(client, "recepcion@test.test")
    for url in ("/api/catalogo/sillones", "/api/catalogo/sillones?incluir_inactivos=true"):
        items = client.get(url, headers=h).json()["items"]
        assert sid not in [i["id"] for i in items]


def test_paginacion_y_limit_invalido(client) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    pagina = client.get("/api/catalogo/sillones?limit=1", headers=h).json()
    assert len(pagina["items"]) == 1 and pagina["next_cursor"] is not None
    assert client.get("/api/catalogo/sillones?limit=500", headers=h).status_code == 422


def test_paciente_enlace_403_y_sin_token_401(  # type: ignore[no-untyped-def]
    client, catalogo_data, session_factory, password_hash
) -> None:
    crear_usuario(
        session_factory, password_hash, catalogo_data["a"], "enlace-lectura@test.test",
        ["paciente-enlace"],
    )  # fmt: skip
    h = bearer(client, "enlace-lectura@test.test")
    for ruta in RUTAS:
        assert client.get(f"/api/catalogo/{ruta}", headers=h).status_code == 403
        assert client.get(f"/api/catalogo/{ruta}").status_code == 401


def test_ninguna_ruta_nueva_es_publica() -> None:
    for path in ("/api/catalogo/sillones", "/api/admin/bloqueos", "/api/profesionales/1/bloqueos"):
        assert is_public_path(path) is False
