"""Administración de usuarios: alta, listado y roles (C-18 4.1, 4.2). PG16 real, sintéticos."""

import pytest
from sqlalchemy import select, text

from app.domain.auditoria.models import AuditoriaAdmin
from tests.integration.conftest import bearer

PASSWORD_NUEVA = "clave-sintetica-123"


def _admin(client, auth_data):  # type: ignore[no-untyped-def]
    return bearer(client, auth_data["admin_email"])


def _alta(client, h, email, roles=("odontologo",), **extra):  # type: ignore[no-untyped-def]
    cuerpo = {"email": email, "nombre": "Alta Sintetica", "password": PASSWORD_NUEVA,
              "roles": list(roles)}  # fmt: skip
    cuerpo.update(extra)
    return client.post("/api/admin/usuarios", json=cuerpo, headers=h)


def _eventos(session_factory, **filtros):  # type: ignore[no-untyped-def]
    with session_factory() as s:
        stmt = select(AuditoriaAdmin)
        for k, v in filtros.items():
            stmt = stmt.where(getattr(AuditoriaAdmin, k) == v)
        return list(s.scalars(stmt.order_by(AuditoriaAdmin.id)).all())


# --- 4.1 Alta y listado --------------------------------------------------------------------


def test_alta_de_odontologo_201_sin_hash_y_con_login(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = _admin(client, auth_data)
    r = _alta(client, h, "Nuevo.Odonto@Example.com")
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["email"] == "nuevo.odonto@example.com" and b["roles"] == ["odontologo"]
    assert b["nombre"] == "Alta Sintetica" and b["is_active"] is True and b["id"]
    assert not any("password" in k or "hash" in k for k in b)
    login = client.post(
        "/api/auth/login", json={"email": "nuevo.odonto@example.com", "password": PASSWORD_NUEVA}
    )
    assert login.status_code == 200


def test_el_usuario_se_crea_en_la_clinica_del_admin(client, session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    r = _alta(client, _admin(client, auth_data), "propia@example.com")
    with session_factory() as s:
        clinica = s.scalar(
            text("SELECT clinica_id FROM usuario WHERE id=:i"), {"i": r.json()["id"]}
        )
    assert clinica == auth_data["clinica_a"]


def test_email_repetido_en_otra_capitalizacion_409(client, session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = _admin(client, auth_data)
    assert _alta(client, h, "repetido@example.com").status_code == 201
    r = _alta(client, h, "REPETIDO@Example.com")
    assert r.status_code == 409
    with session_factory() as s:
        n = s.scalar(text("SELECT count(*) FROM usuario WHERE lower(email)='repetido@example.com'"))
    assert n == 1


@pytest.mark.parametrize(
    "roles", [[], ["paciente-enlace"], ["superuser"], ["odontologo", "odontologo"]]
)
def test_roles_no_asignables_422(client, session_factory, auth_data, roles) -> None:  # type: ignore[no-untyped-def]
    r = _alta(client, _admin(client, auth_data), "roles-malos@example.com", roles)
    assert r.status_code == 422
    with session_factory() as s:
        assert not s.scalar(text("SELECT 1 FROM usuario WHERE email='roles-malos@example.com'"))


@pytest.mark.parametrize(
    "extra", [{"clinica_id": 999}, {"password_hash": "x"}, {"is_active": False}]
)
def test_campos_de_servidor_422(client, auth_data, extra) -> None:  # type: ignore[no-untyped-def]
    assert _alta(client, _admin(client, auth_data), "extra@example.com", **extra).status_code == 422


def test_alta_audita_usuario_crear_sin_email(client, session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = _admin(client, auth_data)
    uid = _alta(client, h, "auditado@example.com", ("recepcionista", "odontologo")).json()["id"]
    (ev,) = _eventos(session_factory, accion="usuario_crear", entidad_id=uid)
    with session_factory() as s:
        admin_id = s.scalar(
            text("SELECT id FROM usuario WHERE email=:e"), {"e": auth_data["admin_email"]}
        )
    assert ev.actor_usuario_id == admin_id
    assert ev.clinica_id == auth_data["clinica_a"]
    assert sorted(ev.diff["roles"]) == ["odontologo", "recepcionista"]
    assert "auditado" not in str(ev.diff) and PASSWORD_NUEVA not in str(ev.diff)


def test_listado_solo_de_la_clinica_sin_hash_y_con_roles(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = _admin(client, auth_data)
    r = client.get("/api/admin/usuarios", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    emails = {u["email"] for u in items}
    assert auth_data["admin_email"] in emails and "recepcion@test.test" in emails
    assert "admin-b@test.test" not in emails  # clínica B
    assert all("password_hash" not in u and "password" not in u for u in items)
    por_email = {u["email"]: u for u in items}
    assert por_email["recepcion@test.test"]["roles"] == ["recepcionista"]
    assert sorted(por_email["multi@test.test"]["roles"]) == ["odontologo", "recepcionista"]


def test_listado_paginado_por_cursor(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = _admin(client, auth_data)
    p1 = client.get("/api/admin/usuarios?limit=2", headers=h).json()
    assert len(p1["items"]) == 2 and p1["next_cursor"] is not None
    p2 = client.get(f"/api/admin/usuarios?limit=2&after_id={p1['next_cursor']}", headers=h).json()
    assert p2["items"] and {u["id"] for u in p1["items"]}.isdisjoint({u["id"] for u in p2["items"]})


@pytest.mark.parametrize("limit", [0, 500])
def test_limite_fuera_de_rango_422(client, auth_data, limit) -> None:  # type: ignore[no-untyped-def]
    assert client.get(f"/api/admin/usuarios?limit={limit}",
                      headers=_admin(client, auth_data)).status_code == 422  # fmt: skip


def test_clinica_con_un_solo_usuario_sin_cursor(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/admin/usuarios", headers=bearer(client, "admin-b@test.test"))
    assert r.status_code == 200
    assert [u["email"] for u in r.json()["items"]] == ["admin-b@test.test"]
    assert r.json()["next_cursor"] is None


# --- 4.2 Roles -----------------------------------------------------------------------------


def _roles(client, h, uid, roles):  # type: ignore[no-untyped-def]
    return client.patch(f"/api/admin/usuarios/{uid}/roles", json={"roles": roles}, headers=h)


def test_cambio_de_rol_es_efectivo_con_el_mismo_token(client, auth_data, staff_c09) -> None:  # type: ignore[no-untyped-def]
    h = _admin(client, auth_data)
    uid = _alta(client, h, "cambio@example.com", ("recepcionista",)).json()["id"]
    login = client.post(
        "/api/auth/login", json={"email": "cambio@example.com", "password": PASSWORD_NUEVA}
    )
    hu = {"Authorization": f"Bearer {login.json()['access_token']}"}
    url = f"/api/pacientes/{staff_c09['pac_con']}/historia"
    assert client.get(url, headers=hu).status_code == 403
    r = _roles(client, h, uid, ["odontologo"])
    assert r.status_code == 200 and r.json()["roles"] == ["odontologo"]
    assert client.get(url, headers=hu).status_code == 200  # sin token nuevo


def test_reactivar_un_rol_quitado(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = _admin(client, auth_data)
    uid = _alta(client, h, "vuelve@example.com", ("recepcionista",)).json()["id"]
    assert _roles(client, h, uid, ["odontologo"]).json()["roles"] == ["odontologo"]
    assert _roles(client, h, uid, ["recepcionista", "odontologo"]).json()["roles"] == [
        "odontologo", "recepcionista",
    ]  # fmt: skip


def test_mismo_conjunto_200_sin_evento(client, session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = _admin(client, auth_data)
    uid = _alta(client, h, "igual@example.com", ("odontologo",)).json()["id"]
    antes = len(_eventos(session_factory, accion="usuario_roles", entidad_id=uid))
    r = _roles(client, h, uid, ["odontologo"])
    assert r.status_code == 200 and r.json()["roles"] == ["odontologo"]
    assert len(_eventos(session_factory, accion="usuario_roles", entidad_id=uid)) == antes


def test_cambio_audita_roles_anteriores_y_nuevos(client, session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = _admin(client, auth_data)
    uid = _alta(client, h, "audit-roles@example.com", ("recepcionista",)).json()["id"]
    _roles(client, h, uid, ["odontologo", "recepcionista"])
    (ev,) = _eventos(session_factory, accion="usuario_roles", entidad_id=uid)
    assert ev.diff == {
        "roles_anteriores": ["recepcionista"],
        "roles": ["odontologo", "recepcionista"],
    }
    assert "audit-roles" not in str(ev.diff)


def test_quitar_el_ultimo_admin_a_si_mismo_409_sin_cambios(client) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "admin-b@test.test")  # único admin de la clínica B
    uid = client.get("/api/admin/usuarios", headers=h).json()["items"][0]["id"]
    r = _roles(client, h, uid, ["recepcionista"])
    assert r.status_code == 409
    items = client.get("/api/admin/usuarios", headers=h).json()["items"]
    assert items[0]["roles"] == ["admin"]


def test_quitar_admin_a_otro_si_queda_uno_es_posible(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = _admin(client, auth_data)
    uid = _alta(client, h, "segundo-admin@example.com", ("admin",)).json()["id"]
    assert _roles(client, h, uid, ["recepcionista"]).status_code == 200


def test_falla_del_writer_admin_revierte_el_cambio_de_roles(  # type: ignore[no-untyped-def]
    client, auth_data, monkeypatch
) -> None:
    from app.domain.usuarios import servicios

    h = _admin(client, auth_data)
    uid = _alta(client, h, "revierte@example.com", ("recepcionista",)).json()["id"]

    def roto(*a, **k):  # type: ignore[no-untyped-def]
        raise RuntimeError("auditoria caida")

    with monkeypatch.context() as m:
        m.setattr(servicios, "registrar_evento_admin", roto)
        with pytest.raises(RuntimeError):
            _roles(client, h, uid, ["odontologo"])
    actual = [u for u in client.get("/api/admin/usuarios?limit=200", headers=h).json()["items"]
              if u["id"] == uid][0]  # fmt: skip
    assert actual["roles"] == ["recepcionista"]


def test_alta_con_falla_del_writer_no_crea_el_usuario(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data, monkeypatch
) -> None:
    from app.domain.usuarios import servicios

    monkeypatch.setattr(servicios, "registrar_evento_admin", lambda *a, **k: 1 / 0)
    h = _admin(client, auth_data)
    with pytest.raises(ZeroDivisionError):
        _alta(client, h, "no-nace@example.com")
    with session_factory() as s:
        assert not s.scalar(text("SELECT 1 FROM usuario WHERE email='no-nace@example.com'"))
