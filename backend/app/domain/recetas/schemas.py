"""Schemas de recetas y órdenes de estudio (C-19, extra=forbid, regla dura 4).

El servidor pone partner, id externo, enlace, simulada, autor y fecha: ninguno viene del cuerpo.
"""

import hashlib
import json
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.core.schemas import _ForbidBase


class MedicamentoIn(_ForbidBase):
    nombre_generico: str = Field(min_length=1, max_length=200)  # Ley 25.649
    presentacion: str = Field(min_length=1, max_length=200)
    cantidad: int = Field(ge=1, le=99)
    posologia: str = Field(min_length=1, max_length=300)


class EstudioIn(_ForbidBase):
    estudio: str = Field(min_length=1, max_length=200)
    indicacion: str | None = Field(default=None, max_length=300)


class _RecetaBase(_ForbidBase):
    evolucion_id: int = Field(ge=1)
    diagnostico: str
    clave_idempotencia: UUID

    @field_validator("diagnostico")
    @classmethod
    def _diagnostico(cls, value: str) -> str:
        limpio = value.strip()
        if not 1 <= len(limpio) <= 500:
            raise ValueError("El diagnóstico debe tener entre 1 y 500 caracteres")
        return limpio


class RecetaMedicamentosIn(_RecetaBase):
    tipo: Literal["receta"]
    items: list[MedicamentoIn] = Field(min_length=1, max_length=10)


class OrdenEstudioIn(_RecetaBase):
    tipo: Literal["orden_estudio"]
    items: list[EstudioIn] = Field(min_length=1, max_length=10)


RecetaIn = Annotated[RecetaMedicamentosIn | OrdenEstudioIn, Field(discriminator="tipo")]


def huella_solicitud(datos: RecetaMedicamentosIn | OrdenEstudioIn) -> str:
    """SHA-256 del contenido canónico (sin la clave): distingue reintento de reuso de clave."""
    contenido = datos.model_dump(mode="json", exclude={"clave_idempotencia"})
    canonico = json.dumps(contenido, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


class RecetaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paciente_id: int
    evolucion_id: int
    tipo: str
    partner: str
    simulada: bool
    id_externo: str
    pdf_url: str
    diagnostico: str
    items: list[dict[str, Any]]
    clave_idempotencia: UUID
    autor_usuario_id: int
    profesional_id: int
    emitida_en: datetime
