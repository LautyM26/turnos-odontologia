"""Application settings loaded from environment (12 vars documented in .env.example)."""

from pathlib import Path

from pydantic import Field
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


def get_settings() -> Settings:
    """Return a fresh Settings instance from the current environment."""
    return Settings()
