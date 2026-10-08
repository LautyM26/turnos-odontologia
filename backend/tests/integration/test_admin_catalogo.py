"""Endpoints admin de catalogo (C-04): sillones, prestaciones, profesionales, habilitacion."""

import itertools

import pytest

from app.domain.agenda.models import Prestacion, ProfesionalSillon, SillonRecurso
from tests.integration.conftest import bearer, make_test_client

_n = itertools.count(1)


def _u(prefijo: str) -> str:
    return f"{prefijo} {next(_n)}"


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return make_test_client(session_factory, monkeypatch)


@pytest.fixture()
def admin(client, auth_data):  # type: ignore[no-untyped-def]
    return bearer(client, auth_data["admin_email"])


def _prestacion(client, admin, **extra) -> dict:  # type: ignore[no-untyped-def]
    body = {"nombre": _u("Pr"), "duracion_min": 30, "precio_referencia": "1"} | extra
    resp = client.post("/api/admin/prestaciones", json=body, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _sillon(client, admin, **extra) -> dict:  # type: ignore[no-untyped-def]
    body = {"nombre": _u("S"), "tipo": "sillon"} | extra
    resp = client.post("/api/admin/sillones", json=body, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _profesional(client, admin, **extra) -> dict:  # type: ignore[no-untyped-def]
    body = {"nombre": "Prof Sintetico", "matricula": _u("MAT")} | extra
    resp = client.post("/api/admin/profesionales", json=body, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- sillones y prestaciones --------------------------------------------------------------


def test_admin_crea_sillon_201_lista_y_detalle(client, admin, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    nombre = _u("Sillon crea")
    resp = client.post("/api/admin/sillones", json={"nombre": nombre, "tipo": "box"}, headers=admin)
    assert resp.status_code == 201, resp.text
    creado = resp.json()
    assert creado["nombre"] == nombre and creado["tipo"] == "box" and creado["is_active"] is True
    assert "clinica_id" not in creado
    detalle = client.get(f"/api/admin/sillones/{creado['id']}", headers=admin)
    assert detalle.status_code == 200 and detalle.json()["nombre"] == nombre
    pagina = client.get("/api/admin/sillones?limit=200", headers=admin).json()
    assert creado["id"] in [s["id"] for s in pagina["items"]]
    assert catalogo_data["sillon_b"] not in [s["id"] for s in pagina["items"]]


def test_admin_crea_prestacion_y_precio_exacto(client, admin) -> None:  # type: ignore[no-untyped-def]
    creada = _prestacion(client, admin, precio_referencia="15000.50")
    assert creada["precio_referencia"] == "15000.50"
    assert creada["duracion_min"] == 30
    otra = _prestacion(client, admin, duracion_min=60, precio_referencia=0.1)
    assert otra["precio_referencia"] == "0.10"


def test_patch_duracion_se_refleja(client, admin) -> None:  # type: ignore[no-untyped-def]
    pid = _prestacion(client, admin)["id"]
    resp = client.patch(f"/api/admin/prestaciones/{pid}", json={"duracion_min": 40}, headers=admin)
    assert resp.status_code == 200 and resp.json()["duracion_min"] == 40
    assert client.get(f"/api/admin/prestaciones/{pid}", headers=admin).json()["duracion_min"] == 40
    sillon = _sillon(client, admin)
    resp = client.patch(
        f"/api/admin/sillones/{sillon['id']}", json={"tipo": "equipo"}, headers=admin
    )
    assert resp.json()["tipo"] == "equipo" and resp.json()["nombre"] == sillon["nombre"]


@pytest.mark.parametrize("duracion", [0, 600, 30.5])
def test_duracion_invalida_422(client, admin, duracion) -> None:  # type: ignore[no-untyped-def]
    resp = client.post(
        "/api/admin/prestaciones",
        json={"nombre": _u("Pr"), "duracion_min": duracion, "precio_referencia": "1"},
        headers=admin,
    )
    assert resp.status_code == 422


def test_precio_negativo_o_con_3_decimales_422(client, admin) -> None:  # type: ignore[no-untyped-def]
    for precio in ("-1", "10.001"):
        resp = client.post(
            "/api/admin/prestaciones",
            json={"nombre": _u("Pr"), "duracion_min": 30, "precio_referencia": precio},
            headers=admin,
        )
        assert resp.status_code == 422


def test_delete_es_logico_y_incluir_inactivos(client, admin, session_factory) -> None:  # type: ignore[no-untyped-def]
    sid = _sillon(client, admin)["id"]
    assert client.delete(f"/api/admin/sillones/{sid}", headers=admin).status_code == 204
    activos = client.get("/api/admin/sillones?limit=200", headers=admin).json()["items"]
    assert sid not in [s["id"] for s in activos]
    todos = client.get("/api/admin/sillones?limit=200&incluir_inactivos=true", headers=admin)
    fila = next(s for s in todos.json()["items"] if s["id"] == sid)
    assert fila["is_active"] is False and fila["deleted_at"] is not None
    with session_factory() as session:
        row = session.get(SillonRecurso, sid)
        assert row is not None and row.is_active is False and row.deleted_at is not None
    assert client.get(f"/api/admin/sillones/{sid}", headers=admin).status_code == 404


def test_prestacion_delete_logico(client, admin, session_factory) -> None:  # type: ignore[no-untyped-def]
    pid = _prestacion(client, admin)["id"]
    assert client.delete(f"/api/admin/prestaciones/{pid}", headers=admin).status_code == 204
    with session_factory() as session:
        assert session.get(Prestacion, pid).is_active is False


def test_nombre_de_sillon_duplicado_409_y_reusable_tras_baja(client, admin) -> None:  # type: ignore[no-untyped-def]
    nombre = _u("Dup")
    primero = _sillon(client, admin, nombre=nombre)
    dup = client.post(
        "/api/admin/sillones", json={"nombre": nombre.upper(), "tipo": "box"}, headers=admin
    )
    assert dup.status_code == 409
    client.delete(f"/api/admin/sillones/{primero['id']}", headers=admin)
    assert _sillon(client, admin, nombre=nombre)["nombre"] == nombre


def test_tipo_invalido_422(client, admin) -> None:  # type: ignore[no-untyped-def]
    resp = client.post(
        "/api/admin/sillones", json={"nombre": _u("S"), "tipo": "quirofano"}, headers=admin
    )
    assert resp.status_code == 422


def test_id_de_otra_clinica_404(client, admin, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    for ruta, ajeno in (
        ("sillones", catalogo_data["sillon_b"]),
        ("prestaciones", catalogo_data["prest_b"]),
        ("profesionales", catalogo_data["prof_b"]),
    ):
        assert client.get(f"/api/admin/{ruta}/{ajeno}", headers=admin).status_code == 404
        patch = client.patch(f"/api/admin/{ruta}/{ajeno}", json={"nombre": "x"}, headers=admin)
        assert patch.status_code == 404
        assert client.delete(f"/api/admin/{ruta}/{ajeno}", headers=admin).status_code == 404


def test_clinica_id_en_body_422(client, admin, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    resp = client.post(
        "/api/admin/sillones",
        json={"nombre": _u("S"), "tipo": "sillon", "clinica_id": catalogo_data["b"]},
        headers=admin,
    )
    assert resp.status_code == 422


def test_limit_fuera_de_rango_422(client, admin) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/admin/prestaciones?limit=500", headers=admin).status_code == 422
    assert client.get("/api/admin/prestaciones?limit=0", headers=admin).status_code == 422


def test_paginacion_por_cursor_via_http(client, admin) -> None:  # type: ignore[no-untyped-def]
    for _ in range(5):
        _prestacion(client, admin)
    vistos, cursor = [], None
    while True:
        url = "/api/admin/prestaciones?limit=2" + (f"&after_id={cursor}" if cursor else "")
        pagina = client.get(url, headers=admin).json()
        assert len(pagina["items"]) <= 2
        vistos += [i["id"] for i in pagina["items"]]
        cursor = pagina["next_cursor"]
        if cursor is None:
            break
    assert len(vistos) == len(set(vistos)) >= 5
    assert vistos == sorted(vistos)


@pytest.mark.parametrize("email", ["recepcion@test.test", "odonto@test.test"])
def test_otros_roles_403(client, email) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, email)
    assert client.get("/api/admin/sillones", headers=h).status_code == 403
    prof = client.post(
        "/api/admin/profesionales", json={"nombre": "x", "matricula": "y"}, headers=h
    )
    assert prof.status_code == 403
    prest = client.post(
        "/api/admin/prestaciones",
        json={"nombre": "x", "duracion_min": 30, "precio_referencia": "1"},
        headers=h,
    )
    assert prest.status_code == 403


def test_sin_token_401(client) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/admin/sillones").status_code == 401
    assert client.get("/api/admin/profesionales").status_code == 401


# --- profesionales ------------------------------------------------------------------------


def test_alta_profesional_con_flags_por_defecto(client, admin) -> None:  # type: ignore[no-untyped-def]
    body = _profesional(client, admin)
    assert body["agenda_activa"] is True and body["tercerizado"] is False
    assert body["usuario_id"] is None and body["sillon_ids"] == []
    flags = _profesional(client, admin, agenda_activa=False, tercerizado=True)
    assert flags["agenda_activa"] is False and flags["tercerizado"] is True


def test_matricula_repetida_en_a_409_y_en_b_201(client, admin) -> None:  # type: ignore[no-untyped-def]
    matricula = _u("MATDUP")
    _profesional(client, admin, matricula=matricula)
    dup = client.post(
        "/api/admin/profesionales", json={"nombre": "A2", "matricula": matricula}, headers=admin
    )
    assert dup.status_code == 409
    admin_b = bearer(client, "admin-b@test.test")
    en_b = client.post(
        "/api/admin/profesionales", json={"nombre": "B1", "matricula": matricula}, headers=admin_b
    )
    assert en_b.status_code == 201


def test_vinculo_usuario_valido_y_conflictos(client, admin, auth_data) -> None:  # type: ignore[no-untyped-def]
    uid = auth_data["user_ids"]["multi@test.test"]
    ok = _profesional(client, admin, usuario_id=uid)
    assert ok["usuario_id"] == uid
    dup = client.post(
        "/api/admin/profesionales",
        json={"nombre": "Vinc2", "matricula": _u("MV"), "usuario_id": uid},
        headers=admin,
    )
    assert dup.status_code == 409
    # Tras la baja del primero, el usuario puede vincularse otra vez.
    client.delete(f"/api/admin/profesionales/{ok['id']}", headers=admin)
    again = _profesional(client, admin, usuario_id=uid)
    client.delete(f"/api/admin/profesionales/{again['id']}", headers=admin)


def test_vinculo_con_usuario_de_otra_clinica_o_inexistente_422(  # type: ignore[no-untyped-def]
    client, admin, auth_data
) -> None:
    for uid in (auth_data["user_ids"]["admin-b@test.test"], 99999999):
        resp = client.post(
            "/api/admin/profesionales",
            json={"nombre": "X", "matricula": _u("MX"), "usuario_id": uid},
            headers=admin,
        )
        assert resp.status_code == 422


def test_vinculo_con_usuario_inactivo_422(client, admin, auth_data, session_factory) -> None:  # type: ignore[no-untyped-def]
    from app.domain.core.models import Usuario

    with session_factory() as session:
        inactivo = Usuario(
            clinica_id=auth_data["clinica_a"],
            email=f"inactivo{next(_n)}@test.test",
            password_hash="hash-sintetico",
            is_active=False,
        )
        session.add(inactivo)
        session.commit()
        uid = inactivo.id
    resp = client.post(
        "/api/admin/profesionales",
        json={"nombre": "X", "matricula": _u("MI"), "usuario_id": uid},
        headers=admin,
    )
    assert resp.status_code == 422


def test_patch_profesional_y_matricula_duplicada_409(client, admin) -> None:  # type: ignore[no-untyped-def]
    p1 = _profesional(client, admin)
    p2 = _profesional(client, admin)
    ok = client.patch(
        f"/api/admin/profesionales/{p1['id']}",
        json={"especialidad": "Ortodoncia", "tercerizado": True},
        headers=admin,
    )
    assert ok.status_code == 200
    assert ok.json()["especialidad"] == "Ortodoncia" and ok.json()["matricula"] == p1["matricula"]
    dup = client.patch(
        f"/api/admin/profesionales/{p1['id']}",
        json={"matricula": p2["matricula"]},
        headers=admin,
    )
    assert dup.status_code == 409


# --- habilitacion -------------------------------------------------------------------------


def _put(client, admin, pid, ids):  # type: ignore[no-untyped-def]
    return client.put(
        f"/api/admin/profesionales/{pid}/sillones", json={"sillon_ids": ids}, headers=admin
    )


def test_put_reemplaza_el_set_y_el_detalle_lo_expone(client, admin, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    s1, s2, s3 = catalogo_data["sillones"]
    pid = _profesional(client, admin)["id"]
    r1 = _put(client, admin, pid, [s3])
    assert r1.status_code == 200 and r1.json()["sillon_ids"] == [s3]
    r2 = _put(client, admin, pid, [s2, s1])
    assert r2.status_code == 200 and r2.json()["sillon_ids"] == sorted([s1, s2])
    detalle = client.get(f"/api/admin/profesionales/{pid}", headers=admin).json()
    assert detalle["sillon_ids"] == sorted([s1, s2])
    assert _put(client, admin, pid, []).json()["sillon_ids"] == []
    assert _put(client, admin, pid, [s3]).json()["sillon_ids"] == [s3]  # reactiva fila previa


def test_put_con_sillon_ajeno_o_inactivo_422_y_previo_intacto(  # type: ignore[no-untyped-def]
    client, admin, catalogo_data, session_factory
) -> None:
    s1, s2, _ = catalogo_data["sillones"]
    pid = _profesional(client, admin)["id"]
    _put(client, admin, pid, [s1])
    assert _put(client, admin, pid, [s2, catalogo_data["sillon_b"]]).status_code == 422
    inactivo_id = _sillon(client, admin)["id"]
    client.delete(f"/api/admin/sillones/{inactivo_id}", headers=admin)
    assert _put(client, admin, pid, [s2, inactivo_id]).status_code == 422
    assert _put(client, admin, pid, [99999999]).status_code == 422
    assert client.get(f"/api/admin/profesionales/{pid}", headers=admin).json()["sillon_ids"] == [s1]
    with session_factory() as session:
        filas = session.query(ProfesionalSillon).filter_by(profesional_id=pid, is_active=True).all()
        assert [f.sillon_id for f in filas] == [s1]


def test_put_sobre_profesional_ajeno_404_y_duplicados_422(client, admin, catalogo_data) -> None:  # type: ignore[no-untyped-def]
    assert _put(client, admin, catalogo_data["prof_b"], []).status_code == 404
    s1 = catalogo_data["sillones"][0]
    assert _put(client, admin, catalogo_data["prof_q"], [s1, s1]).status_code == 422
