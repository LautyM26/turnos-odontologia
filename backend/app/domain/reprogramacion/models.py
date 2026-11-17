"""Conversación de reprogramación por WhatsApp (C-17 D1): espejo de la migración 016."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import TenantMixin


class ConversacionWA(Base, TenantMixin):
    """Una conversación abierta por (clínica, teléfono); ``opciones`` = huecos ofrecidos."""

    __tablename__ = "conversacion_wa"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id"], ["paciente.clinica_id", "paciente.id"],
            name="fk_conversacion_wa_paciente", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "turno_id"], ["turno.clinica_id", "turno.id"],
            name="fk_conversacion_wa_turno", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "turno_nuevo_id"], ["turno.clinica_id", "turno.id"],
            name="fk_conversacion_wa_turno_nuevo", ondelete="RESTRICT",
        ),
        CheckConstraint(
            "estado IN ('eligiendo','confirmando','ejecutando','cerrada')", name="estado_valido"
        ),
        CheckConstraint(
            "resultado IS NULL OR "
            "resultado IN ('reprogramado','sin_cambios','vencida','sin_opciones')",
            name="resultado_valido",
        ),
        CheckConstraint(
            "(estado = 'cerrada') = (resultado IS NOT NULL)", name="cerrada_con_resultado"
        ),
        CheckConstraint("jsonb_typeof(opciones) = 'array'", name="opciones_arreglo"),
    )  # fmt: skip

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    paciente_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telefono: Mapped[str] = mapped_column(Text, nullable=False)
    turno_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    estado: Mapped[str] = mapped_column(
        Text, nullable=False, default="eligiendo", server_default="eligiendo"
    )
    resultado: Mapped[str | None] = mapped_column(Text, nullable=True)
    opciones: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    elegido: Mapped[int | None] = mapped_column(Integer, nullable=True)
    turno_nuevo_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expira_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
