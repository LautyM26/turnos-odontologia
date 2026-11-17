"""Router de consentimientos informados (C-18, RN-CU-02).

Orden de chequeo (igual que la ficha de C-08): auth (401) -> rol (403) -> paciente en tenant
(404) -> vínculo (403) -> consentimiento de datos (403, solo escrituras) -> cuerpo (422) ->
consentimiento ``cid`` (404) -> ya firmado (409) -> firma incompleta (422 reintentable) ->
hash distinto (409) -> 201.

Documento firmado = bloqueado: no hay PUT, PATCH ni DELETE (405) y la base rechaza UPDATE,
DELETE y TRUNCATE. Fecha, IP (``request.client.host``; en despliegue uvicorn con
``--proxy-headers``) y dispositivo (``User-Agent``) los pone SIEMPRE el servidor: ``ip``,
``fecha`` o ``dispositivo`` en el cuerpo -> 422. Lecturas y escrituras quedan auditadas sin
texto ni datos del firmante en el diff.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import AuthContext, get_current_user
from app.api.pacientes import Escritura, Lectura, Sesion
from app.domain.cumplimiento import servicios
from app.domain.cumplimiento.schemas import ConsentimientoIn, ConsentimientoOut, FirmaIn

router = APIRouter(prefix="/api/pacientes", tags=["consentimientos"])

Auth = Annotated[AuthContext, Depends(get_current_user)]


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/{paciente_id}/consentimientos", response_model=list[ConsentimientoOut])
def listar(  # type: ignore[no-untyped-def]
    request: Request, paciente: Lectura, auth: Auth, session: Sesion
):
    """Más recientes primero, con estado y constancia si están firmados."""
    return servicios.listar_consentimientos(session, auth, paciente, _ip(request))


@router.post("/{paciente_id}/consentimientos", response_model=ConsentimientoOut, status_code=201)
def generar(  # type: ignore[no-untyped-def]
    request: Request, paciente: Escritura, datos: ConsentimientoIn, auth: Auth, session: Sesion
):
    """Crea un consentimiento pendiente con el texto vigente (texto y hash del servidor)."""
    return servicios.generar_consentimiento(session, auth, paciente, datos, _ip(request))


@router.get("/{paciente_id}/consentimientos/{cid}", response_model=ConsentimientoOut)
def detalle(  # type: ignore[no-untyped-def]
    cid: int, request: Request, paciente: Lectura, auth: Auth, session: Sesion
):
    """Documento con su constancia; el de otro paciente o clínica -> 404."""
    return servicios.obtener_consentimiento(session, auth, paciente, cid, _ip(request))


@router.post(
    "/{paciente_id}/consentimientos/{cid}/firmar", response_model=ConsentimientoOut, status_code=201
)
def firmar(  # type: ignore[no-untyped-def]
    cid: int, request: Request, paciente: Escritura, datos: FirmaIn, auth: Auth, session: Sesion
):
    """Firma electrónica asistida por el odontólogo; deja el documento bloqueado."""
    return servicios.firmar_consentimiento(
        session, auth, paciente, cid, datos, _ip(request), request.headers.get("user-agent")
    )
