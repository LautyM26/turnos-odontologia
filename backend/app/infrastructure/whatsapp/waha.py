"""Adapter del gateway QR autoalojado WAHA (C-15 D1, DD-10).

Endpoints según la doc vigente de WAHA (consultada con Context7, ``/devlikeapro/waha-docs``):
``POST /api/sendText``, ``POST|PUT /api/sessions[/{s}]``, ``POST /api/sessions/{s}/restart``,
``GET /api/sessions/{s}`` y ``GET /api/{s}/auth/qr``, autenticados con ``X-Api-Key``.
"""

from typing import Any

import httpx

from app.domain.whatsapp.schemas import Evento, EventoAck, EventoMensaje, EventoSesion
from app.infrastructure.whatsapp.puerto import EstadoSesion, GatewayNoDisponible, SesionNoActiva

EVENTOS = ["message", "message.ack", "session.status"]
_ESTADOS = {
    "WORKING": "activa",
    "SCAN_QR_CODE": "escanear_qr",
    "STARTING": "iniciando",
    "FAILED": "caida",
    "STOPPED": "detenida",
}


def chat_id(telefono: str) -> str:
    """``+5491100000001`` -> ``5491100000001@c.us``."""
    return telefono.lstrip("+") + "@c.us"


def _numero(me: Any) -> str | None:
    if isinstance(me, dict) and isinstance(me.get("id"), str) and me["id"].endswith("@c.us"):
        return "+" + me["id"].removesuffix("@c.us")
    return None


class WahaMensajeria:
    nombre = "waha"
    simulado = False

    def __init__(
        self, url: str, api_key: str | None, transport: httpx.BaseTransport | None = None
    ) -> None:
        headers = {"X-Api-Key": api_key} if api_key else {}
        self._http = httpx.Client(
            base_url=url.rstrip("/"), headers=headers, timeout=10, transport=transport
        )

    def _pedir(self, metodo: str, ruta: str, **kw: Any) -> httpx.Response:
        try:
            resp = self._http.request(metodo, ruta, **kw)
        except httpx.HTTPError as exc:
            raise GatewayNoDisponible(type(exc).__name__) from exc
        if resp.status_code >= 500:
            raise GatewayNoDisponible(f"gateway {resp.status_code}")
        return resp

    def enviar_texto(self, sesion: str, telefono: str, texto: str) -> str:
        resp = self._pedir(
            "POST", "/api/sendText",
            json={"session": sesion, "chatId": chat_id(telefono), "text": texto},
        )  # fmt: skip
        # ponytail: todo 4xx al enviar se trata como sesión no activa (la causa habitual);
        # distinguir número inexistente si el piloto lo necesita.
        if resp.status_code >= 400:
            raise SesionNoActiva(f"gateway {resp.status_code}")
        ident = resp.json().get("id")
        return ident["_serialized"] if isinstance(ident, dict) else str(ident)

    def estado(self, sesion: str) -> EstadoSesion:
        resp = self._pedir("GET", f"/api/sessions/{sesion}")
        if resp.status_code >= 400:
            return EstadoSesion("desconocido")
        body = resp.json()
        estado = _ESTADOS.get(body.get("status"), "desconocido")
        return EstadoSesion(estado, _numero(body.get("me")))

    def qr(self, sesion: str) -> str | None:
        resp = self._pedir(
            "GET", f"/api/{sesion}/auth/qr", headers={"Accept": "application/json"}
        )
        if resp.status_code >= 400:
            return None
        body = resp.json()
        return body.get("data") or body.get("base64")

    def iniciar(self, sesion: str, webhook_url: str, hmac_key: str | None) -> EstadoSesion:
        webhook: dict[str, Any] = {"url": webhook_url, "events": EVENTOS}
        if hmac_key:
            webhook["hmac"] = {"key": hmac_key}
        config = {"webhooks": [webhook]}
        resp = self._pedir(
            "POST", "/api/sessions", json={"name": sesion, "start": True, "config": config}
        )
        if resp.status_code >= 400:  # ya existe: actualizar el webhook y reiniciar
            self._pedir("PUT", f"/api/sessions/{sesion}", json={"name": sesion, "config": config})
            self._pedir("POST", f"/api/sessions/{sesion}/restart")
        return self.estado(sesion)


def parsear_evento(body: Any) -> Evento | None:
    """Sobre de evento de WAHA -> evento interno; ``None`` si no nos interesa.

    Solo se extraen los campos usados (D6) y se validan con schemas ``extra='forbid'``. Datos
    mal formados levantan ``ValueError``/``ValidationError``/``KeyError``/``TypeError`` (-> 422).
    """
    tipo, sesion, payload = body.get("event"), body.get("session"), body.get("payload") or {}
    if tipo == "message":
        if payload.get("fromMe"):
            return None
        return EventoMensaje(
            sesion=sesion, id_externo=payload.get("id"), chat=payload.get("from"),
            texto=payload.get("body") or "",
        )  # fmt: skip
    if tipo == "message.ack":
        return EventoAck(sesion=sesion, id_externo=payload.get("id"), ack=payload.get("ack"))
    if tipo == "session.status":
        estado = _ESTADOS.get(payload.get("status"), "desconocido")
        return EventoSesion(sesion=sesion, estado=estado, numero=_numero(body.get("me")))
    return None
