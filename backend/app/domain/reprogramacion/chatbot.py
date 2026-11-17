"""Chatbot de reprogramación por WhatsApp (C-17 D4): ``eligiendo -> confirmando -> cerrada``.

El estado vive en ``conversacion_wa``. Mientras hay una conversación sin cerrar con un número,
lo que escribe el paciente se interpreta DENTRO de ella: un "2" es la opción 2, nunca "cancelar
mi turno". Una conversación vencida se cierra sin tocar la agenda.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, literal, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.types import DateTime

from app.domain.agenda.models import Profesional
from app.domain.agenda.servicio import CatalogoError
from app.domain.agenda.turnos import Turno
from app.domain.core.models import Clinica
from app.domain.pacientes.normalizacion import normalizar_texto
from app.domain.reprogramacion.models import ConversacionWA
from app.domain.reprogramacion.servicios import Ajustes, HorarioOcupado, opciones, reprogramar
from app.domain.whatsapp.servicios import (
    enviar_texto_base,
    interpretar,
    renderizar,
    renderizar_texto,
    variables_horario,
)
from app.infrastructure.whatsapp.puerto import Mensajeria, NoConfigurado

_SALIR = frozenset({"0", "no", "cancelar", "cancelo"})
OCUPADO = "Ese horario se ocupó. "


def _primera_palabra(texto: str) -> str:
    palabras = "".join(c if c.isalnum() or c.isspace() else " " for c in normalizar_texto(texto))
    return palabras.split()[0] if palabras.split() else ""


def _a_json(ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"inicio": o["inicio"].isoformat(), "fin": o["fin"].isoformat(),
             "sillon_ids": list(o["sillon_ids"])} for o in ops]  # fmt: skip


def conversacion_abierta(session: Session, clinica_id: int, telefono: str) -> ConversacionWA | None:
    return session.scalars(
        select(ConversacionWA).where(
            ConversacionWA.clinica_id == clinica_id, ConversacionWA.telefono == telefono,
            ConversacionWA.estado != "cerrada",
        )
    ).first()  # fmt: skip


def _lista(session: Session, clinica_id: int, ops: list[dict[str, Any]]) -> str:
    """"1) 12/03 a las 10:00" en la zona de la clínica (SQL, sin tzdata)."""
    lineas = []
    for i, o in enumerate(ops, start=1):
        inicio = o["inicio"]
        if isinstance(inicio, str):
            inicio = datetime.fromisoformat(inicio)
        local = func.timezone(Clinica.zona_horaria, literal(inicio, DateTime(timezone=True)))
        texto = session.scalar(
            select(func.to_char(local, 'DD/MM "a las" HH24:MI')).where(Clinica.id == clinica_id)
        )
        lineas.append(f"{i}) {texto}")
    return "\n".join(lineas)


class _Envio:
    def __init__(self, session: Session, conv: ConversacionWA,
                 mensajeria: Mensajeria | NoConfigurado, precio: Decimal) -> None:  # fmt: skip
        self.s, self.conv, self.m, self.precio = session, conv, mensajeria, precio

    def texto(self, clave: str, texto: str) -> None:
        c = self.conv
        enviar_texto_base(self.s, self.m, c.clinica_id, clave, texto, c.paciente_id, c.telefono,
                          self.precio, turno_id=c.turno_id)  # fmt: skip

    def del_turno(self, clave: str, turno_id: int) -> None:
        self.texto(clave, renderizar(self.s, self.conv.clinica_id, clave, turno_id))

    def opciones(self, intro: str = "") -> None:
        c = self.conv
        turno = self.s.get(Turno, c.turno_id)
        profesional = self.s.get(Profesional, turno.profesional_id) if turno else None
        variables = {"intro": intro, "profesional": profesional.nombre if profesional else "",
                     "opciones": _lista(self.s, c.clinica_id, c.opciones)}  # fmt: skip
        self.texto("reprogramacion_opciones",
                   renderizar_texto(self.s, "reprogramacion_opciones", variables))  # fmt: skip


def iniciar(
    session: Session, clinica_id: int, turno_id: int, paciente_id: int, telefono: str,
    ahora: datetime, mensajeria: Mensajeria | NoConfigurado, precio: Decimal, ajustes: Ajustes,
) -> bool:  # fmt: skip
    """Abre la conversación y manda las opciones; False si no hay opciones (va a la bandeja)."""
    turno = session.get(Turno, turno_id)
    ops = opciones(session, turno, ahora, ajustes) if turno else []
    if not ops:
        return False
    conv = ConversacionWA(
        clinica_id=clinica_id, paciente_id=paciente_id, telefono=telefono, turno_id=turno_id,
        estado="eligiendo", opciones=_a_json(ops),
        expira_at=ahora + timedelta(minutes=ajustes.timeout_min),
    )  # fmt: skip
    session.add(conv)
    try:
        session.commit()
    except IntegrityError:  # ya hay una abierta con ese número: se reenvían sus opciones
        session.rollback()
        conv = conversacion_abierta(session, clinica_id, telefono)
        if conv is None:
            return False
    _Envio(session, conv, mensajeria, precio).opciones()
    return True


def _cerrar(session: Session, conv: ConversacionWA, resultado: str) -> None:
    conv.estado, conv.resultado = "cerrada", resultado
    session.commit()


def responder(
    session: Session, conv: ConversacionWA, texto: str, ahora: datetime,
    mensajeria: Mensajeria | NoConfigurado, precio: Decimal, ajustes: Ajustes,
) -> str:  # fmt: skip
    """Avanza la conversación con el mensaje del paciente (D4). Devuelve el resultado; ``bandeja``
    significa que recepción tiene que mirarlo."""
    envio = _Envio(session, conv, mensajeria, precio)
    palabra = _primera_palabra(texto)
    if conv.estado == "ejecutando":
        return "sin_efecto"
    if conv.expira_at <= ahora:
        _cerrar(session, conv, "vencida")
        envio.del_turno("reprogramacion_vencida", conv.turno_id)
        return "chatbot_vencida"
    if palabra in _SALIR:
        _cerrar(session, conv, "sin_cambios")
        envio.del_turno("reprogramacion_sin_cambios", conv.turno_id)
        return "chatbot_sin_cambios"
    if conv.estado == "eligiendo":
        if not (palabra.isdigit() and 1 <= int(palabra) <= len(conv.opciones)):
            return "bandeja"
        conv.elegido, conv.estado = int(palabra), "confirmando"
        conv.expira_at = ahora + timedelta(minutes=ajustes.timeout_min)
        session.commit()
        elegida = datetime.fromisoformat(conv.opciones[conv.elegido - 1]["inicio"])
        turno = session.get(Turno, conv.turno_id)
        assert turno is not None
        envio.texto("reprogramacion_confirmar", renderizar_texto(
            session, "reprogramacion_confirmar",
            variables_horario(session, conv.clinica_id, conv.paciente_id, turno.profesional_id,
                              elegida),
        ))  # fmt: skip
        return "chatbot_confirmar"
    if interpretar(texto) != "confirmar":
        return "bandeja"
    return _ejecutar(session, conv, ahora, envio, ajustes)


def _ejecutar(
    session: Session, conv: ConversacionWA, ahora: datetime, envio: _Envio, ajustes: Ajustes
) -> str:
    """Claim ``confirmando -> ejecutando`` y reprogramación (D3/D4): una sola por conversación."""
    gano = session.execute(
        update(ConversacionWA)
        .where(ConversacionWA.id == conv.id, ConversacionWA.estado == "confirmando")
        .values(estado="ejecutando")
        .returning(ConversacionWA.id)
    ).first()
    session.commit()
    if gano is None:
        return "sin_efecto"
    session.refresh(conv)
    turno = session.get(Turno, conv.turno_id, populate_existing=True)
    assert turno is not None and conv.elegido is not None
    inicio = datetime.fromisoformat(conv.opciones[conv.elegido - 1]["inicio"])
    try:
        nuevo = reprogramar(session, turno, inicio, ahora, ajustes, "paciente_whatsapp",
                            "whatsapp")  # fmt: skip
    except HorarioOcupado as exc:
        session.rollback()
        session.refresh(conv)
        if exc.alternativas:
            conv.estado, conv.elegido = "eligiendo", None
            conv.opciones = _a_json(exc.alternativas)
            conv.expira_at = ahora + timedelta(minutes=ajustes.timeout_min)
            session.commit()
            envio.opciones(intro=OCUPADO)
            return "chatbot_alternativas"
        _cerrar(session, conv, "sin_opciones")
        envio.del_turno("reprogramacion", conv.turno_id)
        return "bandeja"
    except CatalogoError:  # el turno dejó de ser reprogramable
        session.rollback()
        session.refresh(conv)
        _cerrar(session, conv, "sin_opciones")
        return "bandeja"
    session.refresh(conv)
    conv.turno_nuevo_id = nuevo.id
    _cerrar(session, conv, "reprogramado")
    envio.del_turno("reprogramacion_hecha", nuevo.id)
    return "chatbot_reprogramado"
