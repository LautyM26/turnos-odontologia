"""Sesión QR por API (C-15 7.1, D9): estado, QR, reconexión, RBAC y 501. PG16 real, sintético."""

import pytest

from app.infrastructure.whatsapp.fake import FakeMensajeria
from app.infrastructure.whatsapp.puerto import GatewayNoDisponible, NoConfigurado
from tests.integration.conftest import bearer, make_test_client

URL = "/api/whatsapp/sesion"


class GatewayCaido(FakeMensajeria):
    def estado(self, sesion: str):  # type: ignore[no-untyped-def]
        raise GatewayNoDisponible("sin red")

    def iniciar(self, sesion, webhook_url, hmac_key):  # type: ignore[no-untyped-def]
        raise GatewayNoDisponible("sin red")


def _cliente(session_factory, monkeypatch, mensajeria):  # type: ignore[no-untyped-def]
    from app.api.whatsapp import mensajeria_wa

    monkeypatch.setenv("WHATSAPP_WEBHOOK_HMAC_KEY", "hmac-sintetica")
    monkeypatch.setenv("APP_BASE_URL", "https://api.sintetica.invalid")
    client = make_test_client(session_factory, monkeypatch)
    client.app.dependency_overrides[mensajeria_wa] = lambda: mensajeria
    return client


def test_admin_ve_qr_cuando_hay_que_escanear(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, turnos_data, auth_data
) -> None:
    fake = FakeMensajeria()
    fake.estado_sesion = "escanear_qr"
    c = _cliente(session_factory, monkeypatch, fake)
    r = c.get(URL, headers=bearer(c, auth_data["admin_email"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["estado"] == "escanear_qr" and body["qr"] and body["en_vivo"] is True


def test_sesion_activa_sin_qr_y_recepcion_puede_ver(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, turnos_data
) -> None:
    c = _cliente(session_factory, monkeypatch, FakeMensajeria())
    r = c.get(URL, headers=bearer(c, "recepcion@test.test"))
    assert r.status_code == 200
    assert r.json()["estado"] == "activa" and r.json()["qr"] is None
    assert r.json()["numero"] == "+5491100009999"


def test_odontologo_403_y_sin_token_401(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    c = _cliente(session_factory, monkeypatch, FakeMensajeria())
    assert c.get(URL, headers=bearer(c, "odonto@test.test")).status_code == 403
    assert c.get(URL).status_code == 401
    assert c.post(f"{URL}/reconectar").status_code == 401


def test_sin_gateway_501_y_health_200(session_factory, monkeypatch, auth_data) -> None:  # type: ignore[no-untyped-def]
    c = _cliente(session_factory, monkeypatch, NoConfigurado("Configurá WHATSAPP_GATEWAY"))
    admin = bearer(c, auth_data["admin_email"])
    r = c.get(URL, headers=admin)
    assert r.status_code == 501 and "WHATSAPP_GATEWAY" in r.json()["detail"]
    assert c.post(f"{URL}/reconectar", headers=admin).status_code == 501
    assert c.get("/api/health").status_code == 200


def test_gateway_caido_devuelve_ultimo_estado_conocido(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, auth_data
) -> None:
    c = _cliente(session_factory, monkeypatch, FakeMensajeria())
    admin = bearer(c, auth_data["admin_email"])
    assert c.get(URL, headers=admin).json()["estado"] == "activa"  # queda persistido
    c2 = _cliente(session_factory, monkeypatch, GatewayCaido())
    r = c2.get(URL, headers=bearer(c2, auth_data["admin_email"]))
    assert r.status_code == 200
    assert r.json()["estado"] == "activa" and r.json()["en_vivo"] is False
    assert c2.post(f"{URL}/reconectar", headers=admin).status_code == 503


def test_reconectar_solo_admin_y_configura_webhook(session_factory, monkeypatch, auth_data) -> None:  # type: ignore[no-untyped-def]
    fake = FakeMensajeria()
    fake.estado_sesion = "caida"
    c = _cliente(session_factory, monkeypatch, fake)
    assert c.post(f"{URL}/reconectar", headers=bearer(c, "recepcion@test.test")).status_code == 403
    assert fake.iniciadas == []
    r = c.post(f"{URL}/reconectar", headers=bearer(c, auth_data["admin_email"]))
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "escanear_qr" and r.json()["qr"]
    a = auth_data["clinica_a"]
    assert fake.iniciadas == [
        (f"clinica-{a}", "https://api.sintetica.invalid/api/webhooks/whatsapp", "hmac-sintetica")
    ]


@pytest.mark.parametrize("email", ["admin-b@test.test"])
def test_cada_clinica_su_sesion(session_factory, monkeypatch, auth_data, email) -> None:  # type: ignore[no-untyped-def]
    fake = FakeMensajeria()
    c = _cliente(session_factory, monkeypatch, fake)
    c.post(f"{URL}/reconectar", headers=bearer(c, email))
    assert fake.iniciadas[0][0] == f"clinica-{auth_data['clinica_b']}"
