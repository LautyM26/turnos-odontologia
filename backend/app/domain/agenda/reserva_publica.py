"""Reserva pública por enlace, sin cuenta (C-06: US-003, Flujo 1, RN-AG-05).

Usa el mismo motor que el mostrador (``buscar_huecos`` y ``crear_turno``): hueco ofrecido ⇒
reservable. Sin seña en esta versión: la rama "seña exigida" (RN-CA-01/02, C-12) se engancha en
``reservar`` antes de crear el turno.
Nunca expone datos del paciente, sillones ni matrículas; el token se guarda solo como hash (D2).
"""

import hashlib
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.agenda.huecos import buscar_huecos
from app.domain.agenda.models import (
    FranjaHoraria,
    Prestacion,
    Profesional,
    ProfesionalSillon,
    SillonRecurso,
)
from app.domain.agenda.schemas_publicas import ReservaIn
from app.domain.agenda.servicio import Conflicto, NoEncontrado, ReferenciaInvalida
from app.domain.agenda.turnos import (
    Turno,
    TurnoNoDisponible,
    crear_turno,
    transicionar_turno,
)
from app.domain.auditoria.writer import registrar_evento_sistema
from app.domain.core.models import Clinica
from app.domain.pacientes.models import Paciente
from app.domain.pacientes.normalizacion import nombre_busqueda
from app.domain.pacientes.servicios import paciente_por_dni
from app.infrastructure.persistence.repository import BaseRepository

MAX_RESERVAS_ONLINE_POR_DNI = 2
RESERVA_NO_COMPLETADA = "No se pudo completar la reserva"
_UNIQUE_VIOLATION = "23505"
_CANCELABLES = frozenset({"reservado", "confirmado"})


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def clinica_por_slug(session: Session, slug: str) -> Clinica:
    clinica = session.scalars(
        select(Clinica).where(Clinica.slug == slug, Clinica.is_active.is_(True))
    ).first()
    if clinica is None:
        raise NoEncontrado("No encontrado")
    return clinica


def _atiende_online(clinica_id: int):  # type: ignore[no-untyped-def]
    """Profesional activo, con agenda activa y al menos una franja de horario (C-05d)."""
    return (
        Profesional.clinica_id == clinica_id,
        Profesional.is_active.is_(True),
        Profesional.agenda_activa.is_(True),
        exists().where(
            FranjaHoraria.clinica_id == clinica_id,
            FranjaHoraria.profesional_id == Profesional.id,
        ),
    )


def _validar_profesional_online(session: Session, clinica_id: int, profesional_id: int) -> None:
    online = session.scalar(
        select(Profesional.id).where(Profesional.id == profesional_id, *_atiende_online(clinica_id))
    )
    if online is None:
        raise ReferenciaInvalida("profesional_id no disponible para reserva online")


def catalogo_publico(session: Session, slug: str) -> dict[str, Any]:
    clinica = clinica_por_slug(session, slug)
    prestaciones = session.scalars(
        select(Prestacion)
        .where(Prestacion.clinica_id == clinica.id, Prestacion.is_active.is_(True))
        .order_by(Prestacion.nombre)
    ).all()
    profesionales = session.scalars(
        select(Profesional).where(*_atiende_online(clinica.id)).order_by(Profesional.nombre)
    ).all()
    return {
        "clinica": clinica.nombre,
        "zona_horaria": clinica.zona_horaria,
        "prestaciones": [
            {"id": p.id, "nombre": p.nombre, "duracion_min": p.duracion_min} for p in prestaciones
        ],
        "profesionales": [
            {"id": p.id, "nombre": p.nombre, "especialidad": p.especialidad} for p in profesionales
        ],
    }


def huecos_publicos(
    session: Session,
    slug: str,
    profesional_id: int,
    prestacion_id: int,
    desde: datetime,
    hasta: datetime,
    ahora: datetime,
    paso_min: int,
) -> list[dict[str, Any]]:
    clinica = clinica_por_slug(session, slug)
    _validar_profesional_online(session, clinica.id, profesional_id)
    huecos = buscar_huecos(
        session, clinica.id, profesional_id, prestacion_id, desde, hasta, ahora, paso_min
    )
    return [{"inicio": h["inicio"], "fin": h["fin"]} for h in huecos]


def _paciente_para_reserva(session: Session, clinica_id: int, datos: ReservaIn) -> Paciente:
    """Reutiliza el paciente del DNI sin tocar su ficha, o lo crea sin usuario (D3).

    Commit propio: los intentos por sillón de ``crear_turno`` hacen commit/rollback por su cuenta.
    """
    existente = paciente_por_dni(session, clinica_id, datos.dni)
    if existente is not None:
        if not existente.is_active:
            raise ReferenciaInvalida(RESERVA_NO_COMPLETADA)
        return existente
    valores = datos.model_dump(include={"nombre", "apellido", "dni", "email", "telefono"})
    paciente = Paciente(**valores, nombre_busqueda=nombre_busqueda(datos.apellido, datos.nombre))
    BaseRepository(session, Paciente, clinica_id).add(paciente)
    try:
        session.flush()
        campos = sorted(k for k, v in valores.items() if v is not None)
        registrar_evento_sistema(
            session, clinica_id, "crear", "paciente", paciente.id, paciente.id, {"campos": campos}
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) != _UNIQUE_VIOLATION:
            raise
        carrera = paciente_por_dni(session, clinica_id, datos.dni)  # otra reserva lo creó
        if carrera is None or not carrera.is_active:
            raise ReferenciaInvalida(RESERVA_NO_COMPLETADA) from exc
        return carrera
    return paciente


def _reservas_online_futuras(
    session: Session, clinica_id: int, paciente_id: int, ahora: datetime
) -> int:
    return session.scalar(
        select(func.count())
        .select_from(Turno)
        .where(
            Turno.clinica_id == clinica_id,
            Turno.paciente_id == paciente_id,
            Turno.origen == "enlace",
            Turno.is_active.is_(True),
            Turno.estado.in_(_CANCELABLES),
            Turno.inicio >= ahora,
        )
    )


def _sillones_habilitados(session: Session, clinica_id: int, profesional_id: int) -> list[int]:
    return list(
        session.scalars(
            select(ProfesionalSillon.sillon_id)
            .join(
                SillonRecurso,
                (SillonRecurso.id == ProfesionalSillon.sillon_id)
                & (SillonRecurso.clinica_id == ProfesionalSillon.clinica_id),
            )
            .where(
                ProfesionalSillon.clinica_id == clinica_id,
                ProfesionalSillon.profesional_id == profesional_id,
                ProfesionalSillon.is_active.is_(True),
                SillonRecurso.is_active.is_(True),
            )
            .order_by(ProfesionalSillon.sillon_id)
        ).all()
    )


def reservar(
    session: Session, slug: str, datos: ReservaIn, ahora: datetime
) -> tuple[dict[str, Any], str]:
    """Crea el turno ``reservado``/``enlace`` y devuelve (comprobante, token en claro)."""
    clinica = clinica_por_slug(session, slug)
    _validar_profesional_online(session, clinica.id, datos.profesional_id)
    if BaseRepository(session, Prestacion, clinica.id).get(datos.prestacion_id) is None:
        raise ReferenciaInvalida("prestacion_id inexistente, inactiva o de otra clinica")
    if datos.inicio < ahora:
        raise ReferenciaInvalida("No se pueden reservar turnos en el pasado")
    clinica_id = clinica.id
    paciente = _paciente_para_reserva(session, clinica_id, datos)
    paciente_id = paciente.id
    # ponytail: tope sin lock; dos reservas simultáneas del mismo DNI pueden dejar 3 turnos.
    # Freno de abuso, no integridad; si importa, SELECT ... FOR UPDATE del paciente.
    if (
        _reservas_online_futuras(session, clinica_id, paciente_id, ahora)
        >= MAX_RESERVAS_ONLINE_POR_DNI
    ):
        raise Conflicto("Límite de reservas online alcanzado para este DNI")
    token = secrets.token_urlsafe(32)
    for sillon_id in _sillones_habilitados(session, clinica_id, datos.profesional_id):
        turno_datos = {
            "profesional_id": datos.profesional_id, "sillon_id": sillon_id,
            "paciente_id": paciente_id, "prestacion_id": datos.prestacion_id,
            "inicio": datos.inicio,
        }  # fmt: skip
        try:
            turno = crear_turno(
                session, clinica_id, turno_datos, ahora,
                origen="enlace", token_publico_hash=hash_token(token),
            )  # fmt: skip
        except TurnoNoDisponible:
            continue  # ocupado en este sillón (o el profesional): probar el siguiente
        return _comprobante(session, turno, ahora), token
    raise TurnoNoDisponible()


def _turno_por_token(session: Session, token: str) -> Turno:
    turno = session.scalars(
        select(Turno).where(
            Turno.token_publico_hash == hash_token(token), Turno.is_active.is_(True)
        )
    ).first()
    if turno is None:
        raise NoEncontrado("No encontrado")
    return turno


def _comprobante(session: Session, turno: Turno, ahora: datetime) -> dict[str, Any]:
    clinica = session.get(Clinica, turno.clinica_id)
    profesional = session.get(Profesional, turno.profesional_id)
    prestacion = session.get(Prestacion, turno.prestacion_id)
    return {
        "clinica": clinica.nombre,
        "zona_horaria": clinica.zona_horaria,
        "profesional": profesional.nombre,
        "prestacion": prestacion.nombre,
        "inicio": turno.inicio,
        "fin": turno.fin,
        "estado": turno.estado,
        "cancelable": turno.estado in _CANCELABLES and ahora < turno.inicio,
    }


def obtener_por_token(session: Session, token: str, ahora: datetime) -> dict[str, Any]:
    return _comprobante(session, _turno_por_token(session, token), ahora)


def cancelar_por_token(session: Session, token: str, ahora: datetime) -> dict[str, Any]:
    """Cancela con la tabla de transiciones, solo antes del inicio; historial sin usuario (D4)."""
    turno = _turno_por_token(session, token)
    if ahora >= turno.inicio:
        raise ReferenciaInvalida("El turno ya comenzó: no se puede cancelar por enlace")
    cancelado = transicionar_turno(
        session, turno.clinica_id, turno.id, "cancelado", None, None, ahora,
        actor_tipo="paciente_enlace",
    )  # fmt: skip
    return _comprobante(session, cancelado, ahora)
