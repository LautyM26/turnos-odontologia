"""Settings tests (TDD RED first). Synthetic values only, no secrets."""

import pathlib

import pytest
from pydantic import ValidationError


def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "DATABASE_URL",
        "APP_BASE_URL",
        "RESERVA_PREBLOQUEO_MIN",
        "JWT_SECRET_KEY",
        "JWT_ALGORITHM",
        "JWT_ACCESS_MIN",
        "JWT_REFRESH_DAYS",
        "COOKIE_SECURE",
        "RATE_LIMIT_LOGIN",
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
