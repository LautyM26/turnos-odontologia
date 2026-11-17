"""Modelos de consentimientos (C-18): espejo de la migración 009.

Ambas tablas son append-only (triggers con ``fn_rechazar_mutacion()`` de la 004): solo
``TenantMixin``, sin ``AuditMixin``. Firmar = INSERT de la constancia; el estado se deriva.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.dialects.postgresql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import TenantMixin

_HEX64 = "^[0-9a-f]{64}$"


class Consentimiento(Base, TenantMixin):
    """Documento inmutable: el texto exacto que se mostró, su versión y su hash."""

    __tablename__ = "consentimiento"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id"],
            ["paciente.clinica_id", "paciente.id"],
            name="fk_consentimiento_paciente",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "autor_usuario_id"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_consentimiento_autor_usuario_id",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "clinica_id", "paciente_id", "id", name="uq_consentimiento_clinica_paciente_id"
        ),
        CheckConstraint(
            "tipo IN ('tratamiento_general','extraccion','endodoncia','implante','anestesia')",
            name="tipo_valido",
        ),
        CheckConstraint("length(btrim(texto)) > 0", name="texto_no_vacio"),
        CheckConstraint("length(btrim(texto_version)) > 0", name="version_no_vacia"),
        CheckConstraint(f"texto_hash ~ '{_HEX64}'", name="hash_formato"),
        Index(
            "ix_consentimiento_clinica_paciente_id", "clinica_id", "paciente_id", text("id DESC")
        ),
        Index("ix_consentimiento_clinica_paciente_tipo", "clinica_id", "paciente_id", "tipo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    paciente_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    texto_version: Mapped[str] = mapped_column(Text, nullable=False)
    texto_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    autor_usuario_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ConsentimientoFirma(Base, TenantMixin):
    """Constancia inmutable de la firma; el UNIQUE impide una segunda firma del documento."""

    __tablename__ = "consentimiento_firma"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id", "consentimiento_id"],
            ["consentimiento.clinica_id", "consentimiento.paciente_id", "consentimiento.id"],
            name="fk_consentimiento_firma_consentimiento",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "asistido_por_usuario_id"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_consentimiento_firma_asistido_por_usuario_id",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "clinica_id",
            "consentimiento_id",
            name="uq_consentimiento_firma_clinica_consentimiento",
        ),
        CheckConstraint(f"texto_hash ~ '{_HEX64}'", name="hash_formato"),
        CheckConstraint("length(btrim(firmante_nombre)) BETWEEN 1 AND 200", name="nombre_len"),
        CheckConstraint("firmante_dni ~ '^[0-9]{7,8}$'", name="dni_formato"),
        CheckConstraint("length(btrim(ip)) > 0", name="ip_no_vacia"),
        CheckConstraint("length(dispositivo) BETWEEN 1 AND 512", name="dispositivo_len"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    paciente_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    consentimiento_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    firmado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ip: Mapped[str] = mapped_column(Text, nullable=False)
    dispositivo: Mapped[str] = mapped_column(Text, nullable=False)
    texto_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    firmante_nombre: Mapped[str] = mapped_column(Text, nullable=False)
    firmante_dni: Mapped[str] = mapped_column(Text, nullable=False)
    asistido_por_usuario_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
