"""Router de turnos (C-05 recorte): alta sin solapamientos y lectura por id.

Orden de chequeo: auth (401) -> rol (403) -> cuerpo (422) -> referencias (422) ->
bloqueo/solapamiento (409). ``clinica_id`` sale siempre del JWT, nunca del cuerpo.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_tenant_checked
from app.api.permissions import require_role
from app.domain.agenda import turnos
from app.domain.agenda.schemas import TurnoCreate, TurnoOut
from app.infrastructure.db import get_session

router = APIRouter(prefix="/api/turnos", tags=["turnos"])

Sesion = Annotated[Session, Depends(get_session)]
Tenant = Annotated[int, Depends(require_tenant_checked)]
Escritura = Annotated[AuthContext, Depends(require_role("admin", "recepcionista"))]
Staff = Annotated[AuthContext, Depends(require_role("admin", "recepcionista", "odontologo"))]


def get_ahora() -> datetime:
    """Reloj del servidor (UTC); los tests lo sobreescriben via ``dependency_overrides``."""
    return datetime.now(UTC)


Ahora = Annotated[datetime, Depends(get_ahora)]


@router.post("", response_model=TurnoOut, status_code=201)
def crear(body: TurnoCreate, auth: Escritura, session: Sesion, tenant: Tenant, ahora: Ahora):  # type: ignore[no-untyped-def]
    return turnos.crear_turno(session, tenant, body.model_dump(), ahora)


@router.get("/{turno_id}", response_model=TurnoOut)
def obtener(turno_id: int, auth: Staff, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return turnos.obtener_turno(session, tenant, turno_id)
