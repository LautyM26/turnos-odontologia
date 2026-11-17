"""RBAC, consentimiento de datos y aislamiento de las 3 rutas de recetas (C-19 3.7)."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.domain.auditoria.models import AuditoriaHC
from tests.integration.conftest import bearer, evolucion_sintetica, nuevo_paciente_c09

MED = {
    "nombre_generico": "amoxicilina",
    "presentacion": "500 mg",
    "cantidad": 1,
    "posologia": "c/8h",
}


def _cuerpo(evo: int):  # type: ignore[no-untyped-def]
    return {"tipo": "receta", "evolucion_id": evo, "diagnostico": "Dx sintetico",
            "items": [MED], "clave_idempotencia": str(uuid4())}  # fmt: skip


@pytest.fixture()
def pid(session_factory, staff_c09) -> int:  # type: ignore[no-untyped-def]
    return nuevo_paciente_c09(session_factory, staff_c09["a"])


@pytest.fixture()
def evo(session_factory, staff_c09, pid) -> int:  # type: ignore[no-untyped-def]
    return evolucion_sintetica(
        session_factory, staff_c09["a"], pid, staff_c09["o"], staff_c09["prof_o"]
    )


def _n_eventos(session_factory, pid: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(
            select(func.count()).select_from(AuditoriaHC).where(AuditoriaHC.paciente_id == pid)
        )


def _n_recetas(session_factory, pid: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(
            text("SELECT count(*) FROM receta_externa WHERE paciente_id=:p"), {"p": pid}
        )


def test_recepcionista_403_en_las_3_rutas_sin_partner_ni_auditoria(  # type: ignore[no-untyped-def]
    client_recetas, fake_partner, session_factory, pid, evo
) -> None:
    h = bearer(client_recetas, "recepcion@test.test")
    base = f"/api/pacientes/{pid}/recetas"
    antes = _n_eventos(session_factory, pid)
    for metodo, url, cuerpo in (
        ("POST", base, _cuerpo(evo)),
        ("GET", base, None),
        ("GET", f"{base}/1", None),
    ):
        assert client_recetas.request(metodo, url, json=cuerpo, headers=h).status_code == 403, url
    assert fake_partner.solicitudes == [] and _n_eventos(session_factory, pid) == antes


def test_admin_no_emite_403_pero_lee_200(
    client_recetas, fake_partner, session_factory, staff_c09, pid, evo
) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client_recetas, staff_c09["admin_solo_email"])
    base = f"/api/pacientes/{pid}/recetas"
    assert client_recetas.post(base, json=_cuerpo(evo), headers=h).status_code == 403
    assert client_recetas.get(base, headers=h).status_code == 200
    assert fake_partner.solicitudes == [] and _n_recetas(session_factory, pid) == 0


def test_sin_consentimiento_403_antes_del_cuerpo_y_del_501(  # type: ignore[no-untyped-def]
    client_recetas, fake_partner, monkeypatch, session_factory, staff_c09
) -> None:
    sin = nuevo_paciente_c09(session_factory, staff_c09["a"], consentimiento=False)
    h = bearer(client_recetas, staff_c09["o_email"])
    url = f"/api/pacientes/{sin}/recetas"
    assert client_recetas.post(url, json={"basura": 1}, headers=h).status_code == 403
    assert fake_partner.solicitudes == [] and _n_recetas(session_factory, sin) == 0
    # Sin partner configurado sigue siendo 403 (el gate clínico va antes).
    from app.api.recetas import partner_recetas

    client_recetas.app.dependency_overrides.pop(partner_recetas)
    monkeypatch.setenv("RECETAS_PARTNER", "")
    assert client_recetas.post(url, json={"basura": 1}, headers=h).status_code == 403


def test_paciente_de_otra_clinica_404_sin_partner(client_recetas, fake_partner, staff_c09) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client_recetas, staff_c09["o_email"])
    url = f"/api/pacientes/{staff_c09['pac_b']}/recetas"
    assert client_recetas.post(url, json=_cuerpo(1), headers=h).status_code == 404
    assert client_recetas.get(url, headers=h).status_code == 404
    assert fake_partner.solicitudes == []


def test_sin_token_401(client_recetas, pid) -> None:  # type: ignore[no-untyped-def]
    assert client_recetas.get(f"/api/pacientes/{pid}/recetas").status_code == 401
