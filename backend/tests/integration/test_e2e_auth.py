"""E2E por tenant en PG16 real (C-03 6.2).

Flujo: seed → login → me → refresh → replay → logout → cross-tenant.
"""

from tests.integration.conftest import TEST_PASSWORD, make_test_client
from tests.integration.test_auth_endpoints import probe_router


def _client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return make_test_client(session_factory, monkeypatch, probe_router)


def test_flujo_e2e_auth_por_tenant(session_factory, monkeypatch, auth_data):  # type: ignore[no-untyped-def]
    client = _client(session_factory, monkeypatch)
    email_a = auth_data["admin_email"]
    email_b = "admin-b@test.test"

    # 1. seed C-02 ya aplicado por auth_data; login tenant A.
    login = client.post(
        "/api/auth/login", json={"email": email_a, "password": TEST_PASSWORD}
    )
    assert login.status_code == 200, login.text
    access_a = login.json()["access_token"]
    cookies_a = dict(login.cookies)
    headers_a = {"Authorization": f"Bearer {access_a}"}

    # 2. me con JWT válido.
    me = client.get("/api/auth/me", headers=headers_a)
    assert me.status_code == 200
    assert me.json()["tenant_id"] == auth_data["clinica_a"]

    # 3. refresh rota el par.
    rotated = client.post("/api/auth/refresh", cookies=cookies_a)
    assert rotated.status_code == 200, rotated.text
    access_nuevo = rotated.json()["access_token"]
    assert access_nuevo != access_a
    headers_nuevo = {"Authorization": f"Bearer {access_nuevo}"}

    # 4. replay del refresh anterior → 401.
    assert client.post("/api/auth/refresh", cookies=cookies_a).status_code == 401

    # 5. logout revoca la sesión vigente.
    out = client.post("/api/auth/logout", headers=headers_nuevo)
    assert out.status_code == 200

    # 6. el access posterior al logout → 401.
    assert client.get("/api/auth/me", headers=headers_nuevo).status_code == 401

    # 7. cross-tenant: JWT de B no ve filas de A y el mismatch → 403.
    login_b = client.post(
        "/api/auth/login", json={"email": email_b, "password": TEST_PASSWORD}
    )
    assert login_b.status_code == 200, login_b.text
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}
    emails_b = client.get("/api/probe/usuarios", headers=headers_b).json()["emails"]
    assert emails_b == ["admin-b@test.test"]
    mismatch = dict(headers_b, **{"X-Clinica-Id": str(auth_data["clinica_a"])})
    assert client.get("/api/probe/tenant", headers=mismatch).status_code == 403
