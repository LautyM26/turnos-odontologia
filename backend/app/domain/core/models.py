"""Entidades base del SaaS: Clinica, Rol, Usuario, UsuarioRol (C-02, D3/D4)."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy import Numeric as NumericType
from sqlalchemy.dialects.postgresql import CHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import AuditMixin, TenantMixin

ROL_CLAVES = ("admin", "odontologo", "recepcionista", "paciente-enlace")


class Clinica(Base, AuditMixin):
    """Tenant raíz. Única tabla no-scoped (sin TenantMixin)."""

    __tablename__ = "clinica"
    __table_args__ = (
        CheckConstraint(
            "length(nombre) > 0 AND length(nombre) <= 200", name="nombre_len"
        ),
        CheckConstraint("cuit ~ '^[0-9]{11}$'", name="cuit_formato"),
        CheckConstraint("moneda = 'ARS'", name="moneda_ars"),
        Index("ix_clinica_activa", "id", postgresql_where=text("is_active")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    cuit: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email_contacto: Mapped[str | None] = mapped_column(Text, nullable=True)
    moneda: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default="ARS")
    sena_porcentaje: Mapped[float | None] = mapped_column(NumericType(5, 2), nullable=True)
    sena_monto_minimo: Mapped[float | None] = mapped_column(NumericType(12, 2), nullable=True)
    sena_obligatoria: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    es_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="clinica")


class Rol(Base, AuditMixin):
    """Catálogo global de roles (no tenant-scoped, clave estable única)."""

    __tablename__ = "rol"
    __table_args__ = (
        CheckConstraint(
            "length(clave) > 0 AND length(clave) <= 50", name="clave_len"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    clave: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)


class Usuario(Base, TenantMixin, AuditMixin):
    """Identidad scoped por clínica. Email único por tenant (índice expresión en 001)."""

    __tablename__ = "usuario"
    __table_args__ = (
        CheckConstraint(
            "length(email) > 0 AND length(email) <= 320", name="email_len"
        ),
        Index("ix_usuario_clinica_activo", "clinica_id", "is_active"),
        Index("ix_usuario_activos", "clinica_id", postgresql_where=text("is_active")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    nombre: Mapped[str | None] = mapped_column(Text, nullable=True)

    clinica: Mapped[Clinica] = relationship(back_populates="usuarios")
    roles: Mapped[list["UsuarioRol"]] = relationship(back_populates="usuario")


class UsuarioRol(Base, TenantMixin, AuditMixin):
    """Join N—M usuario↔rol. PK compuesta + tenant denormalizado (regla dura 10)."""

    __tablename__ = "usuario_rol"

    usuario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuario.id", ondelete="restrict"), primary_key=True
    )
    rol_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("rol.id", ondelete="restrict"), primary_key=True
    )
    asignado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    usuario: Mapped[Usuario] = relationship(back_populates="roles")
    rol: Mapped[Rol] = relationship()


Index(
    "uq_usuario_clinica_email",
    Usuario.clinica_id,
    func.lower(Usuario.email),
    unique=True,
)
Index("ix_usuario_rol_rol", UsuarioRol.rol_id)
Index("ix_usuario_rol_clinica", UsuarioRol.clinica_id, UsuarioRol.usuario_id)
