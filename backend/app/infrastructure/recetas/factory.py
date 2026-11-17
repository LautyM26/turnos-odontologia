"""Selección del partner según la configuración (C-19, D1). Nunca levanta excepciones."""

import logging

from app.infrastructure.recetas.fake import FakePartner
from app.infrastructure.recetas.partner_client import NoConfigurado, PartnerRecetas
from app.infrastructure.settings import Settings

_log = logging.getLogger("turnos.recetas")
_fake = FakePartner()  # singleton por proceso (los tests lo inspeccionan por override)


def obtener_partner(settings: Settings) -> PartnerRecetas | NoConfigurado:
    nombre = settings.recetas_partner
    if not nombre:
        return NoConfigurado("Configurá RECETAS_PARTNER para emitir recetas electrónicas")
    if nombre == "fake":
        if settings.entorno == "produccion":
            _log.warning("RECETAS_PARTNER=fake bloqueado: ENTORNO=produccion")
            return NoConfigurado("El partner simulado está deshabilitado en producción")
        return _fake
    _log.warning("RECETAS_PARTNER desconocido: %r", nombre)
    return NoConfigurado(f"RECETAS_PARTNER={nombre!r} no es un partner soportado")
