"""Dominio de WhatsApp (C-15): interpretación de respuestas y textos base.

Funciones puras arriba (``interpretar``, ``telefono_de_chat_id``); lo que toca la base abajo.
"""

import logging
import re
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, func, literal, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.agenda.models import Profesional
from app.domain.agenda.turnos import Turno, puede_transicionar, transicionar_turno
from app.domain.core.models import Clinica
from app.domain.lista_espera.models import OfertaListaEspera
from app.domain.pacientes.models import Paciente
from app.domain.pacientes.normalizacion import (
    NormalizacionError,
    normalizar_telefono,
    normalizar_texto,
)
from app.domain.reprogramacion.servicios import Ajustes
from app.domain.whatsapp.models import (
    MensajeWhatsApp,
    PlantillaWA,
    WhatsappSesion,
    nombre_sesion,
)
from app.infrastructure.whatsapp.puerto import (
    GatewayNoDisponible,
    Mensajeria,
    NoConfigurado,
    SesionNoActiva,
)

_log = logging.getLogger("turnos.whatsapp")

_CONFIRMAR = frozenset({"1", "si", "confirmo", "confirmar", "confirmado"})
_CANCELAR = frozenset({"2", "no", "cancelo", "cancelar"})
_REPROGRAMAR = frozenset({"3", "reprogramar", "reprogramo", "cambiar"})
_NO_PALABRA = re.compile(r"[^\w\s]")


class TextoIncompleto(Exception):
    """El texto base usa una variable que el servidor no calcula (bug, nunca se envía)."""


def interpretar(texto: str) -> str:
    """Primera palabra, sin mayúsculas/tildes/signos -> confirmar|cancelar|reprogramar|desconocida.

    ponytail: "primera palabra" con conjuntos fijos ("no sé" -> cancelar); la respuesta
    automática dice qué se hizo y recepción revierte. NLP solo si el piloto lo pide.
    """
    palabras = _NO_PALABRA.sub(" ", normalizar_texto(texto)).split()
    if not palabras:
        return "desconocida"
    primera = palabras[0]
    for conjunto, intencion in (
        (_CONFIRMAR, "confirmar"), (_CANCELAR, "cancelar"), (_REPROGRAMAR, "reprogramar"),
    ):  # fmt: skip
        if primera in conjunto:
            return intencion
    return "desconocida"


def telefono_de_chat_id(chat: str) -> str | None:
    """``5491100000001@c.us`` -> ``+5491100000001``; grupos, ``@lid`` o basura -> ``None``."""
    usuario, _, dominio = chat.partition("@")
    if dominio != "c.us" or not usuario.isdigit():
        return None
    try:
        return normalizar_telefono("+" + usuario)
    except NormalizacionError:
        return None


def variables_horario(
    session: Session, clinica_id: int, paciente_id: int, profesional_id: int, inicio: datetime
) -> dict[str, str]:
    """Variables de los textos base; fecha y hora en la zona de la clínica (SQL, sin tzdata)."""
    local = func.timezone(Clinica.zona_horaria, literal(inicio, DateTime(timezone=True)))
    fila = session.execute(
        select(
            Paciente.nombre, Profesional.nombre, Clinica.nombre,
            func.to_char(local, "DD/MM"), func.to_char(local, "HH24:MI"),
        )
        .select_from(Clinica)
        .join(Paciente, (Paciente.clinica_id == Clinica.id) & (Paciente.id == paciente_id))
        .join(Profesional, (Profesional.clinica_id == Clinica.id)
              & (Profesional.id == profesional_id))
        .where(Clinica.id == clinica_id)
    ).one()  # fmt: skip
    paciente, profesional, clinica, fecha, hora = fila
    return {"paciente_nombre": paciente, "profesional": profesional, "clinica": clinica,
            "fecha": fecha, "hora": hora}  # fmt: skip


def renderizar_texto(session: Session, clave: str, variables: dict[str, str]) -> str:
    """Completa el texto base ``clave``; una variable faltante es un bug (nunca se envía)."""
    texto = session.scalars(select(PlantillaWA.texto).where(PlantillaWA.clave == clave)).one()
    try:
        return texto.format_map(variables)
    except (KeyError, IndexError, ValueError) as exc:
        raise TextoIncompleto(f"texto base {clave!r}: {exc}") from exc


def renderizar(session: Session, clinica_id: int, clave: str, turno_id: int) -> str:
    """Texto base con los datos de un turno (paciente, profesional, fecha y hora locales)."""
    turno = session.scalars(
        select(Turno).where(Turno.clinica_id == clinica_id, Turno.id == turno_id)
    ).one()
    return renderizar_texto(
        session, clave,
        variables_horario(session, clinica_id, turno.paciente_id, turno.profesional_id,
                          turno.inicio),
    )  # fmt: skip


def _fallo(msg: MensajeWhatsApp, motivo: str, intento: bool = True) -> None:
    msg.estado, msg.motivo_error, msg.requiere_atencion = "error", motivo, True
    if intento:
        msg.intentos += 1


def despachar(
    session: Session, mensajeria: Mensajeria | NoConfigurado, msg: MensajeWhatsApp,
    precio: Decimal,
) -> bool:  # fmt: skip
    """Envía ``msg`` (saliente ya persistido) y commitea el resultado; True si salió.

    Éxito: ``enviado`` + id externo + costo vigente (RN-WA-02). Fallo: ``error`` + motivo +
    bandeja; el turno nunca cambia (RN-WA-01). Sin gateway no cuenta como intento: se reintenta
    cuando se configure.
    """
    if isinstance(mensajeria, NoConfigurado):
        _fallo(msg, "no_configurado", intento=False)
    else:
        assert msg.telefono is not None and msg.texto is not None
        try:
            msg.id_externo = mensajeria.enviar_texto(
                nombre_sesion(msg.clinica_id), msg.telefono, msg.texto
            )
        except SesionNoActiva:
            _fallo(msg, "sesion_no_activa")
        except GatewayNoDisponible:
            _fallo(msg, "gateway_no_disponible")
        except Exception:
            _log.exception("envío WhatsApp falló mensaje=%s", msg.id)
            _fallo(msg, "otro")
        else:
            msg.estado, msg.motivo_error, msg.requiere_atencion = "enviado", None, False
            msg.intentos += 1
            msg.costo_ars = precio
    session.commit()
    return msg.estado == "enviado"


# --- Eventos entrantes del gateway (D2, D7) -------------------------------------------------

UNIQUE_VIOLATION = "23505"
_DESTINO = {"confirmar": "confirmado", "cancelar": "cancelado"}
_RESPUESTA = {
    "confirmar": "confirmacion", "cancelar": "cancelacion", "reprogramar": "reprogramacion",
}  # fmt: skip
_ESTADOS_ENVIADO = ("enviado", "entregado", "leido")


def _recordatorio_vigente(
    session: Session, clinica_id: int, telefono: str, ahora: datetime
) -> tuple[int, int, datetime, int] | None:
    """(turno_id, paciente_id, created_at, id) del último recordatorio enviado a ese número en
    esa clínica cuyo turno sigue activo y no empezó."""
    fila = session.execute(
        select(MensajeWhatsApp.turno_id, MensajeWhatsApp.paciente_id, MensajeWhatsApp.created_at,
               MensajeWhatsApp.id)
        .join(Turno, (Turno.clinica_id == MensajeWhatsApp.clinica_id)
              & (Turno.id == MensajeWhatsApp.turno_id))
        .where(
            MensajeWhatsApp.clinica_id == clinica_id, MensajeWhatsApp.telefono == telefono,
            MensajeWhatsApp.direccion == "saliente",
            MensajeWhatsApp.plantilla == "recordatorio_24h",
            MensajeWhatsApp.estado.in_(_ESTADOS_ENVIADO),
            Turno.is_active.is_(True), Turno.inicio > ahora,
        )
        .order_by(MensajeWhatsApp.created_at.desc(), MensajeWhatsApp.id.desc())
        .limit(1)
    ).first()  # fmt: skip
    return (fila[0], fila[1], fila[2], fila[3]) if fila else None


def _oferta_vigente(
    session: Session, clinica_id: int, telefono: str, ahora: datetime
) -> tuple[int, int, datetime, int] | None:
    """(oferta_id, paciente_id, created_at, id) de la última oferta de lista de espera enviada a
    ese número cuyo hueco no empezó, en cualquier estado (C-16 D5: una respuesta tardía recibe
    ``oferta_no_disponible``)."""
    fila = session.execute(
        select(OfertaListaEspera.id, MensajeWhatsApp.paciente_id, MensajeWhatsApp.created_at,
               MensajeWhatsApp.id)
        .join(OfertaListaEspera, (OfertaListaEspera.clinica_id == MensajeWhatsApp.clinica_id)
              & (OfertaListaEspera.mensaje_id == MensajeWhatsApp.id))
        .where(
            MensajeWhatsApp.clinica_id == clinica_id, MensajeWhatsApp.telefono == telefono,
            MensajeWhatsApp.direccion == "saliente", MensajeWhatsApp.plantilla == "oferta_hueco",
            MensajeWhatsApp.estado.in_(_ESTADOS_ENVIADO), OfertaListaEspera.inicio > ahora,
        )
        .order_by(MensajeWhatsApp.created_at.desc(), MensajeWhatsApp.id.desc())
        .limit(1)
    ).first()  # fmt: skip
    return (fila[0], fila[1], fila[2], fila[3]) if fila else None


def enviar_texto_base(
    session: Session, mensajeria: Mensajeria | NoConfigurado, clinica_id: int, clave: str,
    texto: str, paciente_id: int, telefono: str, precio: Decimal, turno_id: int | None = None,
) -> tuple[MensajeWhatsApp, bool]:  # fmt: skip
    """Persiste un saliente ``pendiente`` y lo despacha (costo, estado y bandeja de C-15)."""
    msg = MensajeWhatsApp(
        clinica_id=clinica_id, turno_id=turno_id, paciente_id=paciente_id, plantilla=clave,
        direccion="saliente", telefono=telefono, estado="pendiente", texto=texto,
    )  # fmt: skip
    session.add(msg)
    session.commit()
    return msg, despachar(session, mensajeria, msg, precio)


def _responder(
    session: Session, mensajeria: Mensajeria | NoConfigurado, clinica_id: int, clave: str,
    turno_id: int, paciente_id: int, telefono: str, precio: Decimal,
) -> None:  # fmt: skip
    texto = renderizar(session, clinica_id, clave, turno_id)
    enviar_texto_base(session, mensajeria, clinica_id, clave, texto, paciente_id, telefono,
                      precio, turno_id=turno_id)  # fmt: skip


def _registrar_entrante(
    session: Session, clinica_id: int, id_externo: str, telefono: str, texto: str,
    intencion: str, paciente_id: int | None, turno_id: int | None, requiere_atencion: bool,
) -> MensajeWhatsApp | None:  # fmt: skip
    """Insert-first idempotente (C-15 D7): ``None`` si el evento ya se procesó."""
    msg = MensajeWhatsApp(
        clinica_id=clinica_id, turno_id=turno_id, paciente_id=paciente_id,
        direccion="entrante", estado="recibido", intencion=intencion, id_externo=id_externo,
        telefono=telefono, texto=texto[:2000], requiere_atencion=requiere_atencion,
    )  # fmt: skip
    session.add(msg)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == UNIQUE_VIOLATION:
            return None
        raise
    session.commit()
    return msg


def procesar_mensaje_entrante(
    session: Session, clinica_id: int, id_externo: str, telefono: str, texto: str,
    ahora: datetime, mensajeria: Mensajeria | NoConfigurado, precio: Decimal,
    ajustes: Ajustes | None = None,
) -> str:  # fmt: skip
    """Registra la respuesta y mueve la agenda (RN-TU-03). Devuelve el resultado:
    ``duplicado`` | ``confirmado`` | ``cancelado`` | ``bandeja``.

    Insert-first: el UNIQUE ``(clinica_id, id_externo)`` hace que un evento repetido (incluso
    simultáneo: el segundo espera el índice) no repita efectos. El cambio de estado va por
    ``transicionar_turno`` (C-05b) en la misma transacción que el mensaje; la respuesta al
    paciente sale después del commit y, si falla, queda en la bandeja sin deshacer el turno.
    """
    intencion = interpretar(texto)
    ajustes = ajustes or Ajustes()
    # Import diferido: el chatbot (C-17) usa este módulo para enviar y renderizar textos.
    from app.domain.reprogramacion import chatbot

    conv = chatbot.conversacion_abierta(session, clinica_id, telefono)
    if conv is not None:  # C-17 D4: dentro de la conversación un número es una opción
        msg = _registrar_entrante(session, clinica_id, id_externo, telefono, texto, intencion,
                                  conv.paciente_id, conv.turno_id, False)  # fmt: skip
        if msg is None:
            return "duplicado"
        resultado = chatbot.responder(session, conv, texto, ahora, mensajeria, precio, ajustes)
        if resultado == "bandeja":
            msg.requiere_atencion = True
            session.commit()
        return resultado
    vigente = _recordatorio_vigente(session, clinica_id, telefono, ahora)
    oferta = _oferta_vigente(session, clinica_id, telefono, ahora)
    if oferta is not None and (vigente is None or oferta[2:] > vigente[2:]):
        return _procesar_respuesta_oferta(
            session, clinica_id, id_externo, telefono, texto, intencion, oferta, ahora,
            mensajeria, precio,
        )  # fmt: skip
    turno_id, paciente_id = (vigente[0], vigente[1]) if vigente else (None, None)
    msg = MensajeWhatsApp(
        clinica_id=clinica_id, turno_id=turno_id, paciente_id=paciente_id,
        direccion="entrante", estado="recibido", intencion=intencion, id_externo=id_externo,
        telefono=telefono, texto=texto[:2000],
        requiere_atencion=vigente is None or intencion not in _DESTINO,
    )  # fmt: skip
    session.add(msg)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == UNIQUE_VIOLATION:
            return "duplicado"
        raise
    resultado = "bandeja"
    if turno_id is not None and intencion in _DESTINO:
        destino = _DESTINO[intencion]
        turno = session.scalars(
            select(Turno).where(Turno.clinica_id == clinica_id, Turno.id == turno_id)
            .with_for_update().execution_options(populate_existing=True)
        ).one()  # fmt: skip
        if puede_transicionar(turno.estado, destino):
            transicionar_turno(
                session, clinica_id, turno_id, destino, actor_id=None,
                motivo="respuesta WhatsApp", ahora=ahora, actor_tipo="paciente_whatsapp",
            )  # fmt: skip  (commitea también el mensaje entrante)
            resultado = destino
        else:  # transición imposible (p. ej. confirmar un cancelado): a la bandeja
            msg.requiere_atencion = True
    session.commit()
    if (
        turno_id is not None and paciente_id is not None and intencion == "reprogramar"
        and chatbot.iniciar(session, clinica_id, turno_id, paciente_id, telefono, ahora,
                            mensajeria, precio, ajustes)
    ):  # fmt: skip
        msg.requiere_atencion = False  # lo atiende el chatbot (C-17), no recepción
        session.commit()
        return "chatbot"
    if turno_id is not None and paciente_id is not None and (
        resultado != "bandeja" or intencion == "reprogramar"
    ):
        _responder(session, mensajeria, clinica_id, _RESPUESTA[intencion], turno_id,
                   paciente_id, telefono, precio)  # fmt: skip
    return resultado


def _procesar_respuesta_oferta(
    session: Session, clinica_id: int, id_externo: str, telefono: str, texto: str,
    intencion: str, oferta: tuple[int, int, datetime, int], ahora: datetime,
    mensajeria: Mensajeria | NoConfigurado, precio: Decimal,
) -> str:  # fmt: skip
    """Respuesta a una oferta de lista de espera (C-16 D5): mismo insert-first idempotente;
    aceptar/rechazar los resuelve ``lista_espera.servicios``."""
    oferta_id, paciente_id = oferta[0], oferta[1]
    msg = _registrar_entrante(session, clinica_id, id_externo, telefono, texto, intencion,
                              paciente_id, None, intencion not in _DESTINO)  # fmt: skip
    if msg is None:
        return "duplicado"
    if intencion not in _DESTINO:
        return "bandeja"
    # Import diferido: lista_espera depende de este módulo (despachar, textos), no al revés.
    from app.domain.lista_espera.servicios import responder_oferta

    return responder_oferta(
        session, clinica_id, oferta_id, intencion, telefono, ahora, mensajeria, precio
    )


_ORDEN_ENTREGA = {"enviado": 1, "entregado": 2, "leido": 3}
_ACK = {1: "enviado", 2: "entregado", 3: "leido", 4: "leido"}


def procesar_ack(session: Session, clinica_id: int, id_externo: str, ack: int) -> None:
    """Acuse del gateway: el estado de entrega solo avanza; ``-1`` -> error + bandeja."""
    base = update(MensajeWhatsApp).where(
        MensajeWhatsApp.clinica_id == clinica_id,
        MensajeWhatsApp.id_externo == id_externo,
        MensajeWhatsApp.direccion == "saliente",
    )
    if ack == -1:
        session.execute(
            base.where(MensajeWhatsApp.estado.in_(("pendiente", "enviado")))
            .values(estado="error", motivo_error="otro", requiere_atencion=True)
        )
    elif ack in _ACK:
        nuevo = _ACK[ack]
        previos = [e for e, o in _ORDEN_ENTREGA.items() if o < _ORDEN_ENTREGA[nuevo]]
        session.execute(
            base.where(MensajeWhatsApp.estado.in_(["pendiente", *previos])).values(estado=nuevo)
        )
    session.commit()


def procesar_estado_sesion(
    session: Session, clinica_id: int, estado: str, numero: str | None, ahora: datetime
) -> None:
    """Persiste el último estado de la sesión de la clínica; caída desde activa -> WARNING."""
    sesion = session.get(WhatsappSesion, clinica_id, with_for_update=True)
    if sesion is None:
        sesion = WhatsappSesion(clinica_id=clinica_id, nombre=nombre_sesion(clinica_id))
        session.add(sesion)
    anterior = sesion.estado
    if anterior == "activa" and estado in ("caida", "detenida"):
        _log.warning(
            '{"evento":"whatsapp_sesion_caida","clinica_id":%s,"estado":"%s"}', clinica_id, estado
        )
    if anterior != estado:
        sesion.estado, sesion.estado_at = estado, ahora
    if numero:
        sesion.numero = numero
    session.commit()


# --- Consultas de la API autenticada (D9) ---------------------------------------------------


def listar_fallos(
    session: Session, clinica_id: int, limit: int
) -> list[tuple[MensajeWhatsApp, str | None, datetime | None]]:
    """Bandeja: ``(mensaje, paciente, inicio del turno)`` sin resolver, recientes primero."""
    filas = session.execute(
        select(
            MensajeWhatsApp,
            func.concat_ws(" ", Paciente.nombre, Paciente.apellido),
            Turno.inicio,
        )
        .outerjoin(Paciente, (Paciente.clinica_id == MensajeWhatsApp.clinica_id)
                   & (Paciente.id == MensajeWhatsApp.paciente_id))
        .outerjoin(Turno, (Turno.clinica_id == MensajeWhatsApp.clinica_id)
                   & (Turno.id == MensajeWhatsApp.turno_id))
        .where(
            MensajeWhatsApp.clinica_id == clinica_id,
            MensajeWhatsApp.requiere_atencion.is_(True),
            MensajeWhatsApp.resuelto_at.is_(None),
        )
        .order_by(MensajeWhatsApp.created_at.desc(), MensajeWhatsApp.id.desc())
        .limit(limit)
    ).all()  # fmt: skip
    return [(m, nombre or None, inicio) for m, nombre, inicio in filas]


def resolver_fallo(
    session: Session, clinica_id: int, mensaje_id: int, usuario_id: int, ahora: datetime
) -> MensajeWhatsApp | None:
    """Marca resuelto un fallo de la bandeja de la clínica; ajeno o ya resuelto -> ``None``."""
    msg = session.scalars(
        select(MensajeWhatsApp).where(
            MensajeWhatsApp.clinica_id == clinica_id, MensajeWhatsApp.id == mensaje_id,
            MensajeWhatsApp.requiere_atencion.is_(True), MensajeWhatsApp.resuelto_at.is_(None),
        ).with_for_update()
    ).first()  # fmt: skip
    if msg is None:
        return None
    msg.resuelto_at, msg.resuelto_por = ahora, usuario_id
    session.commit()
    return msg


def resumen_costos(
    session: Session, clinica_id: int, desde: date, hasta: date
) -> tuple[Decimal, list[dict[str, object]]]:
    """Total ARS y desglose por (texto base, dirección), por fecha local de la clínica.

    ponytail: filtro por fecha local no indexable (``timezone(...)::date``); con volumen,
    pasar a rango de timestamps calculado en la zona de la clínica.
    """
    dia = func.date(func.timezone(Clinica.zona_horaria, MensajeWhatsApp.created_at))
    filas = session.execute(
        select(
            MensajeWhatsApp.plantilla, MensajeWhatsApp.direccion, func.count(),
            func.coalesce(func.sum(MensajeWhatsApp.costo_ars), 0),
        )
        .join(Clinica, Clinica.id == MensajeWhatsApp.clinica_id)
        .where(MensajeWhatsApp.clinica_id == clinica_id, dia.between(desde, hasta))
        .group_by(MensajeWhatsApp.plantilla, MensajeWhatsApp.direccion)
        .order_by(MensajeWhatsApp.direccion.desc(), MensajeWhatsApp.plantilla)
    ).all()  # fmt: skip
    detalle = [
        {"plantilla": p, "direccion": d, "cantidad": n, "total_ars": Decimal(t).quantize(_CENT)}
        for p, d, n, t in filas
    ]
    total = sum((x["total_ars"] for x in detalle), Decimal("0"))  # type: ignore[misc]
    return Decimal(total).quantize(_CENT), detalle


_CENT = Decimal("0.01")


def mensajes_de_turno(session: Session, clinica_id: int, turno_id: int) -> list[MensajeWhatsApp]:
    return list(
        session.scalars(
            select(MensajeWhatsApp)
            .where(MensajeWhatsApp.clinica_id == clinica_id, MensajeWhatsApp.turno_id == turno_id)
            .order_by(MensajeWhatsApp.id)
        )
    )
