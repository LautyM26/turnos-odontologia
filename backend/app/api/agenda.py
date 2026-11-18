"""Router de agenda: huecos libres (C-05c D6) y lectura de turnos y bloqueos (C-07 D1).

Orden: auth (401) -> agenda propia para el odontólogo (403) -> query (422) -> referencias y
ventana (422). ``clinica_id`` sale siempre del JWT.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, require_tenant_checked
from app.api.permissions import require_own_agenda
from app.api.turnos import get_ahora
from app.domain.agenda.agenda_lectura import bloqueos_de_ventana, turnos_de_ventana
from app.domain.agenda.huecos import buscar_huecos
from app.domain.agenda.schemas import AgendaBloqueoOut, AgendaTurnoOut, HuecoOut
from app.infrastructure.db import get_session
from app.infrastructure.settings import get_settings

router = APIRouter(prefix="/api/agenda", tags=["agenda"])


@router.get("/huecos", response_model=list[HuecoOut])
def huecos(  # type: ignore[no-untyped-def]
    profesional_id: int,
    prestacion_id: int,
    desde: Annotated[AwareDatetime, Query()],
    hasta: Annotated[AwareDatetime, Query()],
    auth: Annotated[AuthContext, Depends(require_own_agenda)],
    session: Annotated[Session, Depends(get_session)],
    tenant: Annotated[int, Depends(require_tenant_checked)],
    ahora: Annotated[datetime, Depends(get_ahora)],
):
    """Inicios libres cada ``AGENDA_PASO_MIN`` para un turno normal; ``[]`` si no hay."""
    return buscar_huecos(
        session, tenant, profesional_id, prestacion_id, desde, hasta, ahora,
        get_settings().agenda_paso_min,
    )  # fmt: skip


Ventana = Annotated[AwareDatetime, Query()]
Agenda = Annotated[AuthContext, Depends(require_own_agenda)]
Sesion = Annotated[Session, Depends(get_session)]
Tenant = Annotated[int, Depends(require_tenant_checked)]


@router.get("/turnos", response_model=list[AgendaTurnoOut])
def turnos(  # type: ignore[no-untyped-def]
    desde: Ventana,
    hasta: Ventana,
    auth: Agenda,
    session: Sesion,
    tenant: Tenant,
    profesional_id: int | None = None,
    sillon_id: int | None = None,
):
    """Turnos de la ventana (≤ 7 días) con nombres; el odontólogo solo los de su agenda."""
    return turnos_de_ventana(session, tenant, desde, hasta, profesional_id, sillon_id)


@router.get("/bloqueos", response_model=list[AgendaBloqueoOut])
def bloqueos(  # type: ignore[no-untyped-def]
    desde: Ventana,
    hasta: Ventana,
    auth: Agenda,
    session: Sesion,
    tenant: Tenant,
    profesional_id: int | None = None,
):
    """Bloqueos activos de la ventana (clínica, sillón y profesional), para pintarlos."""
    return bloqueos_de_ventana(session, tenant, desde, hasta, profesional_id)
