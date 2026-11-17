"""Modelos de WhatsApp (C-15, DD-10): espejo de la migración 014.

``PlantillaWA`` es catálogo global de la plataforma (sin ``clinica_id``, como ``rol``).
``WhatsappSesion`` y ``MensajeWhatsApp`` son datos del tenant (regla dura 10).
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Integer,
    Numeric,
    Text,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base
from app.infrastructure.persistence.mixins import TenantMixin

ESTADOS_SESION = ("desconocido", "iniciando", "escanear_qr", "activa", "caida", "detenida")
ESTADOS_MENSAJE = ("pendiente", "enviado", "entregado", "leido", "error", "recibido")
INTENCIONES = ("confirmar", "cancelar", "reprogramar", "desconocida")
MOTIVOS_ERROR = (
    "sin_telefono", "no_configurado", "sesion_no_activa", "gateway_no_disponible", "otro",
)  # fmt: skip
#: Motivos que se reintentan en corridas posteriores del job (D5).
MOTIVOS_TRANSITORIOS = ("no_configurado", "sesion_no_activa", "gateway_no_disponible", "otro")


def _en(valores: tuple[str, ...]) -> str:
    return "(" + ",".join(f"'{v}'" for v in valores) + ")"


class PlantillaWA(Base):
    """Texto base interno (sin aprobación de Meta, DD-10)."""

    __tablename__ = "plantilla_wa"

    clave: Mapped[str] = mapped_column(Text, primary_key=True)
    idioma: Mapped[str] = mapped_column(Text, nullable=False, server_default="es_AR")
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)


class WhatsappSesion(Base):
    """Una sesión QR (número dedicado) por clínica; ``nombre = 'clinica-<id>'`` (D2)."""

    __tablename__ = "whatsapp_sesion"
    __table_args__ = (
        CheckConstraint("nombre = 'clinica-' || clinica_id::text", name="nombre_coherente"),
        CheckConstraint(f"estado IN {_en(ESTADOS_SESION)}", name="estado_valido"),
    )

    clinica_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clinica.id", ondelete="RESTRICT"), primary_key=True
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    estado: Mapped[str] = mapped_column(
        Text, nullable=False, default="desconocido", server_default="desconocido"
    )
    numero: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


def nombre_sesion(clinica_id: int) -> str:
    return f"clinica-{clinica_id}"


class MensajeWhatsApp(Base, TenantMixin):
    """Mensaje saliente o entrante; mutable solo en entrega, intentos y bandeja (D3)."""

    __tablename__ = "mensaje_whatsapp"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinica_id", "turno_id"], ["turno.clinica_id", "turno.id"],
            name="fk_mensaje_whatsapp_turno", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "paciente_id"], ["paciente.clinica_id", "paciente.id"],
            name="fk_mensaje_whatsapp_paciente", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clinica_id", "resuelto_por"], ["usuario.clinica_id", "usuario.id"],
            name="fk_mensaje_whatsapp_resuelto_por", ondelete="RESTRICT",
        ),
        CheckConstraint("direccion IN ('saliente','entrante')", name="direccion_valida"),
        CheckConstraint(f"estado IN {_en(ESTADOS_MENSAJE)}", name="estado_valido"),
        CheckConstraint(
            "(direccion = 'entrante') = (estado = 'recibido')", name="estado_segun_direccion"
        ),
        CheckConstraint(
            f"intencion IS NULL OR intencion IN {_en(INTENCIONES)}", name="intencion_valida"
        ),
        CheckConstraint(
            "(direccion = 'entrante') = (intencion IS NOT NULL)", name="intencion_solo_entrante"
        ),
        CheckConstraint(
            f"motivo_error IS NULL OR motivo_error IN {_en(MOTIVOS_ERROR)}",
            name="motivo_error_valido",
        ),
        CheckConstraint("(estado = 'error') = (motivo_error IS NOT NULL)", name="error_con_motivo"),
        CheckConstraint("telefono IS NULL OR telefono ~ '^\\+[0-9]{8,15}$'", name="telefono_e164"),
        CheckConstraint(
            "telefono IS NOT NULL OR motivo_error IS NOT DISTINCT FROM 'sin_telefono'",
            name="telefono_requerido",
        ),
        CheckConstraint("texto IS NULL OR length(texto) <= 2000", name="texto_len"),
        CheckConstraint("intentos >= 0", name="intentos_no_negativos"),
        CheckConstraint("costo_ars >= 0", name="costo_no_negativo"),
        CheckConstraint("direccion = 'saliente' OR costo_ars = 0", name="entrante_sin_costo"),
        CheckConstraint(
            "(resuelto_at IS NULL) = (resuelto_por IS NULL)", name="resolucion_coherente"
        ),
    )  # fmt: skip

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    turno_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    paciente_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    plantilla: Mapped[str | None] = mapped_column(
        Text, ForeignKey("plantilla_wa.clave", ondelete="RESTRICT"), nullable=True
    )
    direccion: Mapped[str] = mapped_column(Text, nullable=False)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado: Mapped[str] = mapped_column(Text, nullable=False)
    intencion: Mapped[str | None] = mapped_column(Text, nullable=True)
    id_externo: Mapped[str | None] = mapped_column(Text, nullable=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    motivo_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    costo_ars: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    requiere_atencion: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    resuelto_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resuelto_por: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
