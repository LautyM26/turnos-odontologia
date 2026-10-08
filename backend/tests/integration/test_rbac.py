"""RBAC por recurso en PG16 real: matriz del 03 codificada (C-03 5.2).

Contrato que C-05/C-12 invocarán. NUNCA SQLite. Solo datos sintéticos.
"""

import pytest
from fastapi import APIRouter, Depends

from app.api.deps import AuthContext
from app.api.permissions import (
    require_admin,
    require_anulacion_caja,
    require_clinico,
    require_own_agenda,
    require_sobreturno,
    set_resolver_agenda_propia,
)
from tests.integration.conftest import TEST_PASSWORD, make_test_client

rbac_router = APIRouter()


@rbac_router.get("/api/probe/admin")
def probe_admin(auth: AuthContext = Depends(require_admin())) -> dict:  # noqa: B008
    return {"ok": True, "sub": auth.sub}


@rbac_router.get("/api/probe/hc")
def probe_hc(auth: AuthContext = Depends(require_clinico())) -> dict:  # noqa: B008
    return {"ok": True}


@rbac_router.post("/api/probe/sobreturno")
def probe_sobreturno(auth: AuthContext = Depends(require_sobreturno())) -> dict:  # noqa: B008
    return {"ok": True}


@rbac_router.post("/api/probe/caja/anular")
def probe_anular(auth: AuthContext = Depends(require_anulacion_caja())) -> dict:  # noqa: B008
    return {"ok": True}


@rbac_router.get("/api/probe/agenda/{profesional_id}")
def probe_agenda_path(auth: AuthContext = Depends(require_own_agenda)) -> dict:  # noqa: B008
    return {"ok": True}


@rbac_router.get("/api/probe/agenda")
def probe_agenda_query(auth: AuthContext = Depends(require_own_agenda)) -> dict:  # noqa: B008
    return {"ok": True}


@pytest.fixture()
def rbac_client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    client = make_test_client(session_factory, monkeypatch, rbac_router)
    set_resolver_agenda_propia(None)
    yield client
    set_resolver_agenda_propia(None)


def _login(client, email: str):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )


def _bearer(client, email: str):  # type: ignore[no-untyped-def]
    resp = _login(client, email)
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_recepcionista_sin_acceso_clinico_403(rbac_client, auth_data) -> None:  # type: ignore[no-untyped-def]
    _ = auth_data
    h = _bearer(rbac_client, "recepcion@test.test")
    assert rbac_client.get("/api/probe/hc", headers=h).status_code == 403
    # Pero sí gestiona sobreturnos.
    assert rbac_client.post("/api/probe/sobreturno", headers=h).status_code == 200


def test_odontologo_sin_acceso_admin_403(rbac_client, auth_data) -> None:  # type: ignore[no-untyped-def]
    _ = auth_data
    h = _bearer(rbac_client, "odonto@test.test")
    assert rbac_client.get("/api/probe/admin", headers=h).status_code == 403
    assert rbac_client.get("/api/probe/hc", headers=h).status_code == 200


def test_admin_accede_a_todo(rbac_client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h = _bearer(rbac_client, auth_data["admin_email"])
    assert rbac_client.get("/api/probe/admin", headers=h).status_code == 200
    assert rbac_client.get("/api/probe/agenda/999", headers=h).status_code == 200


def test_sobreturno_sin_rol_403(rbac_client, auth_data) -> None:  # type: ignore[no-untyped-def]
    _ = auth_data
    h = _bearer(rbac_client, "odonto@test.test")
    resp = rbac_client.post("/api/probe/sobreturno", headers=h)
    assert resp.status_code == 403


def test_anulacion_caja_solo_admin(rbac_client, auth_data) -> None:  # type: ignore[no-untyped-def]
    h_recep = _bearer(rbac_client, "recepcion@test.test")
    assert rbac_client.post("/api/probe/caja/anular", headers=h_recep).status_code == 403
    h_admin = _bearer(rbac_client, auth_data["admin_email"])
    assert rbac_client.post("/api/probe/caja/anular", headers=h_admin).status_code == 200


def test_tercerizado_agenda_ajena_403_y_propia_ok(
    rbac_client, auth_data  # type: ignore[no-untyped-def]
) -> None:
    odo_id = auth_data["user_ids"]["odonto@test.test"]
    set_resolver_agenda_propia(lambda _session, sub: 10 if sub == odo_id else None)
    h = _bearer(rbac_client, "odonto@test.test")
    assert rbac_client.get("/api/probe/agenda/11", headers=h).status_code == 403
    assert rbac_client.get("/api/probe/agenda/10", headers=h).status_code == 200
    assert (
        rbac_client.get("/api/probe/agenda", params={"profesional_id": 10}, headers=h).status_code
        == 200
    )


def test_sin_vinculo_falla_cerrado_403(rbac_client, auth_data) -> None:  # type: ignore[no-untyped-def]
    _ = auth_data
    set_resolver_agenda_propia(None)  # pre-C-04: sin binding Usuario→Profesional
    h = _bearer(rbac_client, "odonto@test.test")
    assert rbac_client.get("/api/probe/agenda/10", headers=h).status_code == 403


def test_sin_token_401_en_todas(rbac_client) -> None:  # type: ignore[no-untyped-def]
    assert rbac_client.get("/api/probe/admin").status_code == 401
    assert rbac_client.get("/api/probe/hc").status_code == 401
    assert rbac_client.post("/api/probe/sobreturno").status_code == 401
    assert rbac_client.post("/api/probe/caja/anular").status_code == 401
    assert rbac_client.get("/api/probe/agenda/10").status_code == 401
