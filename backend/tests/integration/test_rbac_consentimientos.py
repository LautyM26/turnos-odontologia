"""RBAC, consentimiento de datos y aislamiento de las 4 rutas de consentimientos (C-18 3.5)."""

import pytest
from sqlalchemy import func, select, text

from app.domain.auditoria.models import AuditoriaHC
from tests.integration.conftest import bearer, nuevo_paciente_c09

HASH = "a" * 64
FIRMA = {"acepta": True, "firmante_nombre": "Firmante Sintetico", "firmante_dni": "90000001",
         "texto_hash": HASH}  # fmt: skip


@pytest.fixture()
def pid(session_factory, staff_c09) -> int:  # type: ignore[no-untyped-def]
    return nuevo_paciente_c09(session_factory, staff_c09["a"])


def _rutas(pid: int, cid: int):  # type: ignore[no-untyped-def]
    base = f"/api/pacientes/{pid}/consentimientos"
    return [
        ("POST", base, {"tipo": "extraccion"}),
        ("GET", base, None),
        ("GET", f"{base}/{cid}", None),
        ("POST", f"{base}/{cid}/firmar", FIRMA),
    ]


def _n_eventos(session_factory, pid: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(
            select(func.count()).select_from(AuditoriaHC).where(AuditoriaHC.paciente_id == pid)
        )


def _n_docs(session_factory, pid: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(
            text("SELECT count(*) FROM consentimiento WHERE paciente_id=:p"), {"p": pid}
        )


@pytest.fixture()
def cid(client, staff_c09, pid) -> int:  # type: ignore[no-untyped-def]
    h = bearer(client, staff_c09["o_email"])
    return client.post(
        f"/api/pacientes/{pid}/consentimientos", json={"tipo": "extraccion"}, headers=h
    ).json()["id"]


def test_recepcionista_403_en_las_4_rutas_sin_auditar(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, pid, cid
) -> None:
    h = bearer(client, "recepcion@test.test")
    antes = _n_eventos(session_factory, pid)
    for metodo, url, cuerpo in _rutas(pid, cid):
        assert client.request(metodo, url, json=cuerpo, headers=h).status_code == 403, url
    assert _n_eventos(session_factory, pid) == antes
    assert _n_docs(session_factory, pid) == 1


def test_paciente_enlace_y_sin_token(client, staff_c09, pid, cid) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, staff_c09["enlace_email"])
    for metodo, url, cuerpo in _rutas(pid, cid):
        assert client.request(metodo, url, json=cuerpo, headers=h).status_code == 403, url
        assert client.request(metodo, url, json=cuerpo).status_code == 401, url


def test_admin_lee_200_y_genera_o_firma_403(client, session_factory, staff_c09, pid, cid) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, staff_c09["admin_solo_email"])
    esperado = {("POST", ""): 403, ("GET", ""): 200, ("GET", f"/{cid}"): 200,
                ("POST", f"/{cid}/firmar"): 403}  # fmt: skip
    for metodo, url, cuerpo in _rutas(pid, cid):
        sufijo = url.removeprefix(f"/api/pacientes/{pid}/consentimientos")
        assert client.request(metodo, url, json=cuerpo, headers=h).status_code == esperado[
            (metodo, sufijo)
        ], url
    assert _n_docs(session_factory, pid) == 1


def test_sin_consentimiento_de_datos_403_antes_de_validar_el_cuerpo(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09
) -> None:
    sin = nuevo_paciente_c09(session_factory, staff_c09["a"], consentimiento=False)
    h = bearer(client, staff_c09["o_email"])
    base = f"/api/pacientes/{sin}/consentimientos"
    # Cuerpo inválido a propósito: el 403 gana al 422.
    assert client.post(base, json={"tipo": "no-existe"}, headers=h).status_code == 403
    assert client.post(f"{base}/1/firmar", json={"basura": 1}, headers=h).status_code == 403
    assert _n_docs(session_factory, sin) == 0
    # Leer sigue permitido (el gate solo corta escrituras clínicas).
    assert client.get(base, headers=h).status_code == 200


def test_paciente_de_otra_clinica_404(client, staff_c09, cid) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, staff_c09["o_email"])
    for metodo, url, cuerpo in _rutas(staff_c09["pac_b"], cid):
        assert client.request(metodo, url, json=cuerpo, headers=h).status_code == 404, url


def test_firma_de_cid_de_otra_clinica_con_paciente_propio_404(  # type: ignore[no-untyped-def]
    client, session_factory, staff_c09, auth_data, pid
) -> None:
    # Consentimiento de la clínica B (insertado por SQL: B no tiene odontólogos en el seed).
    with session_factory() as s:
        cid_b = s.execute(
            text(
                "INSERT INTO consentimiento (clinica_id, paciente_id, tipo, texto, texto_version, "
                "texto_hash, autor_usuario_id) VALUES (:c, :p, 'extraccion', 'T', '1.0', :h, :u) "
                "RETURNING id"
            ),
            {"c": staff_c09["b"], "p": staff_c09["pac_b"], "h": HASH,
             "u": auth_data["user_ids"]["admin-b@test.test"]},
        ).scalar()  # fmt: skip
        s.commit()
    h = bearer(client, staff_c09["o_email"])
    r = client.post(
        f"/api/pacientes/{pid}/consentimientos/{cid_b}/firmar", json=FIRMA, headers=h
    )
    assert r.status_code == 404
    with session_factory() as s:
        assert s.scalar(
            text("SELECT count(*) FROM consentimiento_firma WHERE consentimiento_id=:c"),
            {"c": cid_b},
        ) == 0
