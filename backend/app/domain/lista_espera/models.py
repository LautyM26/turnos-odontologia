"""Modelos de la lista de espera (C-16, RN-AG-06): espejo de la migración 015."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import TenantMixin

ESTADOS_ENTRADA = ("en_cola", "ofertado", "aceptado", "salido")
ESTADOS_ACTIVOS = ("en_cola", "ofertado")
ESTADOS_OFERTA = ("pendiente", "aceptada", "rechazada", "expirada", "anulada")


def _fk(tabla: str, col: str, ref: str, nombre: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["clinica_id", col], [f"{ref}.clinica_id", f"{ref}.id"], name=nombre, ondelete="RESTRICT"
    )


class ListaEspera(Base, TenantMixin):
    """Entrada de la cola: paciente que espera un hueco de una prestación."""

    __tablename__ = "lista_espera"
    __table_args__ = (
        _fk("lista_espera", "paciente_id", "paciente", "fk_lista_espera_paciente"),
        _fk("lista_espera", "prestacion_id", "prestacion", "fk_lista_espera_prestacion"),
        _fk("lista_espera", "profesional_id", "profesional", "fk_lista_espera_profesional"),
        _fk("lista_espera", "sillon_id", "sillon_recurso", "fk_lista_espera_sillon"),
        _fk("lista_espera", "turno_a_adelantar_id", "turno", "fk_lista_espera_turno_a_adelantar"),
        UniqueConstraint("clinica_id", "id", name="uq_lista_espera_clinica_id"),
        CheckConstraint(
            "estado IN ('en_cola','ofertado','aceptado','salido')", name="estado_valido"
        ),
        CheckConstraint("prioridad BETWEEN 0 AND 10", name="prioridad_rango"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    paciente_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prestacion_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    profesional_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sillon_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    turno_a_adelantar_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prioridad: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    estado: Mapped[str] = mapped_column(
        Text, nullable=False, default="en_cola", server_default="en_cola"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OfertaListaEspera(Base, TenantMixin):
    """Un hueco liberado ofrecido a una entrada; el hueco se copia (inmutable)."""

    __tablename__ = "oferta_lista_espera"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "lista_espera_id"], ["lista_espera.clinica_id", "lista_espera.id"],
            name="fk_oferta_lista_espera_entrada", ondelete="RESTRICT",
        ),
        _fk("oferta", "turno_liberado_id", "turno", "fk_oferta_lista_espera_turno_liberado"),
        _fk("oferta", "turno_creado_id", "turno", "fk_oferta_lista_espera_turno_creado"),
        CheckConstraint(
            "estado IN ('pendiente','aceptada','rechazada','expirada','anulada')",
            name="estado_valido",
        ),
        CheckConstraint("fin > inicio", name="fin_posterior"),
        CheckConstraint(
            "turno_creado_id IS NULL OR estado = 'aceptada'", name="turno_creado_solo_aceptada"
        ),
        UniqueConstraint(
            "clinica_id", "lista_espera_id", "turno_liberado_id", name="uq_oferta_hueco_por_entrada"
        ),
    )  # fmt: skip

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    lista_espera_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    turno_liberado_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    profesional_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sillon_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prestacion_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    estado: Mapped[str] = mapped_column(
        Text, nullable=False, default="pendiente", server_default="pendiente"
    )
    expira_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    respondida_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mensaje_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("mensaje_whatsapp.id", ondelete="RESTRICT"), nullable=True
    )
    turno_creado_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
