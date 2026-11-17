"""Modelo de la receta emitida vía partner (C-19): espejo de la migración 010.

Append-only (triggers con ``fn_rechazar_mutacion()`` de la 004): solo ``TenantMixin``.
Se guarda el enlace al PDF del partner, no el binario (DT-4).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CHAR, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import TenantMixin


class RecetaExterna(Base, TenantMixin):
    """Receta u orden de estudio emitida por el partner; inmutable."""

    __tablename__ = "receta_externa"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id"],
            ["paciente.clinica_id", "paciente.id"],
            name="fk_receta_externa_paciente",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id", "evolucion_id"],
            ["evolucion.clinica_id", "evolucion.paciente_id", "evolucion.id"],
            name="fk_receta_externa_evolucion",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "autor_usuario_id"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_receta_externa_autor_usuario_id",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "profesional_id"],
            ["profesional.clinica_id", "profesional.id"],
            name="fk_receta_externa_profesional",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("clinica_id", "clave_idempotencia", name="uq_receta_externa_clave"),
        UniqueConstraint(
            "clinica_id", "partner", "id_externo", name="uq_receta_externa_partner_id_externo"
        ),
        CheckConstraint("tipo IN ('receta','orden_estudio')", name="tipo_valido"),
        CheckConstraint("pdf_url ~ '^https://'", name="pdf_url_https"),
        CheckConstraint("length(btrim(diagnostico)) BETWEEN 1 AND 500", name="diagnostico_len"),
        CheckConstraint("jsonb_typeof(items) = 'array'", name="items_arreglo"),
        CheckConstraint("huella_solicitud ~ '^[0-9a-f]{64}$'", name="huella_formato"),
        Index(
            "ix_receta_externa_clinica_paciente_id", "clinica_id", "paciente_id", text("id DESC")
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    paciente_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    evolucion_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    partner: Mapped[str] = mapped_column(Text, nullable=False)
    simulada: Mapped[bool] = mapped_column(Boolean, nullable=False)
    id_externo: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_url: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostico: Mapped[str] = mapped_column(Text, nullable=False)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    clave_idempotencia: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    huella_solicitud: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    autor_usuario_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    profesional_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    emitida_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
