"""Modelo de auditoría de historia clínica (C-08): append-only por trigger PG."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import TenantMixin

ACCIONES = (
    "crear",
    "actualizar",
    "leer",
    "descargar",
    "consentimiento_otorgado",
    "consentimiento_revocado",
)
ENTIDADES = ("paciente", "ficha", "adjunto")


class AuditoriaHC(Base, TenantMixin):
    """Evento inmutable: quién hizo qué sobre qué paciente (sin PHI en ``diff``)."""

    __tablename__ = "auditoria_hc"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id"],
            ["paciente.clinica_id", "paciente.id"],
            name="fk_auditoria_hc_paciente",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "actor_usuario_id"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_auditoria_hc_actor_usuario_id",
            ondelete="RESTRICT",
        ),
        CheckConstraint("actor_tipo IN ('usuario','sistema')", name="actor_tipo_valido"),
        CheckConstraint(
            "actor_tipo <> 'usuario' OR actor_usuario_id IS NOT NULL",
            name="actor_usuario_requerido",
        ),
        CheckConstraint(
            "accion IN ('crear','actualizar','leer','descargar',"
            "'consentimiento_otorgado','consentimiento_revocado')",
            name="accion_valida",
        ),
        CheckConstraint("entidad IN ('paciente','ficha','adjunto')", name="entidad_valida"),
        Index("ix_auditoria_hc_clinica_paciente_id", "clinica_id", "paciente_id", text("id DESC")),
        Index("ix_auditoria_hc_clinica_created", "clinica_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    paciente_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_usuario_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_tipo: Mapped[str] = mapped_column(Text, nullable=False, default="usuario")
    accion: Mapped[str] = mapped_column(Text, nullable=False)
    entidad: Mapped[str] = mapped_column(Text, nullable=False)
    entidad_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    diff: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    ip: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
