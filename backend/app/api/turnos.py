"""Router de turnos (C-05 recorte + C-05b): alta, lectura por id y transiciones de estado.

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
from app.domain.agenda.schemas import TurnoCreate, TurnoOut, TurnoTransicionIn
from app.domain.agenda.servicio import PermisoDenegado, profesional_de_usuario
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


#: Destinos que puede marcar un odontólogo sin rol de staff (C-05b D2).
_DESTINOS_ODONTOLOGO = frozenset({"asistido", "ausente"})


@router.post("/{turno_id}/transicion", response_model=TurnoOut)
def transicionar(  # type: ignore[no-untyped-def]
    turno_id: int,
    body: TurnoTransicionIn,
    auth: Staff,
    session: Sesion,
    tenant: Tenant,
    ahora: Ahora,
):
    """Cambia el estado del turno (RN-TU-01). ``motivo`` es operativo, no clínico.

    Admin/recepcionista: cualquier transición de la tabla. Odontólogo: solo ``asistido`` o
    ``ausente`` en turnos de su propia agenda (403 en otro caso, falla cerrado sin vínculo).
    """
    solo_agenda_de: int | None = None
    destinos: frozenset[str] | None = None
    if not {"admin", "recepcionista"} & set(auth.roles):
        solo_agenda_de = profesional_de_usuario(session, auth.sub)
        if solo_agenda_de is None:
            raise PermisoDenegado("Agenda no autorizada")
        destinos = _DESTINOS_ODONTOLOGO
    return turnos.transicionar_turno(
        session, tenant, turno_id, body.estado, auth.sub, body.motivo, ahora,
        solo_agenda_de=solo_agenda_de, destinos_permitidos=destinos,
    )  # fmt: skip
