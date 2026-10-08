"""Schemas Pydantic core con extra=forbid (regla dura 4, C-02)."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.core.cuit import normalizar_cuit, validar_cuit


class _ForbidBase(BaseModel):
    """Base que rechaza campos no declarados con 422."""

    model_config = ConfigDict(extra="forbid")


class ClinicaCreate(_ForbidBase):
    """Payload de alta de clínica (tenant raíz)."""

    nombre: str = Field(min_length=1, max_length=200)
    cuit: str = Field(min_length=11, max_length=13)
    email_contacto: EmailStr | None = None

    @field_validator("cuit")
    @classmethod
    def _cuit_valido(cls, value: str) -> str:
        if not validar_cuit(value):
            raise ValueError("CUIT inválido (módulo 11)")
        return normalizar_cuit(value)


class UsuarioCreate(_ForbidBase):
    """Payload de alta de usuario scoped a una clínica."""

    clinica_id: int = Field(gt=0)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _email_minusculas(cls, value: str) -> str:
        return value.strip().lower()
