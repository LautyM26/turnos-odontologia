"""Settings del gateway de WhatsApp (C-15 1.1, D10). Valores sintéticos, sin secretos reales."""

import pathlib
from decimal import Decimal

import pytest
from pydantic import ValidationError

VARS = (
    "WHATSAPP_GATEWAY",
    "WHATSAPP_GATEWAY_URL",
    "WHATSAPP_GATEWAY_API_KEY",
    "WHATSAPP_WEBHOOK_HMAC_KEY",
    "WHATSAPP_RECORDATORIO_HORAS",
    "WHATSAPP_MAX_INTENTOS",
    "WHATSAPP_ENVIOS_POR_MINUTO",
    "ARS_PRECIO_MENSAJE",
    "ENTORNO",
)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in VARS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-sintetico-32-chars-minimo-0000")


def test_arranca_sin_variables_whatsapp() -> None:
    from app.infrastructure.settings import Settings

    s = Settings()
    assert s.whatsapp_gateway == ""
    assert s.whatsapp_gateway_url == ""
    assert s.whatsapp_gateway_api_key is None
    assert s.whatsapp_webhook_hmac_key is None
    assert (s.whatsapp_recordatorio_horas, s.whatsapp_max_intentos) == (24, 3)
    assert s.whatsapp_envios_por_minuto == 20
    assert s.ars_precio_mensaje == Decimal("0.00")


def test_claves_vacias_en_dotenv_son_none(tmp_path: pathlib.Path) -> None:
    env = tmp_path / "sintetico.env"
    env.write_text(
        "WHATSAPP_GATEWAY_API_KEY=\nWHATSAPP_WEBHOOK_HMAC_KEY=  \nWHATSAPP_GATEWAY= WAHA \n"
    )
    from app.infrastructure.settings import Settings

    s = Settings(_env_file=env)  # type: ignore[call-arg]
    assert s.whatsapp_gateway_api_key is None
    assert s.whatsapp_webhook_hmac_key is None
    assert s.whatsapp_gateway == "waha"


def test_secretos_enmascarados(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHATSAPP_GATEWAY_API_KEY", "api-key-sintetica-123")
    monkeypatch.setenv("WHATSAPP_WEBHOOK_HMAC_KEY", "hmac-sintetica-456")
    from app.infrastructure.settings import Settings

    s = Settings()
    assert s.whatsapp_webhook_hmac_key is not None
    assert s.whatsapp_webhook_hmac_key.get_secret_value() == "hmac-sintetica-456"
    for texto in (repr(s), str(s), s.model_dump_json()):
        assert "api-key-sintetica-123" not in texto
        assert "hmac-sintetica-456" not in texto


def test_precio_decimal_exacto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARS_PRECIO_MENSAJE", "12.50")
    from app.infrastructure.settings import Settings

    precio = Settings().ars_precio_mensaje
    assert isinstance(precio, Decimal) and precio == Decimal("12.50")


@pytest.mark.parametrize(
    ("var", "valor"),
    [
        ("WHATSAPP_RECORDATORIO_HORAS", "0"),
        ("WHATSAPP_RECORDATORIO_HORAS", "73"),
        ("WHATSAPP_MAX_INTENTOS", "0"),
        ("WHATSAPP_MAX_INTENTOS", "11"),
        ("WHATSAPP_ENVIOS_POR_MINUTO", "0"),
        ("WHATSAPP_ENVIOS_POR_MINUTO", "61"),
        ("ARS_PRECIO_MENSAJE", "-1"),
        ("ARS_PRECIO_MENSAJE", "1.234"),
    ],
)
def test_fuera_de_rango_falla(monkeypatch: pytest.MonkeyPatch, var: str, valor: str) -> None:
    monkeypatch.setenv(var, valor)
    from app.infrastructure.settings import Settings

    with pytest.raises(ValidationError):
        Settings()
