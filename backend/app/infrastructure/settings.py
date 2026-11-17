"""Application settings loaded from environment (12 vars documented in .env.example)."""

from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process configuration. No secrets hardcoded; only placeholders in repo."""

    model_config = SettingsConfigDict(extra="forbid", env_file=".env", case_sensitive=False)

    database_url: str = Field(
        default="postgresql+psycopg://changeme:changeme@localhost:5432/turnos",
        description="Conexión PostgreSQL (sensible, solo env). Default local sintético.",
    )
    app_base_url: str = Field(
        default="http://localhost:8000",
        description="URL pública para enlaces de reserva/comprobantes.",
    )
    reserva_prebloqueo_min: int = Field(
        default=15,
        ge=1,
        le=120,
        description="Expiración del pre-bloqueo de horario sin pago (SU-04).",
    )
    agenda_paso_min: int = Field(
        default=15,
        ge=5,
        le=60,
        description="Paso en minutos entre inicios candidatos de huecos (C-05c D1).",
    )
    # --- Auth JWT (C-03, D9). Secreto requerido sin default: boot falla sin él. ---
    jwt_secret_key: str = Field(
        description="Secreto HS256 256-bit, solo env backend. Sin default.",
        min_length=32,
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="Algoritmo JWT (solo HS256 en MVP).",
    )
    jwt_access_min: int = Field(
        default=15,
        ge=1,
        le=60,
        description="Vida del access token en minutos.",
    )
    jwt_refresh_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Vida del refresh token en días.",
    )
    cookie_secure: bool = Field(
        default=True,
        description="Cookie refresh con flag Secure (false solo dev http local).",
    )
    rate_limit_login: str = Field(
        default="5/60s",
        description="Ventana de rate-limit login (formato N/Vs).",
    )
    # --- Reserva pública (C-06 D5): límites por IP en formato slowapi ("N/minute"). ---
    rate_limit_publico_lectura: str = Field(
        default="60/minute",
        description="Catálogo, huecos y consulta de reserva públicos, por IP.",
    )
    rate_limit_publico_reserva: str = Field(
        default="5/minute",
        description="Reservar y cancelar por enlace, por IP.",
    )
    # --- Adjuntos clínicos (C-08, D9/D14). ---
    adjuntos_storage_dir: Path = Field(
        default=Path("./var/adjuntos"),
        description="Directorio local de adjuntos (fuera de cualquier static mount).",
    )
    adjunto_max_bytes: int = Field(
        default=10485760,
        ge=1,
        le=26214400,
        description="Tamaño máximo de un adjunto en bytes (default 10 MiB, tope 25 MiB).",
    )
    # --- Recetas vía partner ReNaPDiS (C-19, D2). Nada de esto puede impedir el boot. ---
    recetas_partner: str = Field(
        default="",
        description="Partner de recetas: vacío = no configurado (501); 'fake' fuera de producción.",
    )
    recetas_partner_key: SecretStr | None = Field(
        default=None,
        description="Credencial del partner (solo env backend, enmascarada). Vacía = None.",
    )
    entorno: Literal["desarrollo", "test", "demo", "produccion"] = Field(
        default="produccion",
        description="Entorno de ejecución; default seguro: el partner simulado queda bloqueado.",
    )
    # --- WhatsApp por sesión QR vía gateway (C-15, D10, DD-10). Nada impide el boot. ---
    whatsapp_gateway: str = Field(
        default="",
        description="Gateway QR: vacío = no configurado (501); 'fake' fuera de producción; 'waha'.",
    )
    whatsapp_gateway_url: str = Field(default="", description="URL base del gateway (WAHA).")
    whatsapp_gateway_api_key: SecretStr | None = Field(
        default=None, description="X-Api-Key del gateway (solo env backend). Vacía = None."
    )
    whatsapp_webhook_hmac_key: SecretStr | None = Field(
        default=None, description="Secreto HMAC-SHA512 de los eventos del gateway. Vacío = None."
    )
    whatsapp_recordatorio_horas: int = Field(
        default=24, ge=1, le=72, description="Ventana del recordatorio previo al turno (SU-04)."
    )
    whatsapp_max_intentos: int = Field(
        default=3, ge=1, le=10, description="Intentos máximos de envío de un recordatorio."
    )
    whatsapp_envios_por_minuto: int = Field(
        default=20, ge=1, le=60, description="Ritmo máximo de envío por sesión (riesgo de bloqueo)."
    )
    ars_precio_mensaje: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Costo interno por mensaje saliente en ARS (RN-WA-02, NUMERIC).",
    )

    # --- Lista de espera (C-16, D10, SU-04). ---
    lista_espera_oferta_min: int = Field(
        default=30, ge=5, le=240, description="Minutos que tiene el paciente para aceptar."
    )
    lista_espera_anticipacion_min: int = Field(
        default=120, ge=0, le=1440, description="Anticipación mínima de un hueco ofrecible."
    )

    @field_validator("recetas_partner", "whatsapp_gateway", mode="before")
    @classmethod
    def _normalizar_partner(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator(
        "recetas_partner_key", "whatsapp_gateway_api_key", "whatsapp_webhook_hmac_key",
        mode="before",
    )  # fmt: skip
    @classmethod
    def _clave_vacia_es_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value


def get_settings() -> Settings:
    """Return a fresh Settings instance from the current environment."""
    return Settings()
