"""RBAC y vínculo de las rutas clínicas de C-09 (7 rutas). PG16 real, datos sintéticos."""

import pytest
from sqlalchemy import func, select

from app.api.permissions import set_resolver_vinculo_paciente
from app.domain.auditoria.models import AuditoriaHC
from tests.integration.conftest import bearer, nuevo_paciente_c09

ODONTO = {"version_esperada": 0, "denticion": "permanente", "piezas": {}}
EVO = {"texto": "Control sintetico"}


@pytest.fixture()
def pid(session_factory, staff_c09) -> int:  # type: ignore[no-untyped-def]
    return nuevo_paciente_c09(session_factory, staff_c09["a"])


def _rutas(pid: int, evo_id: int):  # type: ignore[no-untyped-def]
    base = f"/api/pacientes/{pid}"
    return [
        ("GET", f"{base}/odontograma", None),
        ("GET", f"{base}/odontograma/actual", None),
        ("POST", f"{base}/odontograma", ODONTO),
        ("GET", f"{base}/evoluciones", None),
        ("POST", f"{base}/evoluciones", EVO),
        ("GET", f"{base}/evoluciones/{evo_id}", None),
        ("GET", f"{base}/historia", None),
    ]


def _llamar(client, metodo, url, cuerpo, h):  # type: ignore[no-untyped-def]
    return client.request(metodo, url, json=cuerpo, headers=h)


def _n_eventos(session_factory, pid: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(
            select(func.count()).select_from(AuditoriaHC).where(AuditoriaHC.paciente_id == pid)
        )


@pytest.fixture()
def evo_id(client, staff_c09, pid) -> int:  # type: ignore[no-untyped-def]
    h = bearer(client, staff_c09["o_email"])
    return client.post(f"/api/pacientes/{pid}/evoluciones", json=EVO, headers=h).json()["id"]


def test_recepcionista_403_en_las_7_rutas_sin_evento(
    client, session_factory, staff_c09, pid, evo_id
) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    antes = _n_eventos(session_factory, pid)
    for metodo, url, cuerpo in _rutas(pid, evo_id):
        assert _llamar(client, metodo, url, cuerpo, h).status_code == 403, (metodo, url)
    assert _n_eventos(session_factory, pid) == antes


def test_paciente_enlace_403_en_las_7_rutas(client, staff_c09, pid, evo_id) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, staff_c09["enlace_email"])
    for metodo, url, cuerpo in _rutas(pid, evo_id):
        assert _llamar(client, metodo, url, cuerpo, h).status_code == 403, (metodo, url)


def test_sin_token_401(client, pid, evo_id) -> None:  # type: ignore[no-untyped-def]
    for metodo, url, cuerpo in _rutas(pid, evo_id):
        assert _llamar(client, metodo, url, cuerpo, {}).status_code == 401, (metodo, url)


def test_admin_sin_rol_odontologo_lee_200_y_escribe_403(
    client, session_factory, staff_c09, pid, evo_id
) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, staff_c09["admin_solo_email"])
    for metodo, url, cuerpo in _rutas(pid, evo_id):
        esperado = 200 if metodo == "GET" else 403
        assert _llamar(client, metodo, url, cuerpo, h).status_code == esperado, (metodo, url)


def test_dueno_admin_y_odontologo_escribe_201(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, staff_c09["dueno_email"])
    assert (
        client.post(f"/api/pacientes/{pid}/odontograma", json=ODONTO, headers=h).status_code == 201
    )
    r = client.post(f"/api/pacientes/{pid}/evoluciones", json=EVO, headers=h)
    assert r.status_code == 201 and r.json()["profesional_id"] == staff_c09["prof_dueno"]


def test_resolver_que_niega_403_en_odontograma_evoluciones_e_historia(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid, evo_id
) -> None:
    h = bearer(client, staff_c09["o_email"])
    set_resolver_vinculo_paciente(lambda session, auth, paciente: False)
    try:
        for metodo, url, cuerpo in _rutas(pid, evo_id):
            assert _llamar(client, metodo, url, cuerpo, h).status_code == 403, (metodo, url)
        # El admin no pasa por el resolver: sigue leyendo.
        ha = bearer(client, staff_c09["admin_solo_email"])
        assert client.get(f"/api/pacientes/{pid}/historia", headers=ha).status_code == 200
    finally:
        set_resolver_vinculo_paciente(None)


def test_resolver_que_lanza_excepcion_falla_cerrado_403(client, staff_c09, pid, evo_id) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, staff_c09["o_email"])

    def roto(session, auth, paciente):  # type: ignore[no-untyped-def]
        raise RuntimeError("resolver caido")

    set_resolver_vinculo_paciente(roto)
    try:
        for metodo, url, cuerpo in _rutas(pid, evo_id):
            assert _llamar(client, metodo, url, cuerpo, h).status_code == 403, (metodo, url)
    finally:
        set_resolver_vinculo_paciente(None)


def test_paciente_de_otra_clinica_404_sin_invocar_el_resolver(client, staff_c09) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, staff_c09["o_email"])
    llamadas: list[int] = []

    def espia(session, auth, paciente):  # type: ignore[no-untyped-def]
        llamadas.append(paciente.id)
        return True

    set_resolver_vinculo_paciente(espia)
    try:
        for metodo, url, cuerpo in _rutas(staff_c09["pac_b"], 1):
            assert _llamar(client, metodo, url, cuerpo, h).status_code == 404, (metodo, url)
    finally:
        set_resolver_vinculo_paciente(None)
    assert llamadas == []
