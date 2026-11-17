"""Router de la lista de espera (C-16, US-004). Admin y recepción; odontólogo -> 403 (D8).

Errores de dominio (404/409/422/502) los traduce el handler de ``CatalogoError`` de ``main``.
"""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import require_tenant_checked
from app.api.permissions import require_role
from app.api.whatsapp import MensajeriaDep
from app.domain.lista_espera import servicios
from app.domain.lista_espera.schemas import (
    EntradaIn,
    EntradaOut,
    EntradaPatch,
    MetricasOut,
    OfertaBandejaOut,
    OfertaManualIn,
    OfertaOut,
)
from app.infrastructure.db import get_session
from app.infrastructure.settings import get_settings

router = APIRouter(
    prefix="/api/lista-espera",
    tags=["lista-espera"],
    dependencies=[Depends(require_role("admin", "recepcionista"))],
)

Sesion = Annotated[Session, Depends(get_session)]
Tenant = Annotated[int, Depends(require_tenant_checked)]


@router.post("", response_model=EntradaOut, status_code=201)
def anotar(datos: EntradaIn, tenant: Tenant, session: Sesion) -> EntradaOut:
    entrada = servicios.crear_entrada(session, tenant, datos.model_dump(), datetime.now(UTC))
    return EntradaOut.model_validate(entrada)


@router.get("", response_model=list[EntradaOut])
def listar(
    tenant: Tenant, session: Sesion, prestacion_id: Annotated[int | None, Query(gt=0)] = None
) -> list[EntradaOut]:
    filas = servicios.listar_activas(session, tenant, prestacion_id)
    return [EntradaOut.model_validate(e) for e in filas]


@router.get("/bandeja", response_model=list[OfertaBandejaOut])
def bandeja(
    tenant: Tenant, session: Sesion, limit: Annotated[int, Query(ge=1, le=100)] = 50
) -> list[OfertaBandejaOut]:
    return [
        OfertaBandejaOut.model_validate(o).model_copy(
            update={"paciente_id": pid, "paciente_nombre": nombre}
        )
        for o, pid, nombre in servicios.bandeja(session, tenant, limit)
    ]


@router.get("/metricas", response_model=MetricasOut)
def metricas(tenant: Tenant, session: Sesion, desde: date, hasta: date) -> MetricasOut:
    if hasta < desde or (hasta - desde).days > 366:
        raise HTTPException(status_code=422, detail="Rango inválido: desde <= hasta, máx. 366 días")
    conteos = servicios.metricas(session, tenant, desde, hasta)
    return MetricasOut(desde=desde, hasta=hasta, **conteos)


@router.patch("/{entrada_id}", response_model=EntradaOut)
def editar(entrada_id: int, cambios: EntradaPatch, tenant: Tenant, session: Sesion) -> EntradaOut:
    entrada = servicios.editar_entrada(
        session, tenant, entrada_id, cambios.model_dump(exclude_unset=True)
    )
    return EntradaOut.model_validate(entrada)


@router.delete("/{entrada_id}", status_code=204)
def dar_de_baja(entrada_id: int, tenant: Tenant, session: Sesion) -> Response:
    servicios.dar_de_baja(session, tenant, entrada_id)
    return Response(status_code=204)


@router.post("/{entrada_id}/ofertar", response_model=OfertaOut, status_code=201)
def ofertar(
    entrada_id: int, datos: OfertaManualIn, tenant: Tenant, session: Sesion,
    mensajeria: MensajeriaDep,
) -> OfertaOut:  # fmt: skip
    oferta = servicios.ofertar_manual(
        session, mensajeria, get_settings(), tenant, entrada_id, datos.turno_liberado_id,
        datetime.now(UTC),
    )  # fmt: skip
    return OfertaOut.model_validate(oferta)
