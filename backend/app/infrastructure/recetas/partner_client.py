"""Puerto del partner de recetas ReNaPDiS (C-19, D1, RN-CU-03).

El dominio solo conoce este puerto: cambiar de partner = un adapter nuevo + un valor de
``RECETAS_PARTNER``. Sin partner configurado nada se emite (``NoConfigurado`` -> 501).
"""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


class PartnerNoDisponible(Exception):
    """Timeout, 5xx o conexión caída: el usuario puede reintentar con la misma clave."""


class PartnerRechazo(Exception):
    """El partner rechazó la solicitud; ``motivo`` se sanea antes de mostrarse."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


@dataclass(frozen=True)
class NoConfigurado:
    """Resultado de la factory cuando no hay partner utilizable (nunca una excepción)."""

    mensaje: str


@dataclass(frozen=True)
class SolicitudPartner:
    tipo: str
    clave_idempotencia: UUID
    paciente_nombre: str
    paciente_apellido: str
    paciente_dni: str
    obra_social_nombre: str | None
    obra_social_plan: str | None
    nro_afiliado: str | None
    profesional_nombre: str
    profesional_matricula: str
    diagnostico: str
    items: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class EmisionPartner:
    id_externo: str
    pdf_url: str


class PartnerRecetas(Protocol):
    nombre: str
    simulado: bool

    def emitir(self, solicitud: SolicitudPartner) -> EmisionPartner: ...
