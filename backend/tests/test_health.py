"""Health endpoint tests (TDD RED first). Synthetic data only."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_200_ok_without_auth() -> None:
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_unknown_route_returns_404_json_with_detail_no_trace() -> None:
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/ruta-que-no-existe")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "traceback" not in response.text.lower()


def test_unhandled_exception_returns_generic_500_without_trace() -> None:
    from fastapi import APIRouter

    app = create_app()
    router = APIRouter()

    @router.get("/api/boom")
    def boom() -> None:
        raise RuntimeError("synthetic failure for test")

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Error interno del servidor"
    assert "synthetic failure" not in response.text


import pytest  # noqa: E402


@pytest.mark.parametrize(
    ("partner", "key"),
    [(None, None), ("", ""), ("valor-desconocido", None), ("fake", "")],
)
def test_arranca_sin_credencial_de_recetas_ni_partner_valido(  # C-19 5.1
    monkeypatch: pytest.MonkeyPatch, partner: str | None, key: str | None
) -> None:
    for var, valor in (("RECETAS_PARTNER", partner), ("RECETAS_PARTNER_KEY", key)):
        if valor is None:
            monkeypatch.delenv(var, raising=False)
        else:
            monkeypatch.setenv(var, valor)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-sintetico-32-chars-minimo-0000")
    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.get("/api/health").status_code == 200
