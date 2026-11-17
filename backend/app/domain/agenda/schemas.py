"""Schemas Pydantic del catalogo y bloqueos (C-04). Todos con extra='forbid' (regla dura 4).

Ningun payload acepta ``clinica_id``, ``id``, ``es_seed``, ``is_active`` ni ``rango``.
Fechas ``AwareDatetime`` normalizadas a UTC; montos ``Decimal`` exacto (regla dura 7).
"""

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
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


# --- Turno (C-05 recorte: alta sin solapamientos) ------------------------------------------


class TurnoCreate(EntradaBase):
    """Alta de turno: fin, duracion, estado, origen y tenant los fija el servidor."""

    profesional_id: StrictInt
    sillon_id: StrictInt
    paciente_id: StrictInt
    prestacion_id: StrictInt
    inicio: AwareDatetime
    sobreturno: StrictBool = False
    motivo_sobreturno: str | None = Field(default=None, max_length=500)

    @field_validator("inicio")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @field_validator("motivo_sobreturno")
    @classmethod
    def _motivo(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @model_validator(mode="after")
    def _motivo_sii_sobreturno(self) -> Self:
        """RN-AG-04 (C-05c D4): el motivo es obligatorio con sobreturno y prohibido sin él."""
        if self.sobreturno != (self.motivo_sobreturno is not None):
            raise ValueError("motivo_sobreturno es obligatorio si y solo si sobreturno=true")
        return self


class TurnoTransicionIn(EntradaBase):
    """Cambio de estado (C-05b D6): solo destinos alcanzables; ``motivo`` operativo, no clínico."""

    estado: Literal["confirmado", "cancelado", "asistido", "ausente"]
    motivo: str | None = Field(default=None, max_length=500)

    @field_validator("motivo")
    @classmethod
    def _motivo(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip()
        return limpio or None


class TurnoOut(SalidaBase):
    id: int
    profesional_id: int
    sillon_id: int
    paciente_id: int
    prestacion_id: int
    inicio: datetime
    fin: datetime
    duracion_min: int
    estado: str
    origen: str
    es_sobreturno: bool
    motivo_sobreturno: str | None
    created_at: datetime


# --- Huecos (C-05c D6) ---------------------------------------------------------------------


class HuecoOut(SalidaBase):
    """Inicio libre para un turno normal; ``fin`` = inicio + duración (servidor, regla 6)."""

    inicio: datetime
    fin: datetime
    sillon_ids: list[int]


# --- Horario de atención (C-05d D1/D5) -----------------------------------------------------

MAX_FRANJAS = 70  # 10 por día: acota el payload del PUT
_HHMM = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$|^24:00$")


def _a_minutos(value: object) -> int:
    """``"HH:MM"`` (``"24:00"`` = fin del día) -> minutos desde la medianoche local."""
    if not isinstance(value, str) or not _HHMM.match(value):
        raise ValueError("hora en formato HH:MM entre 00:00 y 24:00")
    horas, minutos = value.split(":")
    return int(horas) * 60 + int(minutos)


def _a_hhmm(value: object) -> object:
    return f"{value // 60:02d}:{value % 60:02d}" if isinstance(value, int) else value


Minutos = Annotated[int, BeforeValidator(_a_minutos)]
Hhmm = Annotated[str, BeforeValidator(_a_hhmm)]


class FranjaIn(EntradaBase):
    """Franja semanal: día ISO (1 = lunes) y horas locales; internamente en minutos."""

    dia_semana: Annotated[StrictInt, Field(ge=1, le=7)]
    inicio: Minutos
    fin: Minutos

    @model_validator(mode="after")
    def _inicio_antes_de_fin(self) -> Self:
        if self.inicio >= self.fin:
            raise ValueError("inicio debe ser anterior a fin (sin cruzar la medianoche)")
        return self


class HorarioIn(EntradaBase):
    """Horario completo de un profesional; reemplaza al anterior (todo o nada)."""

    franjas: Annotated[list[FranjaIn], Field(max_length=MAX_FRANJAS)]

    @field_validator("franjas")
    @classmethod
    def _ordenadas_sin_superposicion(cls, value: list[FranjaIn]) -> list[FranjaIn]:
        ordenadas = sorted(value, key=lambda f: (f.dia_semana, f.inicio))
        for previa, actual in zip(ordenadas, ordenadas[1:], strict=False):
            if previa.dia_semana == actual.dia_semana and actual.inicio < previa.fin:
                raise ValueError(f"franjas superpuestas el día {actual.dia_semana}")
        return ordenadas


class FranjaOut(SalidaBase):
    dia_semana: int
    inicio: Hhmm = Field(validation_alias="inicio_min")
    fin: Hhmm = Field(validation_alias="fin_min")


class HorarioOut(BaseModel):
    profesional_id: int
    zona_horaria: str
    franjas: list[FranjaOut]
