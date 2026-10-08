"""Schemas Pydantic del catalogo y bloqueos (C-04). Todos con extra='forbid' (regla dura 4).

Ningun payload acepta ``clinica_id``, ``id``, ``es_seed``, ``is_active`` ni ``rango``.
Fechas ``AwareDatetime`` normalizadas a UTC; montos ``Decimal`` exacto (regla dura 7).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

MAX_BLOQUEO = timedelta(days=31)

Nombre = Annotated[str, Field(min_length=1, max_length=200)]
Matricula = Annotated[str, Field(min_length=1, max_length=50)]
Motivo = Annotated[str, Field(min_length=1, max_length=200)]
Duracion = Annotated[StrictInt, Field(ge=5, le=480)]
Precio = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
TipoSillon = Literal["sillon", "box", "equipo"]


class EntradaBase(BaseModel):
    """Base de entrada: rechaza campos no declarados con 422."""

    model_config = ConfigDict(extra="forbid")


class SalidaBase(BaseModel):
    """Base de salida desde ORM."""

    model_config = ConfigDict(from_attributes=True)


class Pagina[T](BaseModel):
    """Pagina por cursor keyset: ``next_cursor`` nulo al final."""

    items: list[T]
    next_cursor: int | None = None


# --- Sillon / recurso ---------------------------------------------------------------------


class SillonCreate(EntradaBase):
    nombre: Nombre
    tipo: TipoSillon


class SillonUpdate(EntradaBase):
    nombre: Nombre | None = None
    tipo: TipoSillon | None = None


class SillonOut(SalidaBase):
    id: int
    nombre: str
    tipo: str
    is_active: bool
    es_seed: bool
    deleted_at: datetime | None = None


# --- Prestacion ---------------------------------------------------------------------------


class PrestacionCreate(EntradaBase):
    nombre: Nombre
    duracion_min: Duracion
    precio_referencia: Precio


class PrestacionUpdate(EntradaBase):
    nombre: Nombre | None = None
    duracion_min: Duracion | None = None
    precio_referencia: Precio | None = None


class PrestacionOut(SalidaBase):
    id: int
    nombre: str
    duracion_min: int
    precio_referencia: Decimal
    is_active: bool
    es_seed: bool
    deleted_at: datetime | None = None


# --- Profesional --------------------------------------------------------------------------


class ProfesionalCreate(EntradaBase):
    nombre: Nombre
    matricula: Matricula
    especialidad: Annotated[str, Field(max_length=200)] | None = None
    agenda_activa: bool = True
    tercerizado: bool = False
    usuario_id: int | None = None


class ProfesionalUpdate(EntradaBase):
    nombre: Nombre | None = None
    matricula: Matricula | None = None
    especialidad: Annotated[str, Field(max_length=200)] | None = None
    agenda_activa: bool | None = None
    tercerizado: bool | None = None
    usuario_id: int | None = None


class ProfesionalOut(SalidaBase):
    id: int
    nombre: str
    matricula: str
    especialidad: str | None = None
    agenda_activa: bool
    tercerizado: bool
    usuario_id: int | None = None
    is_active: bool
    es_seed: bool
    deleted_at: datetime | None = None
    sillon_ids: list[int] = Field(default_factory=list)


class HabilitacionIn(EntradaBase):
    sillon_ids: list[int]

    @field_validator("sillon_ids")
    @classmethod
    def _sin_duplicados(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("sillon_ids no admite duplicados")
        return value


# --- Bloqueo ------------------------------------------------------------------------------


def validar_rango(inicio: datetime, fin: datetime) -> None:
    """Rango semiabierto valido: fin > inicio y duracion <= 31 dias."""
    if fin <= inicio:
        raise ValueError("fin debe ser posterior a inicio")
    if fin - inicio > MAX_BLOQUEO:
        raise ValueError("un bloqueo no puede superar 31 dias")


def _a_utc(value: datetime | None) -> datetime | None:
    return value.astimezone(UTC) if value is not None else None


class BloqueoCreate(EntradaBase):
    profesional_id: int | None = None
    sillon_id: int | None = None
    inicio: AwareDatetime
    fin: AwareDatetime
    motivo: Motivo

    @field_validator("inicio", "fin")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        if self.profesional_id is not None and self.sillon_id is not None:
            raise ValueError("un bloqueo es de profesional o de sillon, no de ambos")
        validar_rango(self.inicio, self.fin)
        return self


class BloqueoPropioCreate(EntradaBase):
    """Bloqueo propio del odontologo: el profesional sale del path (puede repetirse)."""

    profesional_id: int | None = None
    inicio: AwareDatetime
    fin: AwareDatetime
    motivo: Motivo

    @field_validator("inicio", "fin")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        validar_rango(self.inicio, self.fin)
        return self


class BloqueoUpdate(EntradaBase):
    """Cambio parcial; el rango resultante se revalida en el servicio."""

    inicio: AwareDatetime | None = None
    fin: AwareDatetime | None = None
    motivo: Motivo | None = None

    @field_validator("inicio", "fin")
    @classmethod
    def _utc(cls, value: datetime | None) -> datetime | None:
        return _a_utc(value)


class BloqueoOut(SalidaBase):
    id: int
    profesional_id: int | None = None
    sillon_id: int | None = None
    inicio: datetime
    fin: datetime
    motivo: str
    is_active: bool
    deleted_at: datetime | None = None
