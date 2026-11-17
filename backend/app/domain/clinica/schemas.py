"""Schemas Pydantic del odontograma y las evoluciones (C-09, extra=forbid, regla dura 4)."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.clinica import fdi
from app.domain.core.schemas import _ForbidBase
from app.domain.pacientes.schemas import FichaOut

Registro = Literal["existente", "a_realizar"]
Cara = Literal["V", "L", "M", "D", "O"]
Denticion = Literal["permanente", "temporal", "mixta"]
EstadoPieza = Literal[
    "ausente", "extraida", "extraccion_indicada", "corona", "endodoncia", "implante"
]
EstadoCara = Literal["caries", "obturacion", "sellador", "fractura"]


class MarcaPiezaIn(_ForbidBase):
    codigo: EstadoPieza
    registro: Registro = "existente"


class MarcaCaraIn(_ForbidBase):
    codigo: EstadoCara
    registro: Registro = "existente"


class PiezaIn(_ForbidBase):
    estado: MarcaPiezaIn | None = None
    caras: dict[Cara, MarcaCaraIn] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _sin_caras_si_ausente(self) -> "PiezaIn":
        if self.estado is not None and self.estado.codigo in fdi.PIEZA_SIN_CARAS and self.caras:
            raise ValueError("Una pieza ausente o extraída no admite caras marcadas")
        return self


class OdontogramaIn(_ForbidBase):
    version_esperada: int = Field(ge=0)
    denticion: Denticion
    piezas: dict[str, PiezaIn] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _piezas_de_la_denticion(self) -> "OdontogramaIn":
        if len(self.piezas) > fdi.MAX_PIEZAS:
            raise ValueError(f"Máximo {fdi.MAX_PIEZAS} piezas")
        validas = fdi.piezas_validas(self.denticion)
        for clave in self.piezas:
            if not (clave.isascii() and clave.isdigit() and str(int(clave)) == clave):
                raise ValueError(f"Código de pieza inválido: {clave!r}")
            if int(clave) not in validas:
                raise ValueError(f"Pieza {clave} no válida para la dentición {self.denticion}")
        return self


class EvolucionIn(_ForbidBase):
    texto: str
    pieza_fdi: int | None = None
    corrige_a_id: int | None = Field(default=None, ge=1)
    motivo_correccion: str | None = None

    @field_validator("texto")
    @classmethod
    def _texto(cls, value: str) -> str:
        limpio = value.strip()
        if not 1 <= len(limpio) <= 10_000:
            raise ValueError("El texto debe tener entre 1 y 10000 caracteres")
        return limpio

    @field_validator("pieza_fdi")
    @classmethod
    def _pieza(cls, value: int | None) -> int | None:
        if value is not None and not fdi.es_pieza_fdi(value):
            raise ValueError("Pieza FDI inexistente")
        return value

    @field_validator("motivo_correccion")
    @classmethod
    def _motivo(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip()
        if not 1 <= len(limpio) <= 500:
            raise ValueError("El motivo debe tener entre 1 y 500 caracteres")
        return limpio

    @model_validator(mode="after")
    def _correccion_completa(self) -> "EvolucionIn":
        if (self.corrige_a_id is None) != (self.motivo_correccion is None):
            raise ValueError("corrige_a_id y motivo_correccion van juntos")
        return self


# --- Salida --------------------------------------------------------------------------------


class OdontogramaOut(BaseModel):
    """Versión del odontograma; ``version = 0`` = paciente sin odontograma."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    version: int
    denticion: str | None = None
    piezas: dict[str, Any] = Field(default_factory=dict)
    autor_usuario_id: int | None = None
    created_at: datetime | None = None


def odontograma_out(fila: Any | None) -> OdontogramaOut:
    """Fila ``Odontograma`` (o ``None`` = versión 0) -> schema de salida."""
    if fila is None:
        return OdontogramaOut(version=0)
    return OdontogramaOut.model_validate(fila)


class EvolucionOut(BaseModel):
    id: int
    paciente_id: int
    autor_usuario_id: int
    profesional_id: int
    fecha_hora: datetime
    texto: str
    pieza_fdi: int | None = None
    corrige_a_id: int | None = None
    motivo_correccion: str | None = None
    corregida_por_id: int | None = None


class HistoriaOut(BaseModel):
    ficha: FichaOut
    odontograma: OdontogramaOut
    evoluciones: list[EvolucionOut]
    next_cursor: Annotated[int | None, Field(description="Cursor para /evoluciones")] = None
