"""Schemas de WhatsApp (C-15). Todos con ``extra='forbid'`` (regla dura 4).

Los ``Evento*`` son NUESTRO contrato interno: el adapter del gateway extrae del sobre externo
solo los campos que usamos (D6), así un campo nuevo del gateway no rompe el webhook.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EstadoSesionLit = Literal["desconocido", "iniciando", "escanear_qr", "activa", "caida", "detenida"]


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventoMensaje(_Estricto):
    sesion: str
    id_externo: str = Field(min_length=1, max_length=300)
    chat: str = Field(min_length=1, max_length=300)
    texto: str = Field(default="", max_length=10000)


class EventoAck(_Estricto):
    sesion: str
    id_externo: str = Field(min_length=1, max_length=300)
    ack: int


class EventoSesion(_Estricto):
    sesion: str
    estado: EstadoSesionLit
    numero: str | None = None


Evento = EventoMensaje | EventoAck | EventoSesion


# --- API autenticada (D9) -----------------------------------------------------------------


class _Salida(_Estricto):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class SesionOut(_Salida):
    estado: EstadoSesionLit
    numero: str | None
    estado_at: datetime | None
    en_vivo: bool
    qr: str | None = None


class MensajeOut(_Salida):
    id: int
    turno_id: int | None
    paciente_id: int | None
    plantilla: str | None
    direccion: str
    telefono: str | None
    texto: str | None
    estado: str
    intencion: str | None
    intentos: int
    motivo_error: str | None
    costo_ars: Decimal
    requiere_atencion: bool
    resuelto_at: datetime | None
    created_at: datetime


class FalloOut(MensajeOut):
    paciente_nombre: str | None = None
    turno_inicio: datetime | None = None


class CostoLinea(_Estricto):
    plantilla: str | None
    direccion: str
    cantidad: int
    total_ars: Decimal


class CostosOut(_Estricto):
    desde: date
    hasta: date
    total_ars: Decimal
    detalle: list[CostoLinea]
