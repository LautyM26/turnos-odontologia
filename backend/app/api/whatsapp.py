"""Router de WhatsApp por sesión QR (C-15, DD-10, RN-WA-01..03, RN-TU-02/03).

``POST /api/webhooks/whatsapp`` es público (declarado en ``deps.PUBLIC_PREFIXES``) y se
autentica con HMAC-SHA512 del cuerpo crudo (D6): sin secreto -> 503, firma mala -> 401, sobre
mal formado -> 422, evento que no nos interesa o de una sesión ajena -> 200 sin efectos.

API autenticada (D9): sesión (admin/recepción ven; solo admin reconecta), bandeja de fallos,
costos en ARS y mensajes por turno; todo scoped por la clínica del JWT. Sin gateway -> 501.
"""

import hashlib
import hmac
import json
import re
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import AuthContext, require_tenant_checked
from app.api.permissions import require_role
from app.domain.agenda.turnos import obtener_turno
from app.domain.core.models import Clinica
from app.domain.whatsapp import servicios
from app.domain.whatsapp.models import WhatsappSesion, nombre_sesion
from app.domain.whatsapp.schemas import (
    CostosOut,
    Evento,
    EventoAck,
    EventoMensaje,
    EventoSesion,
    FalloOut,
    MensajeOut,
    SesionOut,
)
from app.infrastructure.db import get_session
from app.infrastructure.settings import Settings, get_settings
from app.infrastructure.whatsapp.factory import obtener_mensajeria
from app.infrastructure.whatsapp.puerto import (
    EstadoSesion,
    GatewayNoDisponible,
    Mensajeria,
    NoConfigurado,
)
from app.infrastructure.whatsapp.waha import parsear_evento

router = APIRouter(tags=["whatsapp"])

Sesion = Annotated[Session, Depends(get_session)]
_SESION_CLINICA = re.compile(r"^clinica-([0-9]{1,18})$")


def mensajeria_wa() -> Mensajeria | NoConfigurado:
    """Gateway según la configuración (los tests lo reemplazan con ``dependency_overrides``)."""
    return obtener_mensajeria(get_settings())


MensajeriaDep = Annotated[Mensajeria | NoConfigurado, Depends(mensajeria_wa)]


def _clinica_de_sesion(session: Session, nombre: str) -> int | None:
    m = _SESION_CLINICA.fullmatch(nombre or "")
    if m is None:
        return None
    clinica_id = int(m.group(1))
    return clinica_id if session.get(Clinica, clinica_id) is not None else None


def _aplicar(
    session: Session, evento: Evento | None, mensajeria: Mensajeria | NoConfigurado,
    settings: Settings,
) -> str:  # fmt: skip
    if evento is None:
        return "ignorado"
    clinica_id = _clinica_de_sesion(session, evento.sesion)
    if clinica_id is None:
        return "ignorado"
    ahora = datetime.now(UTC)
    if isinstance(evento, EventoMensaje):
        telefono = servicios.telefono_de_chat_id(evento.chat)
        if telefono is None:  # grupos, @lid: fuera de alcance
            return "ignorado"
        return servicios.procesar_mensaje_entrante(
            session, clinica_id, evento.id_externo, telefono, evento.texto, ahora, mensajeria,
            settings.ars_precio_mensaje,
        )  # fmt: skip
    if isinstance(evento, EventoAck):
        servicios.procesar_ack(session, clinica_id, evento.id_externo, evento.ack)
    elif isinstance(evento, EventoSesion):
        servicios.procesar_estado_sesion(session, clinica_id, evento.estado, evento.numero, ahora)
    return "ok"


@router.post("/api/webhooks/whatsapp")
async def webhook(request: Request, session: Sesion, mensajeria: MensajeriaDep) -> dict[str, str]:
    """Eventos del gateway QR firmados con HMAC-SHA512 (``X-Webhook-Hmac``)."""
    cuerpo = await request.body()
    settings = get_settings()
    clave = settings.whatsapp_webhook_hmac_key
    if clave is None:
        raise HTTPException(status_code=503, detail="Webhook de WhatsApp no configurado")
    esperado = hmac.new(clave.get_secret_value().encode(), cuerpo, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(esperado, request.headers.get("X-Webhook-Hmac", "")):
        raise HTTPException(status_code=401, detail="Firma inválida")
    try:
        evento = parsear_evento(json.loads(cuerpo))
    except (ValueError, ValidationError, KeyError, TypeError, AttributeError):
        raise HTTPException(status_code=422, detail="Evento mal formado") from None
    resultado = await run_in_threadpool(_aplicar, session, evento, mensajeria, settings)
    return {"resultado": resultado}


# --- API autenticada (D9) -------------------------------------------------------------------

Staff = Annotated[AuthContext, Depends(require_role("admin", "recepcionista"))]
Admin = Annotated[AuthContext, Depends(require_role("admin"))]
Tenant = Annotated[int, Depends(require_tenant_checked)]


def _configurada(mensajeria: Mensajeria | NoConfigurado) -> Mensajeria:
    if isinstance(mensajeria, NoConfigurado):
        raise HTTPException(status_code=501, detail=mensajeria.mensaje)
    return mensajeria


def _salida(
    session: Session, clinica_id: int, mensajeria: Mensajeria, vivo: EstadoSesion | None
) -> SesionOut:
    """Persiste el estado en vivo (si lo hay) y arma la respuesta con QR si hay que escanear."""
    if vivo is not None:
        servicios.procesar_estado_sesion(
            session, clinica_id, vivo.estado, vivo.numero, datetime.now(UTC)
        )
    fila = session.get(WhatsappSesion, clinica_id)
    estado = fila.estado if fila else "desconocido"
    qr = None
    if vivo is not None and estado == "escanear_qr":
        try:
            qr = mensajeria.qr(nombre_sesion(clinica_id))
        except GatewayNoDisponible:
            qr = None
    return SesionOut(
        estado=estado, numero=fila.numero if fila else None,
        estado_at=fila.estado_at if fila else None, en_vivo=vivo is not None, qr=qr,
    )  # fmt: skip


@router.get("/api/whatsapp/sesion", response_model=SesionOut)
def ver_sesion(
    auth: Staff, tenant: Tenant, session: Sesion, mensajeria: MensajeriaDep
) -> SesionOut:
    """Estado de la sesión QR de la clínica (en vivo; si el gateway no responde, el último)."""
    gateway = _configurada(mensajeria)
    try:
        vivo: EstadoSesion | None = gateway.estado(nombre_sesion(tenant))
    except GatewayNoDisponible:
        vivo = None
    return _salida(session, tenant, gateway, vivo)


@router.post("/api/whatsapp/sesion/reconectar", response_model=SesionOut)
def reconectar(
    auth: Admin, tenant: Tenant, session: Sesion, mensajeria: MensajeriaDep
) -> SesionOut:
    """Inicia o reinicia la sesión con el webhook firmado hacia esta API (solo admin)."""
    gateway = _configurada(mensajeria)
    settings = get_settings()
    clave = settings.whatsapp_webhook_hmac_key
    url = settings.app_base_url.rstrip("/") + "/api/webhooks/whatsapp"
    try:
        vivo = gateway.iniciar(
            nombre_sesion(tenant), url, clave.get_secret_value() if clave else None
        )
    except GatewayNoDisponible:
        raise HTTPException(status_code=503, detail="Gateway de WhatsApp no disponible") from None
    return _salida(session, tenant, gateway, vivo)


@router.get("/api/whatsapp/fallos", response_model=list[FalloOut])
def fallos(
    auth: Staff, tenant: Tenant, session: Sesion,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[FalloOut]:  # fmt: skip
    """Bandeja de recepción: envíos fallidos y respuestas que no movieron la agenda."""
    return [
        FalloOut.model_validate(m).model_copy(
            update={"paciente_nombre": nombre, "turno_inicio": inicio}
        )
        for m, nombre, inicio in servicios.listar_fallos(session, tenant, limit)
    ]


@router.post("/api/whatsapp/fallos/{mensaje_id}/resolver", response_model=MensajeOut)
def resolver(mensaje_id: int, auth: Staff, tenant: Tenant, session: Sesion) -> MensajeOut:
    """Recepción avisó a mano: el fallo sale de la bandeja (ajeno o ya resuelto -> 404)."""
    msg = servicios.resolver_fallo(session, tenant, mensaje_id, auth.sub, datetime.now(UTC))
    if msg is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    return MensajeOut.model_validate(msg)


@router.get("/api/whatsapp/costos", response_model=CostosOut)
def costos(auth: Staff, tenant: Tenant, session: Sesion, desde: date, hasta: date) -> CostosOut:
    """Total y desglose en ARS por fecha local de la clínica (RN-WA-02)."""
    if hasta < desde or (hasta - desde).days > 366:
        raise HTTPException(status_code=422, detail="Rango inválido: desde <= hasta, máx. 366 días")
    total, detalle = servicios.resumen_costos(session, tenant, desde, hasta)
    return CostosOut.model_validate(
        {"desde": desde, "hasta": hasta, "total_ars": total, "detalle": detalle}
    )


@router.get("/api/whatsapp/mensajes", response_model=list[MensajeOut])
def mensajes(auth: Staff, tenant: Tenant, session: Sesion, turno_id: int) -> list[MensajeOut]:
    """Mensajes de un turno de la clínica (RN-WA-03); turno ajeno -> 404."""
    obtener_turno(session, tenant, turno_id)
    filas = servicios.mensajes_de_turno(session, tenant, turno_id)
    return [MensajeOut.model_validate(m) for m in filas]
