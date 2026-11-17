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
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    false,
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
from app.domain.agenda.servicio import (
    Conflicto,
    NoEncontrado,
    PermisoDenegado,
    ReferenciaInvalida,
)
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
#: Un sobreturno (marca, C-05c D2) no ocupa el horario: queda fuera de las exclusion constraints.
_PREDICADO_ACTIVO = (
    "is_active AND NOT es_sobreturno AND estado IN ('reservado','confirmado','asistido')"
)

#: Única fuente de verdad de RN-TU-01 (C-05b D1). Estados sin entrada son terminales.
#: El estado ``sobreturno`` de la 005 queda sin uso desde C-05c (se modela con la marca).
TRANSICIONES: dict[str, frozenset[str]] = {
    "reservado": frozenset({"confirmado", "cancelado", "asistido", "ausente"}),
    "confirmado": frozenset({"asistido", "ausente", "cancelado"}),
}
#: Destinos que exigen ``ahora >= inicio`` (C-05b D3).
DESTINOS_DESDE_INICIO = frozenset({"asistido", "ausente"})


def puede_transicionar(desde: str, hacia: str) -> bool:
    """True solo si ``desde -> hacia`` está en la tabla de transiciones."""
    return hacia in TRANSICIONES.get(desde, frozenset())


def _fk(col: str, tabla: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["clinica_id", col],
        [f"{tabla}.clinica_id", f"{tabla}.id"],
        name=f"fk_turno_{col.removesuffix('_id')}",
        ondelete="RESTRICT",
    )


class Turno(Base, TenantMixin, AuditMixin):
    """Turno de un paciente con un profesional en un sillon; espejo de las migraciones 005/011."""

    __tablename__ = "turno"
    __table_args__ = (
        _fk("profesional_id", "profesional"),
        _fk("sillon_id", "sillon_recurso"),
        _fk("paciente_id", "paciente"),
        _fk("prestacion_id", "prestacion"),
        UniqueConstraint("clinica_id", "id", name="uq_turno_clinica_id"),  # FK de 006
        CheckConstraint("fin > inicio", name="fin_posterior"),
        CheckConstraint("duracion_min BETWEEN 5 AND 480", name="duracion_rango"),
        CheckConstraint(
            "estado IN ('reservado','confirmado','asistido','ausente','cancelado','sobreturno')",
            name="estado_valido",
        ),
        CheckConstraint(
            "origen IN ('enlace','mostrador','whatsapp','lista_espera')", name="origen_valido"
        ),
        CheckConstraint(
            "es_sobreturno = (motivo_sobreturno IS NOT NULL)", name="sobreturno_coherente"
        ),
        CheckConstraint(
            "motivo_sobreturno IS NULL OR length(motivo_sobreturno) <= 500",
            name="motivo_sobreturno_largo",
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
    es_sobreturno: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    motivo_sobreturno: Mapped[str | None] = mapped_column(Text, nullable=True)


_ESTADOS_SQL = "('reservado','confirmado','asistido','ausente','cancelado','sobreturno')"


class TurnoTransicion(Base, TenantMixin):
    """Historial append-only de cambios de estado (C-05b D4); espejo de la migración 006.

    Sin ``AuditMixin``: un registro inmutable no tiene baja lógica ni ``updated_at``. La base
    rechaza UPDATE/DELETE/TRUNCATE con ``fn_rechazar_mutacion()`` (migración 004).
    """

    __tablename__ = "turno_transicion"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "turno_id"],
            ["turno.clinica_id", "turno.id"],
            name="fk_turno_transicion_turno",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "actor_usuario_id"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_turno_transicion_actor_usuario_id",
            ondelete="RESTRICT",
        ),
        CheckConstraint(f"desde IN {_ESTADOS_SQL}", name="desde_valido"),
        CheckConstraint(f"hacia IN {_ESTADOS_SQL}", name="hacia_valido"),
        CheckConstraint("motivo IS NULL OR length(motivo) <= 500", name="motivo_largo"),
        Index("ix_turno_transicion_clinica_turno_id", "clinica_id", "turno_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    turno_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    desde: Mapped[str] = mapped_column(Text, nullable=False)
    hacia: Mapped[str] = mapped_column(Text, nullable=False)
    actor_usuario_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
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
            Turno.es_sobreturno.is_(False),
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
    Sobreturno (``datos["sobreturno"]``, C-05c D3): respeta bloqueos pero saltea el chequeo de
    solapamiento con otros turnos; queda marcado con su motivo (RN-AG-04).
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
    es_sobreturno = bool(datos.get("sobreturno", False))
    if not es_sobreturno and _hay_turno_solapado(
        session, clinica_id, inicio, fin, prof_id, sillon_id
    ):
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
        es_sobreturno=es_sobreturno,
        motivo_sobreturno=datos.get("motivo_sobreturno") if es_sobreturno else None,
    )
    BaseRepository(session, Turno, clinica_id).add(turno)
    commit_turno(session)
    session.refresh(turno)
    return turno


def transicionar_turno(
    session: Session,
    clinica_id: int,
    turno_id: int,
    destino: str,
    actor_id: int,
    motivo: str | None,
    ahora: datetime,
    solo_agenda_de: int | None = None,
    destinos_permitidos: frozenset[str] | None = None,
) -> Turno:
    """Cambia el estado según ``TRANSICIONES`` y registra el historial (RN-TU-01, C-05b).

    Orden: lock de fila (D5) -> 404 (ajeno/inexistente/baja) -> 403 fino (D2: destino o
    agenda no permitidos para el actor) -> 422 transición ilegal (D1) -> 422 ventana horaria
    (D3) -> UPDATE + INSERT historial -> commit. ``SELECT ... FOR UPDATE`` con
    ``populate_existing`` (doc SQLAlchemy 2.0 vía Context7): una transición concurrente espera
    y se evalúa contra el estado ya confirmado, nunca contra una copia vieja.
    ``solo_agenda_de``/``destinos_permitidos`` los fija la ruta para el odontólogo.
    """
    stmt = (
        select(Turno)
        .where(Turno.id == turno_id, Turno.clinica_id == clinica_id, Turno.is_active.is_(True))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    turno = session.scalars(stmt).first()
    if turno is None:
        raise NoEncontrado("No encontrado")
    if destinos_permitidos is not None and destino not in destinos_permitidos:
        raise PermisoDenegado("Transición no autorizada para el rol")
    if solo_agenda_de is not None and turno.profesional_id != solo_agenda_de:
        raise PermisoDenegado("Agenda no autorizada")
    desde = turno.estado
    if not puede_transicionar(desde, destino):
        raise ReferenciaInvalida(f"Transición no permitida: {desde} → {destino}")
    if destino in DESTINOS_DESDE_INICIO and ahora < turno.inicio:
        raise ReferenciaInvalida(f"No se puede marcar {destino} antes del inicio del turno")
    turno.estado = destino
    session.add(
        TurnoTransicion(
            clinica_id=clinica_id, turno_id=turno.id, desde=desde, hacia=destino,
            actor_usuario_id=actor_id, motivo=motivo,
        )  # fmt: skip
    )
    session.commit()
    session.refresh(turno)
    return turno


def obtener_turno(session: Session, clinica_id: int, turno_id: int) -> Turno:
    """Turno activo del tenant; ajeno, inexistente o dado de baja -> 404."""
    turno = BaseRepository(session, Turno, clinica_id).get(turno_id)
    if turno is None:
        raise NoEncontrado("No encontrado")
    return turno
