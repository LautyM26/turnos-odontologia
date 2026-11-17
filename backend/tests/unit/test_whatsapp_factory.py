"""Factory de mensajería WhatsApp (C-15 3.1, D1): nunca lanza, fake bloqueado en producción."""

import logging

import pytest

from app.infrastructure.settings import Settings
from app.infrastructure.whatsapp.factory import obtener_mensajeria
from app.infrastructure.whatsapp.fake import FakeMensajeria
from app.infrastructure.whatsapp.puerto import NoConfigurado, SesionNoActiva
from app.infrastructure.whatsapp.waha import WahaMensajeria

JWT = "test-sintetico-32-chars-minimo-0000"


def _s(**kw) -> Settings:  # type: ignore[no-untyped-def]
    return Settings(jwt_secret_key=JWT, _env_file=None, **kw)  # type: ignore[call-arg]


def test_vacio_no_configurado() -> None:
    assert isinstance(obtener_mensajeria(_s(whatsapp_gateway="")), NoConfigurado)


def test_fake_bloqueado_en_produccion(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        r = obtener_mensajeria(_s(whatsapp_gateway="fake", entorno="produccion"))
    assert isinstance(r, NoConfigurado)
    assert "produccion" in caplog.text.lower()


def test_fake_en_desarrollo() -> None:
    r = obtener_mensajeria(_s(whatsapp_gateway="fake", entorno="desarrollo"))
    assert isinstance(r, FakeMensajeria) and r.simulado


def test_waha_sin_url_no_configurado() -> None:
    assert isinstance(obtener_mensajeria(_s(whatsapp_gateway="waha")), NoConfigurado)


def test_waha_con_url() -> None:
    r = obtener_mensajeria(
        _s(whatsapp_gateway="waha", whatsapp_gateway_url="http://gw.invalid:3000",
           whatsapp_gateway_api_key="k-sintetica")
    )  # fmt: skip
    assert isinstance(r, WahaMensajeria) and not r.simulado


def test_valor_desconocido_no_configurado(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        r = obtener_mensajeria(_s(whatsapp_gateway="telegram"))
    assert isinstance(r, NoConfigurado) and "telegram" in r.mensaje


def test_fake_registra_envios_y_respeta_estado() -> None:
    fake = FakeMensajeria()
    id1 = fake.enviar_texto("clinica-1", "+5491100000001", "hola")
    id2 = fake.enviar_texto("clinica-1", "+5491100000001", "hola")
    assert id1 != id2 and id1.startswith("FAKE-")
    assert fake.enviados == [("clinica-1", "+5491100000001", "hola")] * 2
    fake.estado_sesion = "caida"
    with pytest.raises(SesionNoActiva):
        fake.enviar_texto("clinica-1", "+5491100000001", "hola")
    assert fake.qr("clinica-1") is None
    fake.estado_sesion = "escanear_qr"
    assert fake.qr("clinica-1")
