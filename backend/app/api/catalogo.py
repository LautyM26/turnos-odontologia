"""Lectura del catalogo para el staff (C-04): solo activos, paginado, mismo tenant."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_tenant_checked
from app.api.permissions import require_role
from app.domain.agenda import servicio
from app.domain.agenda.models import Prestacion, Profesional, SillonRecurso
from app.domain.agenda.schemas import (
    Pagina,
    PrestacionOut,
    ProfesionalOut,
    SillonOut,
)
from app.infrastructure.db import get_session

router = APIRouter(
    prefix="/api/catalogo",
    tags=["catalogo"],
    dependencies=[Depends(require_role("admin", "recepcionista", "odontologo"))],
)

Sesion = Annotated[Session, Depends(get_session)]
Tenant = Annotated[int, Depends(require_tenant_checked)]
Limit = Annotated[int, Query(ge=1, le=200)]
AfterId = Annotated[int | None, Query(ge=0)]


@router.get("/profesionales", response_model=Pagina[ProfesionalOut])
def profesionales(  # type: ignore[no-untyped-def]
    session: Sesion, tenant: Tenant, limit: Limit = 50, after_id: AfterId = None
):
    items, cursor = servicio.listar(session, Profesional, tenant, after_id, limit)
    habilitados = servicio.sillon_ids_de(session, tenant, [i.id for i in items])
    salida = []
    for fila in items:
        out = ProfesionalOut.model_validate(fila)
        out.sillon_ids = habilitados.get(fila.id, [])
        salida.append(out)
    return Pagina[ProfesionalOut](items=salida, next_cursor=cursor)


@router.get("/sillones", response_model=Pagina[SillonOut])
def sillones(session: Sesion, tenant: Tenant, limit: Limit = 50, after_id: AfterId = None):  # type: ignore[no-untyped-def]
    items, cursor = servicio.listar(session, SillonRecurso, tenant, after_id, limit)
    return Pagina[SillonOut](
        items=[SillonOut.model_validate(i) for i in items], next_cursor=cursor
    )


@router.get("/prestaciones", response_model=Pagina[PrestacionOut])
def prestaciones(session: Sesion, tenant: Tenant, limit: Limit = 50, after_id: AfterId = None):  # type: ignore[no-untyped-def]
    items, cursor = servicio.listar(session, Prestacion, tenant, after_id, limit)
    return Pagina[PrestacionOut](
        items=[PrestacionOut.model_validate(i) for i in items], next_cursor=cursor
    )
