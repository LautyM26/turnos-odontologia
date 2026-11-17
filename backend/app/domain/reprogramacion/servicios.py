"""Reprogramación de turnos (C-17 D2/D3, US-006, RN-TU-03): un solo servicio para WhatsApp y
para el enlace de la reserva online.

Reprogramar = turno nuevo con ``crear_turno`` (mismas reglas y 409 que el mostrador) + cancelar
el viejo con ``transicionar_turno``; el hueco viejo lo levanta la lista de espera (C-16).
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.domain.agenda.bloqueos import bloqueos_solapados
from app.domain.agenda.duracion import calcular_fin
from app.domain.agenda.horario import dentro_de_horario
from app.domain.agenda.huecos import buscar_huecos
from app.domain.agenda.models import Prestacion
from app.domain.agenda.servicio import CatalogoError, Conflicto, ReferenciaInvalida
from app.domain.agenda.turnos import Turno, TurnoNoDisponible, crear_turno, transicionar_turno
from app.domain.pacientes.models import Paciente
from app.domain.whatsapp.models import MensajeWhatsApp

_log = logging.getLogger("turnos.reprogramacion")
REPROGRAMABLES = ("reservado", "confirmado")
MAX_OPCIONES = 3
DIAS_BUSQUEDA = 14


@dataclass(frozen=True)
class Ajustes:
    """Lo que la reprogramación necesita de ``Settings`` (defaults = los de ``Settings``)."""

    timeout_min: int = 30
    anticipacion_min: int = 120
    paso_min: int = 15

    @classmethod
    def desde(cls, settings: Any) -> "Ajustes":
        return cls(settings.chatbot_timeout_min, settings.reprogramacion_anticipacion_min,
                   settings.agenda_paso_min)  # fmt: skip


class HorarioOcupado(Conflicto):
    """409: el horario elegido se ocupó; ``alternativas`` son las opciones vigentes."""

    def __init__(self, alternativas: list[dict[str, Any]]) -> None:
        super().__init__("Horario no disponible")
        self.alternativas = alternativas


def reprogramable(turno: Turno, ahora: datetime) -> bool:
    return turno.is_active and turno.estado in REPROGRAMABLES and turno.inicio > ahora


def _redondear(momento: datetime, paso_min: int) -> datetime:
    paso = paso_min * 60
    return datetime.fromtimestamp(math.ceil(momento.timestamp() / paso) * paso, momento.tzinfo)


def opciones(
    session: Session, turno: Turno, ahora: datetime, ajustes: Ajustes
) -> list[dict[str, Any]]:
    """Hasta 3 huecos del mismo profesional y prestación, desde la anticipación mínima y hasta
    14 días (D2). Turno no reprogramable -> ``[]``."""
    if not reprogramable(turno, ahora):
        return []
    desde = _redondear(ahora + timedelta(minutes=ajustes.anticipacion_min), ajustes.paso_min)
    encontrados: list[dict[str, Any]] = []
    for semana in range(DIAS_BUSQUEDA // 7):
        a = desde + timedelta(days=7 * semana)
        try:
            encontrados += buscar_huecos(
                session, turno.clinica_id, turno.profesional_id, turno.prestacion_id, a,
                a + timedelta(days=7), ahora, ajustes.paso_min,
            )  # fmt: skip
        except ReferenciaInvalida:  # profesional sin agenda o prestación inactiva
            return []
        if len(encontrados) >= MAX_OPCIONES:
            break
    return encontrados[:MAX_OPCIONES]


def _sillones_libres(
    session: Session, turno: Turno, inicio: datetime, ahora: datetime, ajustes: Ajustes
) -> list[int]:
    """Sillones en que un turno de esta prestación entraría en ``inicio`` (vacío = no entra).

    La ventana es exactamente ``[inicio, fin)``: ``buscar_huecos`` solo genera inicios cuyo
    turno completo entra en la ventana.
    """
    prestacion = session.get(Prestacion, turno.prestacion_id)  # duración vigente (RN-AG-02)
    if prestacion is None:
        return []
    try:
        huecos = buscar_huecos(
            session, turno.clinica_id, turno.profesional_id, turno.prestacion_id, inicio,
            inicio + timedelta(minutes=prestacion.duracion_min), ahora, ajustes.paso_min,
        )  # fmt: skip
    except ReferenciaInvalida:
        return []
    return list(huecos[0]["sillon_ids"]) if huecos and huecos[0]["inicio"] == inicio else []


def _ocupado_por_turno(session: Session, turno: Turno, inicio: datetime) -> bool:
    """El horario es válido (atención, sin bloqueo) pero lo tomó otro turno -> 409, no 422."""
    prestacion = session.get(Prestacion, turno.prestacion_id)
    assert prestacion is not None
    fin = calcular_fin(inicio, prestacion.duracion_min)
    return dentro_de_horario(
        session, turno.clinica_id, turno.profesional_id, inicio, fin
    ) and not bloqueos_solapados(
        session, turno.clinica_id, inicio, fin, turno.profesional_id, turno.sillon_id
    )


def _alerta_doble_turno(session: Session, viejo: Turno, nuevo: Turno) -> None:
    """D3: si no se pudo cancelar el viejo, recepción lo ve en la bandeja de WhatsApp."""
    paciente = session.get(Paciente, viejo.paciente_id)
    telefono = paciente.telefono if paciente else None
    session.add(MensajeWhatsApp(
        clinica_id=viejo.clinica_id, turno_id=viejo.id, paciente_id=viejo.paciente_id,
        direccion="saliente", telefono=telefono, estado="error",
        motivo_error="otro" if telefono else "sin_telefono", requiere_atencion=True,
        texto=f"Revisar: la reprogramación creó el turno {nuevo.id} pero el turno {viejo.id} "
              "no se pudo cancelar.",
    ))  # fmt: skip
    session.commit()
    _log.warning("reprogramacion_doble_turno viejo=%s nuevo=%s", viejo.id, nuevo.id)


def reprogramar(
    session: Session, turno: Turno, inicio: datetime, ahora: datetime, ajustes: Ajustes,
    actor_tipo: str, origen: str, exigir_opcion: bool = False,
) -> Turno:  # fmt: skip
    """Crea el turno nuevo en ``inicio`` y cancela ``turno`` (D3).

    422 (``ReferenciaInvalida``): turno no reprogramable, ``inicio`` fuera de la ventana o, con
    ``exigir_opcion``, que no es una de las opciones vigentes. 409 (``HorarioOcupado``): el
    horario lo tomó otro turno; lleva las alternativas vigentes. El token del enlace (C-06) pasa
    al turno nuevo.
    """
    if not reprogramable(turno, ahora):
        raise ReferenciaInvalida("El turno no se puede reprogramar")
    # La anticipación se exige al OFRECER; una opción ya ofrecida (chatbot) solo tiene que seguir
    # en el futuro y libre: si no, confirmar 1 minuto después rechazaría el primer horario.
    minimo = ahora + timedelta(minutes=ajustes.anticipacion_min) if exigir_opcion else ahora
    if inicio < minimo or inicio <= ahora or inicio > ahora + timedelta(days=DIAS_BUSQUEDA + 1):
        raise ReferenciaInvalida("El horario está fuera de la ventana de reprogramación")
    sillones = _sillones_libres(session, turno, inicio, ahora, ajustes)
    if not sillones:
        if _ocupado_por_turno(session, turno, inicio):
            raise HorarioOcupado(opciones(session, turno, ahora, ajustes))
        raise ReferenciaInvalida("El horario elegido no está disponible para este turno")
    if exigir_opcion and inicio not in [o["inicio"] for o in opciones(session, turno, ahora,
                                                                        ajustes)]:  # fmt: skip
        raise ReferenciaInvalida("El horario elegido no es una de las opciones disponibles")
    viejo_id, token = turno.id, turno.token_publico_hash
    datos = {"profesional_id": turno.profesional_id, "paciente_id": turno.paciente_id,
             "prestacion_id": turno.prestacion_id, "inicio": inicio}  # fmt: skip
    nuevo = None
    for sillon_id in sillones:
        if token is not None:  # el UNIQUE del hash: se libera antes de dárselo al nuevo
            turno.token_publico_hash = None
            session.flush()
        try:
            nuevo = crear_turno(session, turno.clinica_id, {**datos, "sillon_id": sillon_id},
                                ahora=ahora, origen=origen, token_publico_hash=token)  # fmt: skip
            break
        except TurnoNoDisponible:
            session.rollback()  # restaura el hash del viejo
            turno = session.get(Turno, viejo_id, populate_existing=True)  # type: ignore[assignment]
    if nuevo is None:
        raise HorarioOcupado(opciones(session, turno, ahora, ajustes))
    try:
        transicionar_turno(
            session, turno.clinica_id, viejo_id, "cancelado", actor_id=None,
            motivo=f"reprogramado al turno {nuevo.id}", ahora=ahora, actor_tipo=actor_tipo,
        )  # fmt: skip
    except CatalogoError:
        session.rollback()
        viejo = session.get(Turno, viejo_id)
        assert viejo is not None
        _alerta_doble_turno(session, viejo, nuevo)
    return nuevo
