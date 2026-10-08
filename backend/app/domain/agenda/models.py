"""Modelos del catalogo de agenda (C-04): espejo de la migracion 003."""

from datetime import datetime
from decimal import Decimal
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
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TSTZRANGE
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import AuditMixin, TenantMixin

TIPOS_SILLON = ("sillon", "box", "equipo")


class Profesional(Base, TenantMixin, AuditMixin):
    """Profesional de la clinica; ``usuario_id`` lo vincula a un login (agenda propia)."""

    __tablename__ = "profesional"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "usuario_id"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_profesional_usuario",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("clinica_id", "id", name="uq_profesional_clinica_id"),
        CheckConstraint("length(nombre) BETWEEN 1 AND 200", name="nombre_len"),
        CheckConstraint("length(matricula) BETWEEN 1 AND 50", name="matricula_len"),
        Index(
            "uq_profesional_matricula_activa",
            "clinica_id",
            text("lower(matricula)"),
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "uq_profesional_usuario_activo",
            "clinica_id",
            "usuario_id",
            unique=True,
            postgresql_where=text("usuario_id IS NOT NULL AND is_active"),
        ),
        Index("ix_profesional_clinica_activo", "clinica_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    matricula: Mapped[str] = mapped_column(Text, nullable=False)
    especialidad: Mapped[str | None] = mapped_column(Text, nullable=True)
    agenda_activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tercerizado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    usuario_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    es_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SillonRecurso(Base, TenantMixin, AuditMixin):
    """Sillon, box o equipo reservable."""

    __tablename__ = "sillon_recurso"
    __table_args__ = (
        UniqueConstraint("clinica_id", "id", name="uq_sillon_recurso_clinica_id"),
        CheckConstraint("length(nombre) BETWEEN 1 AND 200", name="nombre_len"),
        CheckConstraint("tipo IN ('sillon','box','equipo')", name="tipo_valido"),
        Index(
            "uq_sillon_recurso_nombre_activo",
            "clinica_id",
            text("lower(nombre)"),
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index("ix_sillon_recurso_clinica_activo", "clinica_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    es_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Prestacion(Base, TenantMixin, AuditMixin):
    """Prestacion con duracion (fuente del fin del turno) y precio de referencia."""

    __tablename__ = "prestacion"
    __table_args__ = (
        CheckConstraint("length(nombre) BETWEEN 1 AND 200", name="nombre_len"),
        CheckConstraint("duracion_min BETWEEN 5 AND 480", name="duracion_rango"),
        CheckConstraint("precio_referencia >= 0", name="precio_no_negativo"),
        Index("ix_prestacion_clinica_activo", "clinica_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    duracion_min: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_referencia: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    es_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ProfesionalSillon(Base, TenantMixin, AuditMixin):
    """Habilitacion N-M profesional <-> sillon (FK compuestas por tenant)."""

    __tablename__ = "profesional_sillon"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "profesional_id"],
            ["profesional.clinica_id", "profesional.id"],
            name="fk_profesional_sillon_profesional",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "sillon_id"],
            ["sillon_recurso.clinica_id", "sillon_recurso.id"],
            name="fk_profesional_sillon_sillon",
            ondelete="RESTRICT",
        ),
        Index("ix_profesional_sillon_clinica_sillon", "clinica_id", "sillon_id"),
    )

    profesional_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sillon_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class Bloqueo(Base, TenantMixin, AuditMixin):
    """Bloqueo de agenda: clinica, profesional o sillon (alcance unico)."""

    __tablename__ = "bloqueo"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "profesional_id"],
            ["profesional.clinica_id", "profesional.id"],
            name="fk_bloqueo_profesional",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "sillon_id"],
            ["sillon_recurso.clinica_id", "sillon_recurso.id"],
            name="fk_bloqueo_sillon",
            ondelete="RESTRICT",
        ),
        CheckConstraint("fin > inicio", name="fin_posterior"),
        CheckConstraint("fin - inicio <= interval '31 days'", name="duracion_maxima"),
        CheckConstraint(
            "NOT (profesional_id IS NOT NULL AND sillon_id IS NOT NULL)", name="alcance_unico"
        ),
        CheckConstraint("length(motivo) BETWEEN 1 AND 200", name="motivo_len"),
        Index(
            "ix_bloqueo_rango_activo",
            "clinica_id",
            "rango",
            postgresql_using="gist",
            postgresql_where=text("is_active"),
        ),
        Index("ix_bloqueo_clinica_profesional", "clinica_id", "profesional_id"),
        Index("ix_bloqueo_clinica_sillon", "clinica_id", "sillon_id"),
        Index("ix_bloqueo_clinica_activo", "clinica_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    profesional_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sillon_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
    rango: Mapped[Any] = mapped_column(
        TSTZRANGE, Computed("tstzrange(inicio, fin, '[)')", persisted=True), nullable=True
    )
