"""Endpoints admin del catalogo (C-04): solo rol ``admin``, tenant del JWT.

Todos bajo ``/api/admin`` (fuera de ``PUBLIC_PREFIXES``): 401 sin token, 403 a otros roles.
El ``clinica_id`` sale siempre de ``require_tenant_checked`` y nunca del cuerpo.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.api.deps import require_tenant_checked
from app.api.permissions import require_admin
from app.domain.agenda import servicio
from app.domain.agenda.models import Bloqueo, Prestacion, Profesional, SillonRecurso
from app.domain.agenda.schemas import (
    BloqueoCreate,
    BloqueoOut,
    BloqueoUpdate,
    HabilitacionIn,
    Pagina,
    PrestacionCreate,
    PrestacionOut,
    PrestacionUpdate,
    ProfesionalCreate,
    ProfesionalOut,
    ProfesionalUpdate,
    SillonCreate,
    SillonOut,
    SillonUpdate,
)
from app.infrastructure.db import get_session

router = APIRouter(
    prefix="/api/admin", tags=["admin-catalogo"], dependencies=[Depends(require_admin())]
)

Sesion = Annotated[Session, Depends(get_session)]
Tenant = Annotated[int, Depends(require_tenant_checked)]
Limit = Annotated[int, Query(ge=1, le=200)]
AfterId = Annotated[int | None, Query(ge=0)]


def _pagina[S](items, cursor, esquema: type[S]) -> Pagina[S]:  # type: ignore[no-untyped-def]
    return Pagina[esquema](  # type: ignore[valid-type]
        items=[esquema.model_validate(i) for i in items], next_cursor=cursor
    )


# --- sillones -----------------------------------------------------------------------------


@router.get("/sillones", response_model=Pagina[SillonOut])
def listar_sillones(
    session: Sesion, tenant: Tenant, limit: Limit = 50, after_id: AfterId = None,
    incluir_inactivos: bool = False,
):  # type: ignore[no-untyped-def]
    items, cursor = servicio.listar(
        session, SillonRecurso, tenant, after_id, limit, incluir_inactivos
    )
    return _pagina(items, cursor, SillonOut)


@router.post("/sillones", response_model=SillonOut, status_code=201)
def crear_sillon(body: SillonCreate, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return servicio.crear(
        session, SillonRecurso, tenant, body.model_dump(), servicio.CONFLICTO_SILLON
    )


@router.get("/sillones/{row_id}", response_model=SillonOut)
def detalle_sillon(row_id: int, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return servicio.obtener(session, SillonRecurso, tenant, row_id)


@router.patch("/sillones/{row_id}", response_model=SillonOut)
def modificar_sillon(row_id: int, body: SillonUpdate, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return servicio.actualizar(
        session, SillonRecurso, tenant, row_id, body.model_dump(exclude_unset=True),
        servicio.CONFLICTO_SILLON,
    )


@router.delete("/sillones/{row_id}", status_code=204)
def baja_sillon(row_id: int, session: Sesion, tenant: Tenant) -> Response:
    servicio.dar_de_baja(session, SillonRecurso, tenant, row_id)
    return Response(status_code=204)


# --- prestaciones -------------------------------------------------------------------------


@router.get("/prestaciones", response_model=Pagina[PrestacionOut])
def listar_prestaciones(
    session: Sesion, tenant: Tenant, limit: Limit = 50, after_id: AfterId = None,
    incluir_inactivos: bool = False,
):  # type: ignore[no-untyped-def]
    items, cursor = servicio.listar(
        session, Prestacion, tenant, after_id, limit, incluir_inactivos
    )
    return _pagina(items, cursor, PrestacionOut)


@router.post("/prestaciones", response_model=PrestacionOut, status_code=201)
def crear_prestacion(body: PrestacionCreate, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return servicio.crear(session, Prestacion, tenant, body.model_dump(), "Prestacion duplicada")


@router.get("/prestaciones/{row_id}", response_model=PrestacionOut)
def detalle_prestacion(row_id: int, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return servicio.obtener(session, Prestacion, tenant, row_id)


@router.patch("/prestaciones/{row_id}", response_model=PrestacionOut)
def modificar_prestacion(  # type: ignore[no-untyped-def]
    row_id: int, body: PrestacionUpdate, session: Sesion, tenant: Tenant
):
    return servicio.actualizar(
        session, Prestacion, tenant, row_id, body.model_dump(exclude_unset=True),
        "Prestacion duplicada",
    )


@router.delete("/prestaciones/{row_id}", status_code=204)
def baja_prestacion(row_id: int, session: Sesion, tenant: Tenant) -> Response:
    servicio.dar_de_baja(session, Prestacion, tenant, row_id)
    return Response(status_code=204)


# --- profesionales ------------------------------------------------------------------------


def _profesional_out(session: Session, tenant: int, fila: Profesional) -> ProfesionalOut:
    out = ProfesionalOut.model_validate(fila)
    out.sillon_ids = servicio.sillon_ids_de(session, tenant, [fila.id]).get(fila.id, [])
    return out


@router.get("/profesionales", response_model=Pagina[ProfesionalOut])
def listar_profesionales(
    session: Sesion, tenant: Tenant, limit: Limit = 50, after_id: AfterId = None,
    incluir_inactivos: bool = False,
):  # type: ignore[no-untyped-def]
    items, cursor = servicio.listar(
        session, Profesional, tenant, after_id, limit, incluir_inactivos
    )
    habilitados = servicio.sillon_ids_de(session, tenant, [i.id for i in items])
    salida = []
    for fila in items:
        out = ProfesionalOut.model_validate(fila)
        out.sillon_ids = habilitados.get(fila.id, [])
        salida.append(out)
    return Pagina[ProfesionalOut](items=salida, next_cursor=cursor)


@router.post("/profesionales", response_model=ProfesionalOut, status_code=201)
def crear_profesional(body: ProfesionalCreate, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    fila = servicio.crear_profesional(session, tenant, body.model_dump())
    return _profesional_out(session, tenant, fila)


@router.get("/profesionales/{row_id}", response_model=ProfesionalOut)
def detalle_profesional(row_id: int, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return _profesional_out(session, tenant, servicio.obtener(session, Profesional, tenant, row_id))


@router.patch("/profesionales/{row_id}", response_model=ProfesionalOut)
def modificar_profesional(  # type: ignore[no-untyped-def]
    row_id: int, body: ProfesionalUpdate, session: Sesion, tenant: Tenant
):
    fila = servicio.actualizar_profesional(
        session, tenant, row_id, body.model_dump(exclude_unset=True)
    )
    return _profesional_out(session, tenant, fila)


@router.delete("/profesionales/{row_id}", status_code=204)
def baja_profesional(row_id: int, session: Sesion, tenant: Tenant) -> Response:
    servicio.dar_de_baja(session, Profesional, tenant, row_id)
    return Response(status_code=204)


@router.put("/profesionales/{row_id}/sillones", response_model=ProfesionalOut)
def reemplazar_habilitacion(  # type: ignore[no-untyped-def]
    row_id: int, body: HabilitacionIn, session: Sesion, tenant: Tenant
):
    fila = servicio.reemplazar_habilitacion(session, tenant, row_id, body.sillon_ids)
    return _profesional_out(session, tenant, fila)


# --- bloqueos -----------------------------------------------------------------------------


@router.get("/bloqueos", response_model=Pagina[BloqueoOut])
def listar_bloqueos(  # type: ignore[no-untyped-def]
    session: Sesion,
    tenant: Tenant,
    limit: Limit = 50,
    after_id: AfterId = None,
    incluir_inactivos: bool = False,
    desde: AwareDatetime | None = None,
    hasta: AwareDatetime | None = None,
    profesional_id: int | None = None,
    sillon_id: int | None = None,
):
    items, cursor = servicio.listar_bloqueos(
        session, tenant, after_id, limit, incluir_inactivos, desde, hasta, profesional_id, sillon_id
    )
    return _pagina(items, cursor, BloqueoOut)


@router.post("/bloqueos", response_model=BloqueoOut, status_code=201)
def crear_bloqueo(body: BloqueoCreate, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return servicio.crear_bloqueo(session, tenant, body.model_dump())


@router.get("/bloqueos/{row_id}", response_model=BloqueoOut)
def detalle_bloqueo(row_id: int, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return servicio.obtener(session, Bloqueo, tenant, row_id)


@router.patch("/bloqueos/{row_id}", response_model=BloqueoOut)
def modificar_bloqueo(row_id: int, body: BloqueoUpdate, session: Sesion, tenant: Tenant):  # type: ignore[no-untyped-def]
    return servicio.actualizar_bloqueo(session, tenant, row_id, body.model_dump(exclude_unset=True))


@router.delete("/bloqueos/{row_id}", status_code=204)
def baja_bloqueo(row_id: int, session: Sesion, tenant: Tenant) -> Response:
    servicio.dar_de_baja(session, Bloqueo, tenant, row_id)
    return Response(status_code=204)
