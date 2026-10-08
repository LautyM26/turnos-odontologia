"""Resolver real Usuario->Profesional para require_own_agenda (C-04, cierra hook de C-03)."""

import pytest
from fastapi import APIRouter, Depends

from app.api.deps import AuthContext
from app.api.permissions import require_own_agenda
from app.domain.agenda.models import Profesional
from tests.integration.conftest import bearer, crear_usuario, make_test_client

probe = APIRouter()


@probe.get("/api/probe/agenda/{profesional_id}")
def probe_agenda(auth: AuthContext = Depends(require_own_agenda)) -> dict:  # noqa: B008
    return {"ok": True}


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return make_test_client(session_factory, monkeypatch, probe)


def test_odontologo_vinculado_accede_a_su_agenda_y_no_a_la_ajena(  # type: ignore[no-untyped-def]
    client, catalogo_data
) -> None:
    h = bearer(client, "odonto@test.test")
    assert client.get(f"/api/probe/agenda/{catalogo_data['prof_p']}", headers=h).status_code == 200
    assert client.get(f"/api/probe/agenda/{catalogo_data['prof_q']}", headers=h).status_code == 403


def test_odontologo_sin_vinculo_403(  # type: ignore[no-untyped-def]
    client, catalogo_data, session_factory, password_hash
) -> None:
    crear_usuario(
        session_factory, password_hash, catalogo_data["a"], "odonto-sin-vinculo@test.test",
        ["odontologo"],
    )  # fmt: skip
    h = bearer(client, "odonto-sin-vinculo@test.test")
    for pid in (catalogo_data["prof_p"], catalogo_data["prof_q"]):
        assert client.get(f"/api/probe/agenda/{pid}", headers=h).status_code == 403


def test_profesional_dado_de_baja_deja_de_resolver(  # type: ignore[no-untyped-def]
    client, catalogo_data, session_factory, password_hash
) -> None:
    uid = crear_usuario(
        session_factory, password_hash, catalogo_data["a"], "odonto-baja@test.test", ["odontologo"]
    )
    with session_factory() as session:
        prof = Profesional(
            clinica_id=catalogo_data["a"], nombre="Temp", matricula="PROPIA-TEMP", usuario_id=uid
        )
        session.add(prof)
        session.commit()
        pid = prof.id
    h = bearer(client, "odonto-baja@test.test")
    assert client.get(f"/api/probe/agenda/{pid}", headers=h).status_code == 200
    with session_factory() as session:
        session.get(Profesional, pid).is_active = False
        session.commit()
    assert client.get(f"/api/probe/agenda/{pid}", headers=h).status_code == 403


def test_admin_y_recepcionista_pasan_sin_vinculo(client, catalogo_data, auth_data) -> None:  # type: ignore[no-untyped-def]
    for email in (auth_data["admin_email"], "recepcion@test.test"):
        h = bearer(client, email)
        url = f"/api/probe/agenda/{catalogo_data['prof_q']}"
        assert client.get(url, headers=h).status_code == 200
