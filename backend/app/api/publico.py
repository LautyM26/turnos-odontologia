"""API pública de reserva online (C-06 D5): sin JWT ni ``X-Clinica-Id``.

El tenant sale del ``slug`` de la clínica o del turno encontrado por el hash del token; nunca
del cliente. Límite por IP con el limiter de slowapi (429 + ``Retry-After`` por el handler de
``main``). Respuestas sin datos del paciente, sillones ni matrículas.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.turnos import get_ahora
from app.domain.agenda import reserva_publica
from app.domain.agenda.schemas_publicas import (
    CatalogoPublicoOut,
    HuecoPublicoOut,
    ReservaCreadaOut,
    ReservaIn,
    ReservaPublicaOut,
)
from app.domain.agenda.servicio import NoEncontrado, ReferenciaInvalida
from app.domain.agenda.turnos import Turno
from app.domain.auth.ratelimit import limiter
from app.domain.reprogramacion.schemas import ReprogramarIn
from app.domain.reprogramacion.servicios import (
    Ajustes,
    HorarioOcupado,
    opciones,
    reprogramable,
    reprogramar,
)
from app.infrastructure.db import get_session
from app.infrastructure.settings import get_settings

router = APIRouter(prefix="/api/public", tags=["reserva-publica"])

Sesion = Annotated[Session, Depends(get_session)]
Ahora = Annotated[datetime, Depends(get_ahora)]


def _lectura() -> str:
    return get_settings().rate_limit_publico_lectura


def _escritura() -> str:
    return get_settings().rate_limit_publico_reserva


lectura = limiter.limit(_lectura, key_func=get_remote_address)
escritura = limiter.limit(_escritura, key_func=get_remote_address)


@router.get("/clinicas/{slug}", response_model=CatalogoPublicoOut)
@lectura
def catalogo(request: Request, slug: str, session: Sesion):  # type: ignore[no-untyped-def]
    return reserva_publica.catalogo_publico(session, slug)


@router.get("/clinicas/{slug}/huecos", response_model=list[HuecoPublicoOut])
@lectura
def huecos(  # type: ignore[no-untyped-def]
    request: Request,
    slug: str,
    profesional_id: int,
    prestacion_id: int,
    desde: Annotated[AwareDatetime, Query()],
    hasta: Annotated[AwareDatetime, Query()],
    session: Sesion,
    ahora: Ahora,
):
    return reserva_publica.huecos_publicos(
        session, slug, profesional_id, prestacion_id, desde, hasta, ahora,
        get_settings().agenda_paso_min,
    )  # fmt: skip


@router.post("/clinicas/{slug}/reservas", response_model=ReservaCreadaOut, status_code=201)
@escritura
def reservar(request: Request, slug: str, body: ReservaIn, session: Sesion, ahora: Ahora):  # type: ignore[no-untyped-def]
    comprobante, token = reserva_publica.reservar(session, slug, body, ahora)
    return {**comprobante, "token": token}


@router.get("/reservas/{token}", response_model=ReservaPublicaOut)
@lectura
def ver_reserva(request: Request, token: str, session: Sesion, ahora: Ahora):  # type: ignore[no-untyped-def]
    return reserva_publica.obtener_por_token(session, token, ahora)


@router.post("/reservas/{token}/cancelar", response_model=ReservaPublicaOut)
@escritura
def cancelar_reserva(request: Request, token: str, session: Sesion, ahora: Ahora):  # type: ignore[no-untyped-def]
    return reserva_publica.cancelar_por_token(session, token, ahora)


# --- Reprogramación por enlace (C-17 D5): mismo servicio que el chatbot de WhatsApp. ---------


def _turno_reprogramable(session: Session, token: str, ahora: datetime) -> Turno:
    turno = session.scalars(
        select(Turno).where(
            Turno.token_publico_hash == reserva_publica.hash_token(token),
            Turno.is_active.is_(True),
        )
    ).first()
    if turno is None:
        raise NoEncontrado("No encontrado")
    if not reprogramable(turno, ahora):
        raise ReferenciaInvalida("El turno no se puede reprogramar")
    return turno


def _horarios(ops: list[dict]) -> list[dict]:  # type: ignore[type-arg]
    return [{"inicio": o["inicio"], "fin": o["fin"]} for o in ops]  # sin sillones


@router.get("/reservas/{token}/opciones", response_model=list[HuecoPublicoOut])
@lectura
def opciones_reprogramacion(request: Request, token: str, session: Sesion, ahora: Ahora):  # type: ignore[no-untyped-def]
    turno = _turno_reprogramable(session, token, ahora)
    return _horarios(opciones(session, turno, ahora, Ajustes.desde(get_settings())))


@router.post("/reservas/{token}/reprogramar", response_model=ReservaPublicaOut)
@escritura
def reprogramar_reserva(  # type: ignore[no-untyped-def]
    request: Request, token: str, body: ReprogramarIn, session: Sesion, ahora: Ahora
):
    """Turno nuevo + original cancelado (actor ``paciente_enlace``); el token sigue al nuevo.
    Horario ocupado al confirmar -> 409 con las alternativas vigentes."""
    turno = _turno_reprogramable(session, token, ahora)
    try:
        reprogramar(session, turno, body.inicio, ahora, Ajustes.desde(get_settings()),
                    "paciente_enlace", "enlace", exigir_opcion=True)  # fmt: skip
    except HorarioOcupado as exc:
        alternativas = [
            {k: v.isoformat() for k, v in h.items()} for h in _horarios(exc.alternativas)
        ]
        return JSONResponse(
            status_code=409, content={"detail": exc.detail, "alternativas": alternativas}
        )
    return reserva_publica.obtener_por_token(session, token, ahora)
