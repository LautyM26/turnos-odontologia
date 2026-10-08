"""RBAC clínico de pacientes y vínculo odontólogo-paciente (C-08 6.1/6.2)."""

import pytest
from sqlalchemy import func, select

from app.api.permissions import set_resolver_vinculo_paciente
from app.domain.auditoria.models import AuditoriaHC
from tests.integration.conftest import alta_paciente, bearer

FICHA = {"version_esperada": 0, "alergias": "sintetica"}


@pytest.fixture()
def reset_vinculo():  # type: ignore[no-untyped-def]
    yield
    set_resolver_vinculo_paciente(None)


@pytest.fixture()
def paciente_a(client, auth_data):  # type: ignore[no-untyped-def]
    """Paciente de A sin consentimiento (alta por recepción)."""
    h = bearer(client, "recepcion@test.test")
    return alta_paciente(client, h).json()["id"]


@pytest.fixture()
def paciente_a_consentido(client, paciente_a):  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    client.patch(f"/api/pacientes/{paciente_a}", json={"consentimiento_datos": True}, headers=h)
    return paciente_a


def _rutas_clinicas(pid: int):  # type: ignore[no-untyped-def]
    return [
        ("GET", f"/api/pacientes/{pid}/ficha", None),
        ("PUT", f"/api/pacientes/{pid}/ficha", FICHA),
        ("GET", f"/api/pacientes/{pid}/ficha/versiones", None),
        ("GET", f"/api/pacientes/{pid}/adjuntos", None),
        ("GET", f"/api/pacientes/{pid}/adjuntos/1/contenido", None),
        ("POST", f"/api/pacientes/{pid}/adjuntos", None),
    ]


def _eventos_leer(session_factory, pid: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return session.scalar(
            select(func.count())
            .select_from(AuditoriaHC)
            .where(AuditoriaHC.paciente_id == pid, AuditoriaHC.accion == "leer")
        )


def test_paciente_enlace_no_accede_a_api_privada(client, staff_c08) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "enlace@test.test")
    assert client.get("/api/pacientes", headers=h).status_code == 403
    assert alta_paciente(client, h).status_code == 403


def test_recepcion_recibe_403_en_todo_endpoint_clinico_sin_auditar(  # type: ignore[no-untyped-def]
    client, session_factory, paciente_a_consentido
) -> None:
    pid = paciente_a_consentido
    h = bearer(client, "recepcion@test.test")
    for metodo, url, body in _rutas_clinicas(pid):
        resp = client.request(metodo, url, json=body, headers=h)
        assert resp.status_code == 403, (metodo, url)
    assert _eventos_leer(session_factory, pid) == 0


def test_admin_sin_odontologo_lee_pero_no_escribe(  # type: ignore[no-untyped-def]
    client, session_factory, auth_data, paciente_a_consentido
) -> None:
    pid = paciente_a_consentido
    h = bearer(client, auth_data["admin_email"])
    assert client.get(f"/api/pacientes/{pid}/ficha", headers=h).status_code == 200
    put = client.put(f"/api/pacientes/{pid}/ficha", json=FICHA, headers=h)
    assert put.status_code == 403 and put.json()["detail"] == "Rol insuficiente"
    post = client.post(f"/api/pacientes/{pid}/adjuntos", headers=h)
    assert post.status_code == 403 and post.json()["detail"] == "Rol insuficiente"


def test_dueno_admin_y_odontologo_supera_el_gate_de_rol(  # type: ignore[no-untyped-def]
    client, staff_c08, paciente_a
) -> None:
    h = bearer(client, "dueno@test.test")
    # paciente SIN consentimiento: el 403 es por consentimiento, no por rol.
    put = client.put(f"/api/pacientes/{paciente_a}/ficha", json=FICHA, headers=h)
    assert put.status_code == 403
    assert "consentimiento" in put.json()["detail"].lower()
    assert client.get(f"/api/pacientes/{paciente_a}/ficha", headers=h).status_code == 200


def test_odontologo_no_consulta_auditoria(client, paciente_a) -> None:  # type: ignore[no-untyped-def]
    for email in ("odonto@test.test", "recepcion@test.test"):
        h = bearer(client, email)
        assert client.get(f"/api/pacientes/{paciente_a}/auditoria", headers=h).status_code == 403


def test_odontologo_regla_interina_lee_y_queda_evento(  # type: ignore[no-untyped-def]
    client, session_factory, paciente_a
) -> None:
    h = bearer(client, "odonto@test.test")
    antes = _eventos_leer(session_factory, paciente_a)
    assert client.get(f"/api/pacientes/{paciente_a}/ficha", headers=h).status_code == 200
    assert _eventos_leer(session_factory, paciente_a) == antes + 1


def test_resolver_niega_acceso_403_en_ficha_y_adjuntos(  # type: ignore[no-untyped-def]
    client, paciente_a, reset_vinculo
) -> None:
    h = bearer(client, "odonto@test.test")
    set_resolver_vinculo_paciente(lambda *_: False)
    for url in (
        f"/api/pacientes/{paciente_a}/ficha",
        f"/api/pacientes/{paciente_a}/ficha/versiones",
        f"/api/pacientes/{paciente_a}/adjuntos",
    ):
        assert client.get(url, headers=h).status_code == 403, url


def test_resolver_que_lanza_excepcion_falla_cerrado(client, paciente_a, reset_vinculo) -> None:  # type: ignore[no-untyped-def]
    def roto(*_):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    h = bearer(client, "odonto@test.test")
    set_resolver_vinculo_paciente(roto)
    assert client.get(f"/api/pacientes/{paciente_a}/ficha", headers=h).status_code == 403


def test_otra_clinica_404_sin_invocar_resolver(  # type: ignore[no-untyped-def]
    client, paciente_a, auth_data, reset_vinculo
) -> None:
    llamadas: list[int] = []
    set_resolver_vinculo_paciente(lambda *a: llamadas.append(1) or True)
    hb = bearer(client, "admin-b@test.test")
    assert client.get(f"/api/pacientes/{paciente_a}/ficha", headers=hb).status_code == 404
    assert llamadas == []


def test_admin_y_dueno_no_pasan_por_el_resolver(  # type: ignore[no-untyped-def]
    client, auth_data, staff_c08, paciente_a, reset_vinculo
) -> None:
    llamadas: list[int] = []
    set_resolver_vinculo_paciente(lambda *a: llamadas.append(1) or False)
    for email in (auth_data["admin_email"], "dueno@test.test"):
        h = bearer(client, email)
        assert client.get(f"/api/pacientes/{paciente_a}/ficha", headers=h).status_code == 200
    assert llamadas == []


def test_resolver_recibe_sesion_auth_y_paciente(client, paciente_a, reset_vinculo) -> None:  # type: ignore[no-untyped-def]
    vistos = []

    def resolver(session, auth, paciente):  # type: ignore[no-untyped-def]
        vistos.append((auth.email, paciente.id))
        return True

    set_resolver_vinculo_paciente(resolver)
    h = bearer(client, "odonto@test.test")
    client.get(f"/api/pacientes/{paciente_a}/ficha", headers=h)
    assert vistos == [("odonto@test.test", paciente_a)]
