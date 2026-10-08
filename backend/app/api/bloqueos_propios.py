"""Bloqueos propios por profesional (C-04): admin y odontologo dueño de la agenda.

``require_role`` antecede a ``require_own_agenda`` porque esta deja pasar a la
recepcionista (que no gestiona bloqueos, matriz del 03). El ``profesional_id`` del
path manda: el cuerpo nunca puede escribir en otra agenda.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.api.deps import require_tenant_checked
from app.api.permissions import require_own_agenda, require_role
from app.domain.agenda import servicio
from app.domain.agenda.schemas import BloqueoOut, BloqueoPropioCreate, Pagina
from app.infrastructure.db import get_session

router = APIRouter(
    prefix="/api/profesionales/{profesional_id}/bloqueos",
    tags=["bloqueos-propios"],
    dependencies=[Depends(require_role("admin", "odontologo")), Depends(require_own_agenda)],
)

Sesion = Annotated[Session, Depends(get_session)]
Tenant = Annotated[int, Depends(require_tenant_checked)]


@router.get("", response_model=Pagina[BloqueoOut])
def listar(  # type: ignore[no-untyped-def]
    profesional_id: int,
    session: Sesion,
    tenant: Tenant,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    after_id: Annotated[int | None, Query(ge=0)] = None,
    desde: AwareDatetime | None = None,
    hasta: AwareDatetime | None = None,
):
    items, cursor = servicio.listar_bloqueos_de_profesional(
        session, tenant, profesional_id, after_id, limit, desde, hasta
    )
    return Pagina[BloqueoOut](
        items=[BloqueoOut.model_validate(i) for i in items], next_cursor=cursor
    )


@router.post("", response_model=BloqueoOut, status_code=201)
def crear(  # type: ignore[no-untyped-def]
    profesional_id: int, body: BloqueoPropioCreate, session: Sesion, tenant: Tenant
):
    datos = body.model_dump(exclude={"profesional_id"})
    return servicio.crear_bloqueo_de_profesional(session, tenant, profesional_id, datos)


@router.delete("/{bloqueo_id}", status_code=204)
def borrar(profesional_id: int, bloqueo_id: int, session: Sesion, tenant: Tenant) -> Response:
    servicio.dar_de_baja_bloqueo_de_profesional(session, tenant, profesional_id, bloqueo_id)
    return Response(status_code=204)
