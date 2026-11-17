"""Adapter WAHA (C-15 3.2, D1) contra ``httpx.MockTransport``: sin red ni WhatsApp real."""

import json

import httpx
import pytest

from app.infrastructure.whatsapp.puerto import GatewayNoDisponible, SesionNoActiva
from app.infrastructure.whatsapp.waha import WahaMensajeria

URL = "http://gw.invalid:3000"


def _waha(handler) -> tuple[WahaMensajeria, list[httpx.Request]]:  # type: ignore[no-untyped-def]
    vistos: list[httpx.Request] = []

    def _h(req: httpx.Request) -> httpx.Response:
        vistos.append(req)
        return handler(req)

    return WahaMensajeria(URL, "k-sintetica", transport=httpx.MockTransport(_h)), vistos


def test_send_text_contrato_y_id() -> None:
    w, vistos = _waha(lambda r: httpx.Response(201, json={"id": "true_x@c.us_ABC"}))
    assert w.enviar_texto("clinica-1", "+5491100000001", "hola") == "true_x@c.us_ABC"
    req = vistos[0]
    assert req.method == "POST" and req.url.path == "/api/sendText"
    assert req.headers["X-Api-Key"] == "k-sintetica"
    assert json.loads(req.content) == {
        "session": "clinica-1", "chatId": "5491100000001@c.us", "text": "hola",
    }  # fmt: skip


def test_send_text_id_como_objeto() -> None:
    w, _ = _waha(lambda r: httpx.Response(201, json={"id": {"_serialized": "true_y@c.us_Z"}}))
    assert w.enviar_texto("clinica-1", "+5491100000001", "hola") == "true_y@c.us_Z"


@pytest.mark.parametrize(
    ("waha", "interno"),
    [("WORKING", "activa"), ("SCAN_QR_CODE", "escanear_qr"), ("STARTING", "iniciando"),
     ("FAILED", "caida"), ("STOPPED", "detenida"), ("PASSKEY_REQUIRED", "desconocido")],
)  # fmt: skip
def test_mapeo_de_estados(waha: str, interno: str) -> None:
    body = {"name": "clinica-1", "status": waha, "me": {"id": "5491100000009@c.us"}}
    w, vistos = _waha(lambda r: httpx.Response(200, json=body))
    estado = w.estado("clinica-1")
    assert estado.estado == interno and estado.numero == "+5491100000009"
    assert vistos[0].url.path == "/api/sessions/clinica-1"


def test_sesion_inexistente_es_desconocido() -> None:
    w, _ = _waha(lambda r: httpx.Response(404, json={"message": "not found"}))
    assert w.estado("clinica-1").estado == "desconocido"


def test_qr_base64() -> None:
    w, vistos = _waha(lambda r: httpx.Response(200, json={"mimetype": "image/png", "data": "QUJD"}))
    assert w.qr("clinica-1") == "QUJD"
    assert vistos[0].url.path == "/api/clinica-1/auth/qr"
    assert vistos[0].headers["Accept"] == "application/json"


def test_iniciar_crea_sesion_con_webhook_firmado() -> None:
    def h(r: httpx.Request) -> httpx.Response:
        if r.method == "POST" and r.url.path == "/api/sessions":
            return httpx.Response(201, json={"name": "clinica-1"})
        return httpx.Response(200, json={"status": "SCAN_QR_CODE"})

    w, vistos = _waha(h)
    estado = w.iniciar("clinica-1", "https://api.invalid/api/webhooks/whatsapp", "hmac-sint")
    assert estado.estado == "escanear_qr"
    cuerpo = json.loads(vistos[0].content)
    assert cuerpo["name"] == "clinica-1" and cuerpo["start"] is True
    webhook = cuerpo["config"]["webhooks"][0]
    assert webhook["url"] == "https://api.invalid/api/webhooks/whatsapp"
    assert set(webhook["events"]) == {"message", "message.ack", "session.status"}
    assert webhook["hmac"] == {"key": "hmac-sint"}


def test_iniciar_sesion_existente_actualiza_y_reinicia() -> None:
    def h(r: httpx.Request) -> httpx.Response:
        if r.method == "POST" and r.url.path == "/api/sessions":
            return httpx.Response(422, json={"message": "already exists"})
        return httpx.Response(200, json={"status": "STARTING"})

    w, vistos = _waha(h)
    assert w.iniciar("clinica-1", "https://api.invalid/w", "hmac-sint").estado == "iniciando"
    pasos = [(r.method, r.url.path) for r in vistos]
    assert ("PUT", "/api/sessions/clinica-1") in pasos
    assert ("POST", "/api/sessions/clinica-1/restart") in pasos


def test_5xx_y_timeout_son_gateway_no_disponible() -> None:
    w, _ = _waha(lambda r: httpx.Response(502))
    with pytest.raises(GatewayNoDisponible):
        w.enviar_texto("clinica-1", "+5491100000001", "hola")

    def timeout(r: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("sin red", request=r)

    w, _ = _waha(timeout)
    with pytest.raises(GatewayNoDisponible):
        w.estado("clinica-1")


def test_4xx_al_enviar_es_sesion_no_activa() -> None:
    w, _ = _waha(lambda r: httpx.Response(422, json={"message": "session not working"}))
    with pytest.raises(SesionNoActiva):
        w.enviar_texto("clinica-1", "+5491100000001", "hola")
