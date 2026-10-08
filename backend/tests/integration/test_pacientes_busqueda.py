"""Búsqueda keyset de pacientes (C-08 5.5): DNI/teléfono normalizados, nombre sin acentos."""

from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql

from app.domain.pacientes.models import Paciente
from app.domain.pacientes.servicios import filtros_busqueda
from tests.integration.conftest import alta_paciente, bearer


def test_busqueda_por_dni_con_formato_distinto(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, h, dni="91.200.001").json()["id"]
    resp = client.get("/api/pacientes", params={"dni": "91.200.001"}, headers=h)
    assert resp.status_code == 200
    assert [p["id"] for p in resp.json()["items"]] == [pid]
    sin = client.get("/api/pacientes", params={"dni": "91200999"}, headers=h)
    assert sin.json()["items"] == []


def test_busqueda_por_telefono_local_encuentra_e164(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, h, dni="91200002", telefono="+5491155551234").json()["id"]
    resp = client.get("/api/pacientes", params={"telefono": "011 15 5555-1234"}, headers=h)
    assert [p["id"] for p in resp.json()["items"]] == [pid]


def test_busqueda_por_nombre_sin_acentos_ni_mayusculas(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    pid = alta_paciente(client, h, dni="91200003", apellido="Pérezzz", nombre="José").json()["id"]
    for q in ("perezzz", "PEREZ", "jose", "ezzz jo"):
        ids = [
            p["id"]
            for p in client.get("/api/pacientes", params={"q": q}, headers=h).json()["items"]
        ]
        assert pid in ids, q
    assert client.get("/api/pacientes", params={"q": "zzzqq"}, headers=h).json()["items"] == []


def test_q_comodines_se_escapan_y_minimo_3(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    alta_paciente(client, h, dni="91200004")
    assert client.get("/api/pacientes", params={"q": "%%%"}, headers=h).json()["items"] == []
    for q in ("pe", " a ", ""):
        assert client.get("/api/pacientes", params={"q": q}, headers=h).status_code == 422


def test_dni_o_telefono_invalidos_422(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    assert client.get("/api/pacientes", params={"dni": "12AB"}, headers=h).status_code == 422
    assert client.get("/api/pacientes", params={"telefono": "abc"}, headers=h).status_code == 422


def test_paginacion_keyset_sin_repetidos_ni_faltantes(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    creados = {
        alta_paciente(client, h, apellido="Paginacionxyz", dni=f"9300{n:04d}").json()["id"]
        for n in range(45)
    }
    vistos: list[int] = []
    cursor = None
    paginas = 0
    while True:
        params = {"q": "paginacionxyz", "limit": 20}
        if cursor is not None:
            params["after_id"] = cursor
        cuerpo = client.get("/api/pacientes", params=params, headers=h).json()
        vistos += [p["id"] for p in cuerpo["items"]]
        paginas += 1
        cursor = cuerpo["next_cursor"]
        if cursor is None:
            break
    assert paginas == 3
    assert len(vistos) == len(set(vistos)) == 45
    assert set(vistos) == creados


def test_limites_de_limit_y_default_50(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    for limit in (0, 201, -1):
        assert client.get("/api/pacientes", params={"limit": limit}, headers=h).status_code == 422
    resp = client.get("/api/pacientes", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()["items"]) <= 50


def test_busqueda_no_cruza_tenants(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    ha = bearer(client, "recepcion@test.test")
    hb = bearer(client, "admin-b@test.test")
    alta_paciente(client, hb, dni="91200005", apellido="Soloenb")
    res_a = client.get("/api/pacientes", params={"dni": "91200005"}, headers=ha)
    assert res_a.json()["items"] == []
    assert client.get("/api/pacientes", params={"q": "soloenb"}, headers=ha).json()["items"] == []
    res_b = client.get("/api/pacientes", params={"dni": "91200005"}, headers=hb)
    assert len(res_b.json()["items"]) == 1


def test_explain_busqueda_por_dni_usa_indice_tenant(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    stmt = select(Paciente.id).where(
        Paciente.clinica_id == auth_data["clinica_a"], *filtros_busqueda(dni="91.200.001")
    )
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    with session_factory() as session:
        session.execute(
            text(
                "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, "
                "nombre_busqueda, es_seed) "
                "SELECT :c, 'N', 'Explain', '92' || lpad(g::text, 6, '0'), "
                "'+5491155550001', 'explain n', true FROM generate_series(1, 200) g "
                "ON CONFLICT DO NOTHING"
            ),
            {"c": auth_data["clinica_a"]},
        )
        session.execute(text("ANALYZE paciente"))
        session.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(r[0] for r in session.execute(text("EXPLAIN " + sql)))
    assert "uq_paciente_clinica_dni" in plan, plan
    cond = plan.split("Index Cond", 1)[1].splitlines()[0]
    assert "dni = " in cond, plan
