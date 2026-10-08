"""Modelos de pacientes, ficha versionada y adjuntos (C-08): espejo de la migración 004."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.dialects.postgresql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import AuditMixin, TenantMixin

TIPOS_ADJUNTO = ("foto", "pdf")
MIMES_ADJUNTO = ("image/jpeg", "image/png", "application/pdf")


class Paciente(Base, TenantMixin, AuditMixin):
    """Paciente de una clínica; no requiere cuenta de usuario (RN-AG-05)."""

    __tablename__ = "paciente"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "consentimiento_datos_por"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_paciente_consentimiento_datos_por",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("clinica_id", "id", name="uq_paciente_clinica_id"),
        UniqueConstraint("clinica_id", "dni", name="uq_paciente_clinica_dni"),
        CheckConstraint("length(nombre) BETWEEN 1 AND 100", name="nombre_len"),
        CheckConstraint("length(apellido) BETWEEN 1 AND 100", name="apellido_len"),
        CheckConstraint("dni ~ '^[0-9]{7,8}$'", name="dni_formato"),
        CheckConstraint("email IS NULL OR length(email) <= 320", name="email_len"),
        CheckConstraint("telefono IS NULL OR telefono ~ '^\\+[0-9]{8,15}$'", name="telefono_e164"),
        CheckConstraint("email IS NOT NULL OR telefono IS NOT NULL", name="contacto_requerido"),
        CheckConstraint(
            "obra_social_nombre IS NULL OR length(obra_social_nombre) <= 120", name="os_nombre_len"
        ),
        CheckConstraint(
            "obra_social_plan IS NULL OR length(obra_social_plan) <= 120", name="os_plan_len"
        ),
        CheckConstraint(
            "nro_afiliado IS NULL OR length(nro_afiliado) <= 50", name="nro_afiliado_len"
        ),
        CheckConstraint("riesgo_ausencia BETWEEN 0 AND 100", name="riesgo_rango"),
        CheckConstraint(
            "NOT consentimiento_datos OR consentimiento_datos_at IS NOT NULL",
            name="consentimiento_con_fecha",
        ),
        Index("ix_paciente_clinica_telefono", "clinica_id", "telefono"),
        Index("ix_paciente_clinica_email", "clinica_id", "email"),
        Index(
            "ix_paciente_nombre_busqueda_trgm",
            "nombre_busqueda",
            postgresql_using="gin",
            postgresql_ops={"nombre_busqueda": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    apellido: Mapped[str] = mapped_column(Text, nullable=False)
    dni: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    obra_social_nombre: Mapped[str | None] = mapped_column(Text, nullable=True)
    obra_social_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    nro_afiliado: Mapped[str | None] = mapped_column(Text, nullable=True)
    riesgo_ausencia: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0, server_default="0"
    )
    consentimiento_datos: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    consentimiento_datos_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consentimiento_datos_por: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    nombre_busqueda: Mapped[str] = mapped_column(Text, nullable=False)
    es_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class FichaVersion(Base, TenantMixin):
    """Versión inmutable de la ficha de anamnesis (append-only por trigger PG)."""

    __tablename__ = "ficha_version"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id"],
            ["paciente.clinica_id", "paciente.id"],
            name="fk_ficha_version_paciente",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "autor_usuario_id"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_ficha_version_autor_usuario_id",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("paciente_id", "version", name="uq_ficha_version_paciente_version"),
        CheckConstraint("version > 0", name="version_positiva"),
        CheckConstraint("anamnesis IS NULL OR length(anamnesis) <= 10000", name="anamnesis_len"),
        CheckConstraint("alergias IS NULL OR length(alergias) <= 10000", name="alergias_len"),
        CheckConstraint(
            "antecedentes IS NULL OR length(antecedentes) <= 10000", name="antecedentes_len"
        ),
        Index(
            "ix_ficha_version_clinica_paciente_version",
            "clinica_id",
            "paciente_id",
            text("version DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    paciente_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    anamnesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    alergias: Mapped[str | None] = mapped_column(Text, nullable=True)
    antecedentes: Mapped[str | None] = mapped_column(Text, nullable=True)
    autor_usuario_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Adjunto(Base, TenantMixin, AuditMixin):
    """Adjunto clínico (foto/PDF); el contenido vive en el storage, no en la DB."""

    __tablename__ = "adjunto"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id"],
            ["paciente.clinica_id", "paciente.id"],
            name="fk_adjunto_paciente",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "subido_por"],
            ["usuario.clinica_id", "usuario.id"],
            name="fk_adjunto_subido_por",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("storage_key", name="uq_adjunto_storage_key"),
        CheckConstraint("tipo IN ('foto','pdf')", name="tipo_valido"),
        CheckConstraint("mime IN ('image/jpeg','image/png','application/pdf')", name="mime_valido"),
        CheckConstraint("tamano_bytes > 0", name="tamano_positivo"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_formato"),
        CheckConstraint(
            "nombre_original IS NULL OR length(nombre_original) <= 255", name="nombre_len"
        ),
        Index(
            "ix_adjunto_clinica_paciente_created",
            "clinica_id",
            "paciente_id",
            text("created_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    paciente_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    evolucion_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(Text, nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    nombre_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    subido_por: Mapped[int] = mapped_column(BigInteger, nullable=False)
