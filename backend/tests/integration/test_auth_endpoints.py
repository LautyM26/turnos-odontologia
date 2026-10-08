"""Endpoints /api/auth/* en PG16 real: login/me/refresh/logout + rate-limit.

Cubre C-03 3.3, 4.1, 4.2, 4.3 y 5.1 (cross-check tenant). NUNCA SQLite.
"""

import logging

import pytest
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import is_public_path, require_tenant_checked
from app.domain.auth.tokens import ACCESS
from app.domain.core.models import Usuario
from app.infrastructure.db import get_session
from tests.integration.conftest import TEST_JWT_SECRET, TEST_PASSWORD, make_test_client

probe_router = APIRouter()


@probe_router.get("/api/probe/tenant")
def probe_tenant(tenant_id: int = Depends(require_tenant_checked)) -> dict:  # noqa: B008
    return {"tenant_id": tenant_id}


@probe_router.get("/api/probe/usuarios")
def probe_usuarios(
    tenant_id: int = Depends(require_tenant_checked),  # noqa: B008
    session: Session = Depends(get_session),  # noqa: B008
) -> dict:
    emails = sorted(
        session.scalars(
            select(Usuario.email).where(Usuario.clinica_id == tenant_id)
        ).all()
    )
    return {"emails": emails}


@pytest.fixture()
def probe_client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return make_test_client(session_factory, monkeypatch, probe_router)


def _login(client, email: str, password: str = TEST_PASSWORD):  # type: ignore[no-untyped-def]
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _bearer(client, email: str):  # type: ignore[no-untyped-def]
    token = _login(client, email).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- 4.1 login + me -----------------------------------------------------------


def test_login_ok_emite_par_y_cookie(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    resp = _login(client, auth_data["admin_email"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["access_token"].count(".") == 2
    assert "refresh_token=" in resp.headers.get("set-cookie", "")
    cookie = resp.headers["set-cookie"]
    lowered = cookie.lower()
    assert "httponly" in lowered and "samesite=lax" in lowered and "Path=/api/auth" in cookie

    from app.domain.auth.tokens import verify_token

    claims = verify_token(body["access_token"], ACCESS, TEST_JWT_SECRET, "HS256")
    assert claims.tenant_id == auth_data["clinica_a"]
    assert "admin" in claims.roles


def test_login_fallo_generico_igual_para_inexistente_y_mala_clave(
    client, auth_data  # type: ignore[no-untyped-def]
) -> None:
    r1 = _login(client, "nadie@test.test", "cualquiera")
    r2 = _login(client, auth_data["admin_email"], "mala-clave-sintetica")
    assert r1.status_code == 401 and r2.status_code == 401
    assert r1.json() == r2.json() == {"detail": "Credenciales inválidas"}


def test_login_rechaza_campos_extra_422(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    resp = client.post(
        "/api/auth/login",
        json={"email": auth_data["admin_email"], "password": TEST_PASSWORD, "otro": 1},
    )
    assert resp.status_code == 422


def test_me_sin_token_401_con_mensaje_breaking(client) -> None:  # type: ignore[no-untyped-def]
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert "BREAKING C-03" in resp.json()["detail"]


def test_me_con_token_retorna_identidad(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    resp = client.get("/api/auth/me", headers=_bearer(client, auth_data["admin_email"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == auth_data["admin_email"]
    assert body["tenant_id"] == auth_data["clinica_a"]
    assert "admin" in body["roles"]


def test_access_expirado_401(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    from datetime import timedelta

    from app.domain.auth.tokens import issue_token

    token, _, _ = issue_token(
        sub=1,
        tenant_id=auth_data["clinica_a"],
        roles=["admin"],
        email=auth_data["admin_email"],
        type=ACCESS,
        secret=TEST_JWT_SECRET,
        ttl=timedelta(seconds=-300),
    )
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# --- 4.2 refresh + logout ------------------------------------------------------


def test_refresh_rota_y_replay_anterior_401(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    login_resp = _login(client, auth_data["admin_email"])
    viejas = login_resp.cookies
    r2 = client.post("/api/auth/refresh", cookies=dict(viejas))
    assert r2.status_code == 200, r2.text
    assert r2.json()["access_token"] != login_resp.json()["access_token"]
    replay = client.post("/api/auth/refresh", cookies=dict(viejas))
    assert replay.status_code == 401


def test_logout_invalida_access_y_limpia_cookie(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    headers = _bearer(client, auth_data["admin_email"])
    out = client.post("/api/auth/logout", headers=headers)
    assert out.status_code == 200
    assert "refresh_token=" in out.headers.get("set-cookie", "")
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 401


# --- 3.3 rate limit ------------------------------------------------------------


def test_sexto_login_en_60s_429_con_retry_after(client, auth_data) -> None:  # type: ignore[no-untyped-def]
    email = "ratelimit-unico@test.test"
    statuses = [
        _login(client, email, "mala-clave-sintetica").status_code for _ in range(6)
    ]
    assert statuses[:5] == [401] * 5
    assert statuses[5] == 429
    # El 429 trae Retry-After y no revela si el email existe.
    probe = _login(client, email, "mala-clave-sintetica")
    assert probe.status_code == 429
    assert probe.headers.get("Retry-After") == "60"


# --- 5.1 cross-check tenant ----------------------------------------------------


def test_scoped_sin_token_401(probe_client) -> None:  # type: ignore[no-untyped-def]
    assert probe_client.get("/api/probe/tenant").status_code == 401


def test_mismatch_header_vs_jwt_403(probe_client, auth_data) -> None:  # type: ignore[no-untyped-def]
    headers = _bearer(probe_client, auth_data["admin_email"])
    headers["X-Clinica-Id"] = str(auth_data["clinica_b"])
    resp = probe_client.get("/api/probe/tenant", headers=headers)
    assert resp.status_code == 403


def test_header_ausente_usa_jwt_y_match_ok(probe_client, auth_data) -> None:  # type: ignore[no-untyped-def]
    headers = _bearer(probe_client, auth_data["admin_email"])
    assert probe_client.get("/api/probe/tenant", headers=headers).json() == {
        "tenant_id": auth_data["clinica_a"]
    }
    headers["X-Clinica-Id"] = str(auth_data["clinica_a"])
    assert probe_client.get("/api/probe/tenant", headers=headers).json() == {
        "tenant_id": auth_data["clinica_a"]
    }


def test_jwt_ajeno_ve_cero_filas_de_otro_tenant(probe_client, auth_data) -> None:  # type: ignore[no-untyped-def]
    headers = _bearer(probe_client, auth_data["admin_email"])
    emails = probe_client.get("/api/probe/usuarios", headers=headers).json()["emails"]
    assert "admin-b@test.test" not in emails
    assert auth_data["admin_email"] in emails


def test_ruta_publica_sin_token_ok(probe_client) -> None:  # type: ignore[no-untyped-def]
    assert probe_client.get("/api/health").json() == {"status": "ok"}
    assert is_public_path("/api/auth/login")
    assert is_public_path("/api/webhooks/whatsapp/cualquiera")
    assert not is_public_path("/api/probe/tenant")


def test_toda_ruta_scoped_exige_auth() -> None:
    """Convención D8: ninguna ruta scoped nace sin auth por defecto."""
    import fnmatch

    from app.api.deps import get_current_user, require_tenant_checked
    from app.main import create_app

    app = create_app()
    protegidas = {id(get_current_user), id(require_tenant_checked)}
    infra = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}
    for route in app.routes:
        path = getattr(route, "path", "")
        if is_public_path(path) or any(fnmatch.fnmatch(path, p) for p in infra):
            continue
        if not getattr(route, "methods", None):
            continue
        deps = getattr(getattr(route, "dependant", None), "dependencies", [])
        assert any(id(d.call) in protegidas for d in deps), f"ruta sin auth: {path}"


# --- 4.3 eventos ---------------------------------------------------------------


def test_eventos_auth_en_log_estructurado(client, auth_data, caplog) -> None:  # type: ignore[no-untyped-def]
    caplog.set_level(logging.INFO, logger="turnos.auth")
    email = auth_data["admin_email"]
    _login(client, email)
    _login(client, email, "mala-clave-sintetica")
    texto = "\n".join(r.message for r in caplog.records if r.name == "turnos.auth")
    assert '"evento": "login_ok"' in texto
    assert '"evento": "login_ko"' in texto
    assert email in texto
    assert TEST_PASSWORD not in texto
