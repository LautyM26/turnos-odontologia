"""Selección del gateway de WhatsApp según la configuración (C-15 D1). Nunca lanza."""

import logging

from app.infrastructure.settings import Settings
from app.infrastructure.whatsapp.fake import FakeMensajeria
from app.infrastructure.whatsapp.puerto import Mensajeria, NoConfigurado
from app.infrastructure.whatsapp.waha import WahaMensajeria

_log = logging.getLogger("turnos.whatsapp")
_fake = FakeMensajeria()  # singleton por proceso (demo: los envíos quedan en memoria)


def obtener_mensajeria(settings: Settings) -> Mensajeria | NoConfigurado:
    nombre = settings.whatsapp_gateway
    if not nombre:
        return NoConfigurado("Configurá WHATSAPP_GATEWAY para usar WhatsApp")
    if nombre == "fake":
        if settings.entorno == "produccion":
            _log.warning("WHATSAPP_GATEWAY=fake bloqueado: ENTORNO=produccion")
            return NoConfigurado("El gateway simulado está deshabilitado en producción")
        return _fake
    if nombre == "waha":
        if not settings.whatsapp_gateway_url:
            return NoConfigurado("Configurá WHATSAPP_GATEWAY_URL para el gateway waha")
        clave = settings.whatsapp_gateway_api_key
        return WahaMensajeria(
            settings.whatsapp_gateway_url, clave.get_secret_value() if clave else None
        )
    _log.warning("WHATSAPP_GATEWAY desconocido: %r", nombre)
    return NoConfigurado(f"WHATSAPP_GATEWAY={nombre!r} no es un gateway soportado")
