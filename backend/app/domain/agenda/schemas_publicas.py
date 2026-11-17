"""Schemas de la reserva pública (C-06 D5). ``extra='forbid'`` (regla dura 4) vía la base.

Entrada: reutiliza los validadores de paciente (DNI, nombre, email, teléfono normalizados).
Salidas: nunca exponen datos del paciente, ids de sillón ni matrículas.
"""

from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, StrictInt, field_validator, model_validator

from app.domain.pacientes.schemas import _CamposPaciente


class ReservaIn(_CamposPaciente):
    """Reserva sin cuenta: hueco elegido + identificación mínima + aceptación de privacidad."""

    profesional_id: StrictInt
    prestacion_id: StrictInt
    inicio: AwareDatetime
    dni: str
    nombre: str
    apellido: str
    email: str | None = None
    telefono: str | None = None
    acepta_privacidad: Literal[True]

    @field_validator("inicio")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _contacto(self) -> Self:
        if self.email is None and self.telefono is None:
            raise ValueError("Se requiere email o teléfono")
        return self


class PrestacionPublicaOut(BaseModel):
    id: int
    nombre: str
    duracion_min: int


class ProfesionalPublicoOut(BaseModel):
    id: int
    nombre: str
    especialidad: str | None = None


class CatalogoPublicoOut(BaseModel):
    clinica: str
    zona_horaria: str
    prestaciones: list[PrestacionPublicaOut]
    profesionales: list[ProfesionalPublicoOut]


class HuecoPublicoOut(BaseModel):
    inicio: datetime
    fin: datetime


class ReservaPublicaOut(BaseModel):
    """Comprobante sin datos del paciente (lo que ve quien tiene el token)."""

    clinica: str
    zona_horaria: str
    profesional: str
    prestacion: str
    inicio: datetime
    fin: datetime
    estado: str
    cancelable: bool


class ReservaCreadaOut(ReservaPublicaOut):
    """Respuesta del alta: el token en claro se muestra solo esta vez (D2)."""

    token: str
