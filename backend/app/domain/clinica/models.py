"""Modelos del odontograma y las evoluciones (C-09): espejo de la migración 008.

Ambas tablas son append-only (triggers con ``fn_rechazar_mutacion()`` de la 004): solo
``TenantMixin``, sin ``AuditMixin`` (no hay update ni soft-delete). ``piezas`` no usa
``MutableDict``: una mutación in-place de un objeto cargado nunca emite UPDATE (D8).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import TenantMixin

DENTICIONES = ("permanente", "temporal", "mixta")

_PIEZA_FDI_VALIDA = (
    "pieza_fdi IS NULL "
    "OR (pieza_fdi / 10 BETWEEN 1 AND 4 AND pieza_fdi % 10 BETWEEN 1 AND 8) "
    "OR (pieza_fdi / 10 BETWEEN 5 AND 8 AND pieza_fdi % 10 BETWEEN 1 AND 5)"
)


class Odontograma(Base, TenantMixin):
    """Versión inmutable (snapshot completo) del odontograma de un paciente."""

    __tablename__ = "odontograma"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id"],
            ["paciente.clinica_id", "paciente.id"],
            name="fk_odontograma_paciente",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "autor_usuario_id"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_odontograma_autor_usuario_id",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "clinica_id", "paciente_id", "version", name="uq_odontograma_clinica_paciente_version"
        ),
        CheckConstraint("version > 0", name="version_positiva"),
        CheckConstraint("denticion IN ('permanente','temporal','mixta')", name="denticion_valida"),
        CheckConstraint("jsonb_typeof(piezas) = 'object'", name="piezas_objeto"),
        Index(
            "ix_odontograma_piezas_gin",
            "piezas",
            postgresql_using="gin",
            postgresql_ops={"piezas": "jsonb_path_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    paciente_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    denticion: Mapped[str] = mapped_column(Text, nullable=False)
    piezas: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    autor_usuario_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Evolucion(Base, TenantMixin):
    """Evolución clínica inmutable; se corrige con una fila nueva (``corrige_a_id``)."""

    __tablename__ = "evolucion"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id"],
            ["paciente.clinica_id", "paciente.id"],
            name="fk_evolucion_paciente",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "autor_usuario_id"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_evolucion_autor_usuario_id",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "profesional_id"],
            ["profesional.clinica_id", "profesional.id"],
            name="fk_evolucion_profesional",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id", "corrige_a_id"],
            ["evolucion.clinica_id", "evolucion.paciente_id", "evolucion.id"],
            name="fk_evolucion_corrige_a",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "clinica_id", "paciente_id", "id", name="uq_evolucion_clinica_paciente_id"
        ),
        CheckConstraint("length(btrim(texto)) BETWEEN 1 AND 10000", name="texto_len"),
        CheckConstraint(_PIEZA_FDI_VALIDA, name="pieza_fdi_valida"),
        CheckConstraint("(corrige_a_id IS NULL) = (motivo_correccion IS NULL)", name="correccion"),
        CheckConstraint(
            "motivo_correccion IS NULL OR length(btrim(motivo_correccion)) BETWEEN 1 AND 500",
            name="motivo_len",
        ),
        CheckConstraint("corrige_a_id IS NULL OR corrige_a_id <> id", name="no_se_autocorrige"),
        Index("ix_evolucion_clinica_paciente_id", "clinica_id", "paciente_id", text("id DESC")),
        Index(
            "uq_evolucion_corrige_a",
            "clinica_id",
            "corrige_a_id",
            unique=True,
            postgresql_where=text("corrige_a_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    paciente_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    autor_usuario_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    profesional_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    pieza_fdi: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    corrige_a_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    motivo_correccion: Mapped[str | None] = mapped_column(Text, nullable=True)
