"""Router de recetas y órdenes de estudio vía partner ReNaPDiS (C-19, RN-CU-03).

Orden de chequeo de ``POST``: auth (401) -> rol odontólogo (403) -> paciente en tenant (404) ->
vínculo (403) -> consentimiento de datos (403) -> partner configurado (501) -> cuerpo (422) ->
idempotencia (200 / 409) -> profesional y evolución propia (422) -> partner (502 reintentable /
422 rechazo) -> 201. FastAPI resuelve las dependencias antes de validar el cuerpo: el usuario no
completa una receta que no se puede emitir.

Sin partner configurado, o con ``fake`` en ``ENTORNO=produccion``, la emisión responde 501 con un
mensaje de configuración; el boot nunca falla y las lecturas siguen funcionando. La receta es
inmutable: no hay PUT, PATCH ni DELETE (405). Partner, id externo, enlace, ``simulada``, autor y
fecha los pone el servidor. Solo ids y partner quedan en la auditoría, nunca ítems ni diagnóstico.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.deps import AuthContext, get_current_user
from app.api.pacientes import Escritura, Lectura, Sesion
from app.domain.agenda.schemas import Pagina
from app.domain.recetas import servicios
from app.domain.recetas.errores import PartnerNoConfigurado
from app.domain.recetas.schemas import RecetaIn, RecetaOut
from app.infrastructure.recetas.factory import obtener_partner
from app.infrastructure.recetas.partner_client import NoConfigurado, PartnerRecetas
from app.infrastructure.settings import get_settings

router = APIRouter(prefix="/api/pacientes", tags=["recetas"])

Auth = Annotated[AuthContext, Depends(get_current_user)]


def partner_recetas() -> PartnerRecetas:
    """Partner según la configuración (los tests la reemplazan con ``dependency_overrides``)."""
    partner = obtener_partner(get_settings())
    if isinstance(partner, NoConfigurado):
        raise PartnerNoConfigurado(partner.mensaje)
    return partner


Partner = Annotated[PartnerRecetas, Depends(partner_recetas)]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/{paciente_id}/recetas", response_model=RecetaOut, status_code=201)
def emitir(  # type: ignore[no-untyped-def]
    request: Request,
    response: Response,
    paciente: Escritura,
    partner: Partner,
    datos: RecetaIn,
    auth: Auth,
    session: Sesion,
):
    """Emite receta u orden vía partner; mismo ``clave_idempotencia`` y contenido -> 200."""
    secreto = get_settings().recetas_partner_key
    receta, creada = servicios.emitir_receta(
        session, auth, paciente, datos, partner,
        secreto.get_secret_value() if secreto else None, _ip(request),
    )  # fmt: skip
    if not creada:
        response.status_code = 200
    return receta


@router.get("/{paciente_id}/recetas", response_model=Pagina[RecetaOut])
def listar(  # type: ignore[no-untyped-def]
    request: Request,
    paciente: Lectura,
    auth: Auth,
    session: Sesion,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    after_id: Annotated[int | None, Query(ge=0)] = None,
):
    """Más recientes primero con enlaces al PDF; no depende del partner."""
    items, cursor = servicios.listar_recetas(session, auth, paciente, after_id, limit, _ip(request))
    return Pagina[RecetaOut](items=items, next_cursor=cursor)


@router.get("/{paciente_id}/recetas/{rid}", response_model=RecetaOut)
def detalle(  # type: ignore[no-untyped-def]
    rid: int, request: Request, paciente: Lectura, auth: Auth, session: Sesion
):
    """Una receta del paciente; la de otro paciente o clínica -> 404."""
    return servicios.obtener_receta(session, auth, paciente, rid, _ip(request))
