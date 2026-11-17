"""Schemas de administración de usuarios (C-18, D6; extra=forbid, regla dura 4)."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.core.schemas import _ForbidBase

RolPersonal = Literal["admin", "odontologo", "recepcionista"]
Roles = Annotated[list[RolPersonal], Field(min_length=1)]


def _sin_duplicados(roles: list[str]) -> list[str]:
    if len(set(roles)) != len(roles):
        raise ValueError("Roles duplicados")
    return roles


class RolesIn(_ForbidBase):
    roles: Roles

    _unicos = field_validator("roles")(_sin_duplicados)


class UsuarioAdminIn(_ForbidBase):
    email: EmailStr
    nombre: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    roles: Roles

    _unicos = field_validator("roles")(_sin_duplicados)

    @field_validator("email")
    @classmethod
    def _minusculas(cls, value: str) -> str:
        return value.strip().lower()


class UsuarioAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str | None
    is_active: bool
    roles: list[str]
