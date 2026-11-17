"""Schemas de consentimientos (C-18, extra=forbid, regla dura 4).

La completitud de la firma (aceptación, nombre, DNI) la valida el servicio para responder
``FirmaIncompleta`` (reintentable) en lugar del 422 genérico de Pydantic (D3).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.core.schemas import _ForbidBase

TipoConsentimiento = Literal[
    "tratamiento_general", "extraccion", "endodoncia", "implante", "anestesia"
]


class ConsentimientoIn(_ForbidBase):
    tipo: TipoConsentimiento


class FirmaIn(_ForbidBase):
    acepta: bool | None = None
    firmante_nombre: str | None = Field(default=None, max_length=200)
    firmante_dni: str | None = Field(default=None, max_length=20)
    texto_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ConstanciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    firmado_en: datetime
    ip: str
    dispositivo: str
    texto_hash: str
    firmante_nombre: str
    firmante_dni: str
    asistido_por_usuario_id: int


class ConsentimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paciente_id: int
    tipo: str
    texto: str
    texto_version: str
    texto_hash: str
    autor_usuario_id: int
    created_at: datetime
    estado: Literal["pendiente", "firmado"]
    documento_bloqueado: bool
    constancia: ConstanciaOut | None = None
