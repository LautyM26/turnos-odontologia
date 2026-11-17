"""Schemas de la lista de espera (C-16, D8). Todos con ``extra='forbid'`` (regla dura 4)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntradaIn(_Estricto):
    paciente_id: int = Field(gt=0)
    prestacion_id: int = Field(gt=0)
    profesional_id: int | None = Field(default=None, gt=0)
    sillon_id: int | None = Field(default=None, gt=0)
    turno_a_adelantar_id: int | None = Field(default=None, gt=0)
    prioridad: int = Field(default=0, ge=0, le=10)


class EntradaPatch(_Estricto):
    prioridad: int | None = Field(default=None, ge=0, le=10)
    profesional_id: int | None = Field(default=None, gt=0)
    sillon_id: int | None = Field(default=None, gt=0)


class OfertaManualIn(_Estricto):
    turno_liberado_id: int = Field(gt=0)


class EntradaOut(_Estricto):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    paciente_id: int
    prestacion_id: int
    profesional_id: int | None
    sillon_id: int | None
    turno_a_adelantar_id: int | None
    prioridad: int
    estado: str
    created_at: datetime


class OfertaOut(_Estricto):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    lista_espera_id: int
    turno_liberado_id: int
    inicio: datetime
    fin: datetime
    profesional_id: int
    sillon_id: int
    prestacion_id: int
    estado: str
    expira_at: datetime
    respondida_at: datetime | None
    turno_creado_id: int | None
    created_at: datetime


class OfertaBandejaOut(OfertaOut):
    paciente_id: int | None = None
    paciente_nombre: str | None = None


class MetricasOut(_Estricto):
    desde: date
    hasta: date
    liberados: int
    recuperados: int
    perdidos: int
