"""Schemas Pydantic de pacientes, ficha, adjuntos y auditoría (C-08, extra=forbid)."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.core.schemas import _ForbidBase
from app.domain.pacientes.normalizacion import (
    normalizar_dni,
    normalizar_email,
    normalizar_telefono,
)

Nombre = Annotated[str, Field(min_length=1, max_length=100)]


def _recortar(valor: str | None) -> str | None:
    """Recorta espacios; vacío -> ``None``."""
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


class _CamposPaciente(_ForbidBase):
    """Validadores compartidos de alta y edición."""

    @field_validator("nombre", "apellido", check_fields=False)
    @classmethod
    def _nombre_recortado(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip()
        if not 1 <= len(limpio) <= 100:
            raise ValueError("Debe tener entre 1 y 100 caracteres")
        return limpio

    @field_validator("dni", check_fields=False)
    @classmethod
    def _dni(cls, value: str | None) -> str | None:
        return None if value is None else normalizar_dni(value)

    @field_validator("email", check_fields=False)
    @classmethod
    def _email(cls, value: str | None) -> str | None:
        return None if value is None else normalizar_email(value)

    @field_validator("telefono", check_fields=False)
    @classmethod
    def _telefono(cls, value: str | None) -> str | None:
        return None if value is None else normalizar_telefono(value)

    @field_validator("obra_social_nombre", "obra_social_plan", check_fields=False)
    @classmethod
    def _os(cls, value: str | None) -> str | None:
        limpio = _recortar(value)
        if limpio is not None and len(limpio) > 120:
            raise ValueError("Máximo 120 caracteres")
        return limpio

    @field_validator("nro_afiliado", check_fields=False)
    @classmethod
    def _afiliado(cls, value: str | None) -> str | None:
        limpio = _recortar(value)
        if limpio is not None and len(limpio) > 50:
            raise ValueError("Máximo 50 caracteres")
        return limpio


class PacienteCreate(_CamposPaciente):
    """Alta de paciente: nombre, apellido, DNI y al menos un contacto."""

    nombre: str
    apellido: str
    dni: str
    email: str | None = None
    telefono: str | None = None
    obra_social_nombre: str | None = None
    obra_social_plan: str | None = None
    nro_afiliado: str | None = None

    @model_validator(mode="after")
    def _contacto(self) -> "PacienteCreate":
        if self.email is None and self.telefono is None:
            raise ValueError("Se requiere email o teléfono")
        return self


class PacienteUpdate(_CamposPaciente):
    """Edición parcial: todo opcional; sin ``riesgo_ausencia`` ni ``clinica_id``."""

    nombre: str | None = None
    apellido: str | None = None
    dni: str | None = None
    email: str | None = None
    telefono: str | None = None
    obra_social_nombre: str | None = None
    obra_social_plan: str | None = None
    nro_afiliado: str | None = None
    consentimiento_datos: bool | None = None

    @model_validator(mode="after")
    def _sin_nulos_obligatorios(self) -> "PacienteUpdate":
        for campo in ("nombre", "apellido", "dni", "consentimiento_datos"):
            if campo in self.model_fields_set and getattr(self, campo) is None:
                raise ValueError(f"{campo} no puede ser nulo")
        return self


class PacienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    apellido: str
    dni: str
    email: str | None
    telefono: str | None
    obra_social_nombre: str | None
    obra_social_plan: str | None
    nro_afiliado: str | None
    riesgo_ausencia: int
    consentimiento_datos: bool
    consentimiento_datos_at: datetime | None
    consentimiento_datos_por: int | None
    created_at: datetime


class FichaPut(_ForbidBase):
    """Reemplazo completo de la ficha + control optimista de versión."""

    version_esperada: int = Field(ge=0)
    anamnesis: str | None = Field(default=None, max_length=10000)
    alergias: str | None = Field(default=None, max_length=10000)
    antecedentes: str | None = Field(default=None, max_length=10000)


class FichaOut(BaseModel):
    version: int
    anamnesis: str | None = None
    alergias: str | None = None
    antecedentes: str | None = None
    autor_usuario_id: int | None = None
    created_at: datetime | None = None


class AdjuntoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paciente_id: int
    tipo: str
    mime: str
    tamano_bytes: int
    sha256: str
    subido_por: int
    created_at: datetime


class AuditoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paciente_id: int
    actor_usuario_id: int | None
    actor_tipo: str
    accion: str
    entidad: str
    entidad_id: int
    diff: dict[str, Any]
    created_at: datetime
