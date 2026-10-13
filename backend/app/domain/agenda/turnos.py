"""Turnos (C-05 recorte): modelo ``Turno`` y alta sin solapamientos.

La base de datos arbitra el anti-solapamiento (exclusion constraints GiST por profesional y
por sillon, regla dura 8); el servicio hace un pre-chequeo amigable, valida referencias del
tenant y consulta bloqueos (``bloqueos_solapados``, contrato C-04) en la misma transaccion.
``fin`` se calcula SIEMPRE aqui (regla dura 6) con ``calcular_fin``.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Text,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import TSTZRANGE, ExcludeConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.domain.agenda.bloqueos import bloqueos_solapados
from app.domain.agenda.duracion import calcular_fin
from app.domain.agenda.models import Prestacion, Profesional, ProfesionalSillon, SillonRecurso
from app.domain.agenda.servicio import Conflicto, NoEncontrado, ReferenciaInvalida
from app.domain.pacientes.models import Paciente
from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import AuditMixin, TenantMixin
from app.infrastructure.persistence.repository import BaseRepository

_logger = logging.getLogger("turnos.agenda")

EXCLUSION_VIOLATION = "23P01"
ESTADOS_TURNO = ("reservado", "confirmado", "asistido", "ausente", "cancelado", "sobreturno")
ESTADOS_ACTIVOS = ("reservado", "confirmado", "asistido")
ORIGENES_TURNO = ("enlace", "mostrador", "whatsapp", "lista_espera")
HORARIO_NO_DISPONIBLE = "Horario no disponible"
_PREDICADO_ACTIVO = "is_active AND estado IN ('reservado','confirmado','asistido')"


def _fk(col: str, tabla: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["clinica_id", col],
        [f"{tabla}.clinica_id", f"{tabla}.id"],
        name=f"fk_turno_{col.removesuffix('_id')}",
        ondelete="RESTRICT",
    )


class Turno(Base, TenantMixin, AuditMixin):
    """Turno de un paciente con un profesional en un sillon; espejo de la migracion 005."""

    __tablename__ = "turno"
    __table_args__ = (
        _fk("profesional_id", "profesional"),
        _fk("sillon_id", "sillon_recurso"),
        _fk("paciente_id", "paciente"),
        _fk("prestacion_id", "prestacion"),
        CheckConstraint("fin > inicio", name="fin_posterior"),
        CheckConstraint("duracion_min BETWEEN 5 AND 480", name="duracion_rango"),
        CheckConstraint(
            "estado IN ('reservado','confirmado','asistido','ausente','cancelado','sobreturno')",
            name="estado_valido",
        ),
        CheckConstraint(
            "origen IN ('enlace','mostrador','whatsapp','lista_espera')", name="origen_valido"
        ),
        ExcludeConstraint(
            ("clinica_id", "="),
            ("profesional_id", "="),
            ("rango", "&&"),
            using="gist",
            where=text(_PREDICADO_ACTIVO),
            name="ex_turno_profesional_rango",
        ),
        ExcludeConstraint(
            ("clinica_id", "="),
            ("sillon_id", "="),
            ("rango", "&&"),
            using="gist",
            where=text(_PREDICADO_ACTIVO),
            name="ex_turno_sillon_rango",
        ),
        Index("ix_turno_clinica_profesional_inicio", "clinica_id", "profesional_id", "inicio"),
        Index("ix_turno_clinica_sillon_inicio", "clinica_id", "sillon_id", "inicio"),
        Index("ix_turno_clinica_paciente_inicio", "clinica_id", "paciente_id", "inicio"),
        Index("ix_turno_clinica_estado", "clinica_id", "estado"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    profesional_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sillon_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    paciente_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prestacion_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duracion_min: Mapped[int] = mapped_column(Integer, nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rango: Mapped[Any] = mapped_column(
        TSTZRANGE, Computed("tstzrange(inicio, fin, '[)')", persisted=True), nullable=True
    )
    estado: Mapped[str] = mapped_column(
        Text, nullable=False, default="reservado", server_default="reservado"
    )
    origen: Mapped[str] = mapped_column(
        Text, nullable=False, default="mostrador", server_default="mostrador"
    )


class TurnoNoDisponible(Conflicto):
    """409 generico: no expone ids ni datos del turno/bloqueo en conflicto."""

    def __init__(self) -> None:
        super().__init__(HORARIO_NO_DISPONIBLE)


def commit_turno(session: Session) -> None:
    """Commit; ``23P01`` (exclusion_violation) -> 409 generico, el resto se propaga."""
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == EXCLUSION_VIOLATION:
            diag = getattr(exc.orig, "diag", None)
            _logger.info(
                "turno rechazado por exclusion constraint=%s",
                getattr(diag, "constraint_name", None),
            )
            raise TurnoNoDisponible() from exc
        raise


def _validar_referencias(session: Session, clinica_id: int, datos: dict[str, Any]) -> Prestacion:
    """Todas scoped por tenant; cualquier incumplimiento -> 422 (design 7)."""
    profesional = BaseRepository(session, Profesional, clinica_id).get(datos["profesional_id"])
    if profesional is None or not profesional.agenda_activa:
        raise ReferenciaInvalida("profesional_id inexistente, inactivo o sin agenda activa")
    if BaseRepository(session, SillonRecurso, clinica_id).get(datos["sillon_id"]) is None:
        raise ReferenciaInvalida("sillon_id inexistente, inactivo o de otra clinica")
    prestacion = BaseRepository(session, Prestacion, clinica_id).get(datos["prestacion_id"])
    if prestacion is None:
        raise ReferenciaInvalida("prestacion_id inexistente, inactiva o de otra clinica")
    if BaseRepository(session, Paciente, clinica_id).get(datos["paciente_id"]) is None:
        raise ReferenciaInvalida("paciente_id inexistente, inactivo o de otra clinica")
    habilitado = session.scalars(
        select(ProfesionalSillon.profesional_id).where(
            ProfesionalSillon.clinica_id == clinica_id,
            ProfesionalSillon.profesional_id == datos["profesional_id"],
            ProfesionalSillon.sillon_id == datos["sillon_id"],
            ProfesionalSillon.is_active.is_(True),
        )
    ).first()
    if habilitado is None:
        raise ReferenciaInvalida("el profesional no esta habilitado en el sillon")
    return prestacion


def _hay_turno_solapado(
    session: Session,
    clinica_id: int,
    inicio: datetime,
    fin: datetime,
    profesional_id: int,
    sillon_id: int,
) -> bool:
    ventana = func.tstzrange(inicio, fin, "[)", type_=TSTZRANGE)
    stmt = (
        select(Turno.id)
        .where(
            Turno.clinica_id == clinica_id,
            Turno.is_active.is_(True),
            Turno.estado.in_(ESTADOS_ACTIVOS),
            Turno.rango.op("&&")(ventana),
            or_(Turno.profesional_id == profesional_id, Turno.sillon_id == sillon_id),
        )
        .limit(1)
    )
    return session.scalars(stmt).first() is not None


def crear_turno(
    session: Session,
    clinica_id: int,
    datos: dict[str, Any],
    ahora: datetime | None = None,
) -> Turno:
    """Crea un turno ``reservado``/``mostrador``; ``fin`` y ``duracion_min`` salen del servidor.

    Orden: pasado (422) -> referencias (422) -> bloqueos/solapamiento (409) -> INSERT; la
    exclusion constraint resuelve la carrera entre requests concurrentes (409 al perdedor).
    ``ahora`` se inyecta para tests deterministas (D-A4: ``inicio == ahora`` se acepta).
    """
    inicio: datetime = datos["inicio"]
    if inicio < (ahora if ahora is not None else datetime.now(UTC)):
        raise ReferenciaInvalida("No se pueden crear turnos en el pasado")
    prestacion = _validar_referencias(session, clinica_id, datos)
    fin = calcular_fin(inicio, prestacion.duracion_min)
    prof_id, sillon_id = datos["profesional_id"], datos["sillon_id"]
    if bloqueos_solapados(session, clinica_id, inicio, fin, prof_id, sillon_id):
        raise TurnoNoDisponible()
    if _hay_turno_solapado(session, clinica_id, inicio, fin, prof_id, sillon_id):
        raise TurnoNoDisponible()
    turno = Turno(
        profesional_id=prof_id,
        sillon_id=sillon_id,
        paciente_id=datos["paciente_id"],
        prestacion_id=prestacion.id,
        duracion_min=prestacion.duracion_min,
        inicio=inicio,
        fin=fin,
        estado="reservado",
        origen="mostrador",
    )
    BaseRepository(session, Turno, clinica_id).add(turno)
    commit_turno(session)
    session.refresh(turno)
    return turno


def obtener_turno(session: Session, clinica_id: int, turno_id: int) -> Turno:
    """Turno activo del tenant; ajeno, inexistente o dado de baja -> 404."""
    turno = BaseRepository(session, Turno, clinica_id).get(turno_id)
    if turno is None:
        raise NoEncontrado("No encontrado")
    return turno
