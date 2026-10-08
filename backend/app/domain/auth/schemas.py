"""Schemas Pydantic del ciclo auth (C-03, D10). Todos extra='forbid' → 422."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Forbid(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginIn(_Forbid):
    """Credenciales de login. El email se normaliza a minúsculas (3.2)."""

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RefreshIn(_Forbid):
    """Cuerpo vacío: el refresh viaja solo en cookie HttpOnly, nunca en JSON."""


class TokenOut(_Forbid):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Segundos de vida del access token.")


class MeOut(_Forbid):
    sub: int
    email: str
    tenant_id: int
    roles: list[str]
