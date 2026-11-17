"""Settings tests (TDD RED first). Synthetic values only, no secrets."""

import pathlib

import pytest
from pydantic import ValidationError


def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "DATABASE_URL",
        "APP_BASE_URL",
        "RESERVA_PREBLOQUEO_MIN",
        "AGENDA_PASO_MIN",
        "JWT_SECRET_KEY",
        "JWT_ALGORITHM",
        "JWT_ACCESS_MIN",
        "JWT_REFRESH_DAYS",
        "COOKIE_SECURE",
        "RATE_LIMIT_LOGIN",
        "RATE_LIMIT_PUBLICO_LECTURA",
        "RATE_LIMIT_PUBLICO_RESERVA",
        "ADJUNTOS_STORAGE_DIR",
        "ADJUNTO_MAX_BYTES",
        "RECETAS_PARTNER",
        "RECETAS_PARTNER_KEY",
        "ENTORNO",
    ):
        monkeypatch.delenv(key, raising=False)
    # Secreto sintético por defecto (32+ chars); los tests de boot-falla lo borran.
    monkeypatch.setenv("JWT_SECRET_KEY", "test-sintetico-32-chars-minimo-0000")


def test_settings_loads_with_minimal_dev_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/testdb")
    from app.infrastructure.settings import Settings

    settings = Settings()
    assert settings.database_url.startswith("postgresql")
    assert settings.app_base_url != ""
    assert settings.reserva_prebloqueo_min == 15
    assert settings.agenda_paso_min == 15


def test_settings_respects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/testdb")
    monkeypatch.setenv("RESERVA_PREBLOQUEO_MIN", "20")
    from app.infrastructure.settings import Settings

    settings = Settings()
    assert settings.reserva_prebloqueo_min == 20


def test_settings_forbids_undeclared_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/testdb")
    from app.infrastructure.settings import Settings

    with pytest.raises(ValidationError):
        Settings(campo_no_declarado="valor-sintetico")  # type: ignore[call-arg]


def test_settings_has_no_hardcoded_secrets() -> None:
    from app.infrastructure import settings as settings_module

    source = pathlib.Path(settings_module.__file__).read_text(encoding="utf-8")
    for marker in ("APP_USR-", "EAAB", "whsec_", "-----BEGIN"):
        assert marker not in source
    assert "changeme" in source or "localhost" in source


def test_settings_boot_falla_sin_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """C-03 D9: JWT_SECRET_KEY requerida sin default (boot falla en claro)."""
    _clean_env(monkeypatch)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/testdb")
    from app.infrastructure.settings import Settings

    with pytest.raises(ValidationError, match="jwt_secret_key"):
        Settings()


def test_settings_jwt_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """C-03 D9: defaults HS256 / 15min / 7d / secure / 5-60s."""
    _clean_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/testdb")
    from app.infrastructure.settings import Settings

    settings = Settings()
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_access_min == 15
    assert settings.jwt_refresh_days == 7
    assert settings.cookie_secure is True
    assert settings.rate_limit_login == "5/60s"


def test_settings_rechaza_secreto_corto(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET_KEY", "corto")
    from app.infrastructure.settings import Settings

    with pytest.raises(ValidationError):
        Settings()


def test_settings_adjuntos_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """C-08 1.2: storage local y tope de 10 MiB por defecto."""
    _clean_env(monkeypatch)
    from pathlib import Path

    from app.infrastructure.settings import Settings

    settings = Settings()
    assert settings.adjuntos_storage_dir == Path("./var/adjuntos")
    assert settings.adjunto_max_bytes == 10485760


def test_settings_adjuntos_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("ADJUNTO_MAX_BYTES", "2048")
    monkeypatch.setenv("ADJUNTOS_STORAGE_DIR", "/tmp/sintetico-adjuntos")
    from app.infrastructure.settings import Settings

    settings = Settings()
    assert settings.adjunto_max_bytes == 2048
    assert str(settings.adjuntos_storage_dir).endswith("sintetico-adjuntos")


@pytest.mark.parametrize("valor", ["0", str(30 * 1024 * 1024)])
def test_settings_adjunto_max_bytes_fuera_de_rango(
    monkeypatch: pytest.MonkeyPatch, valor: str
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("ADJUNTO_MAX_BYTES", valor)
    from app.infrastructure.settings import Settings

    with pytest.raises(ValidationError):
        Settings()


# --- C-19 1.1: configuración del partner de recetas (D2) ------------------------------------


def test_settings_recetas_defaults_seguros(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    from app.infrastructure.settings import Settings

    settings = Settings()
    assert settings.recetas_partner == ""
    assert settings.recetas_partner_key is None
    assert settings.entorno == "produccion"


def test_settings_recetas_key_vacia_en_dotenv_es_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    _clean_env(monkeypatch)
    env = tmp_path / "sintetico.env"
    env.write_text("\n".join(["RECETAS_PARTNER_KEY=", "RECETAS_PARTNER=", "ENTORNO=desarrollo"]))
    from app.infrastructure.settings import Settings

    settings = Settings(_env_file=env)  # type: ignore[call-arg]
    assert settings.recetas_partner_key is None
    assert settings.entorno == "desarrollo"


def test_settings_recetas_key_con_valor_no_aparece_en_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("RECETAS_PARTNER_KEY", "clave-sintetica-no-real-123")
    from app.infrastructure.settings import Settings

    settings = Settings()
    assert settings.recetas_partner_key is not None
    assert settings.recetas_partner_key.get_secret_value() == "clave-sintetica-no-real-123"
    assert "clave-sintetica-no-real-123" not in repr(settings)
    assert "clave-sintetica-no-real-123" not in str(settings)


def test_settings_recetas_partner_se_normaliza(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("RECETAS_PARTNER", "  FAKE ")
    from app.infrastructure.settings import Settings

    assert Settings().recetas_partner == "fake"


def test_settings_entorno_invalido_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("ENTORNO", "staging")
    from app.infrastructure.settings import Settings

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("entorno", ["desarrollo", "test", "demo", "produccion"])
def test_settings_entorno_valores_permitidos(
    monkeypatch: pytest.MonkeyPatch, entorno: str
) -> None:
    _clean_env(monkeypatch)
    monkeypatch.setenv("ENTORNO", entorno)
    from app.infrastructure.settings import Settings

    assert Settings().entorno == entorno


@pytest.mark.parametrize("valor", ["4", "61", "abc"])
def test_agenda_paso_min_fuera_de_rango_falla(monkeypatch: pytest.MonkeyPatch, valor: str) -> None:
    """C-05c D1: paso de huecos configurable entre 5 y 60 minutos."""
    _clean_env(monkeypatch)
    monkeypatch.setenv("AGENDA_PASO_MIN", valor)
    from app.infrastructure.settings import Settings

    with pytest.raises(ValidationError):
        Settings()
