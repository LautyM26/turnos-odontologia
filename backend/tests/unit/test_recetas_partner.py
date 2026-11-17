"""Puerto del partner de recetas, FakePartner y factory (C-19 1.3-1.4). Sin red ni DB."""

import logging
from uuid import UUID, uuid4

import pytest

from app.infrastructure.recetas.partner_client import (
    NoConfigurado,
    PartnerNoDisponible,
    PartnerRechazo,
    SolicitudPartner,
)


def _solicitud(clave: UUID | None = None, tipo: str = "receta") -> SolicitudPartner:
    return SolicitudPartner(
        tipo=tipo,
        clave_idempotencia=clave or uuid4(),
        paciente_nombre="Paciente",
        paciente_apellido="Sintetico",
        paciente_dni="90000001",
        obra_social_nombre=None,
        obra_social_plan=None,
        nro_afiliado=None,
        profesional_nombre="Profesional Sintetico",
        profesional_matricula="MP-0001",
        diagnostico="Control sintetico",
        items=({"nombre_generico": "ibuprofeno"},),
    )


def test_fake_id_determinista_por_clave() -> None:
    from app.infrastructure.recetas.fake import FakePartner

    fake, clave = FakePartner(), uuid4()
    a, b = fake.emitir(_solicitud(clave)), fake.emitir(_solicitud(clave))
    assert a.id_externo == b.id_externo and a.id_externo.startswith("FAKE-")
    assert fake.emitir(_solicitud()).id_externo != a.id_externo


def test_fake_pdf_url_invalid_y_marcas() -> None:
    from app.infrastructure.recetas.fake import FakePartner

    fake = FakePartner()
    e = fake.emitir(_solicitud())
    assert e.pdf_url == f"https://partner-simulado.invalid/recetas/{e.id_externo}.pdf"
    assert fake.simulado is True and fake.nombre == "fake"


def test_fake_registra_solicitudes() -> None:
    from app.infrastructure.recetas.fake import FakePartner

    fake, s = FakePartner(), _solicitud()
    fake.emitir(s)
    assert fake.solicitudes == [s]


@pytest.mark.parametrize("error", [PartnerNoDisponible("caido"), PartnerRechazo("motivo")])
def test_fake_propaga_errores_pedidos_y_no_registra(error: Exception) -> None:
    from app.infrastructure.recetas.fake import FakePartner

    fake = FakePartner()
    fake.fallar_con(error)
    with pytest.raises(type(error)):
        fake.emitir(_solicitud())
    assert fake.solicitudes == []
    fake.fallar_con(None)
    assert fake.emitir(_solicitud()).id_externo.startswith("FAKE-")


# --- factory --------------------------------------------------------------------------------


def _settings(partner: str, entorno: str):  # type: ignore[no-untyped-def]
    from app.infrastructure.settings import Settings

    return Settings(
        jwt_secret_key="test-sintetico-32-chars-minimo-0000",
        recetas_partner=partner,
        entorno=entorno,
        _env_file=None,
    )  # type: ignore[call-arg]


def test_factory_vacio_no_configurado_nombra_variable() -> None:
    from app.infrastructure.recetas.factory import obtener_partner

    r = obtener_partner(_settings("", "desarrollo"))
    assert isinstance(r, NoConfigurado) and "RECETAS_PARTNER" in r.mensaje


@pytest.mark.parametrize("entorno", ["desarrollo", "test", "demo"])
def test_factory_fake_fuera_de_produccion(entorno: str) -> None:
    from app.infrastructure.recetas.factory import obtener_partner
    from app.infrastructure.recetas.fake import FakePartner

    assert isinstance(obtener_partner(_settings("fake", entorno)), FakePartner)


def test_factory_fake_es_singleton_por_proceso() -> None:
    from app.infrastructure.recetas.factory import obtener_partner

    s = _settings("fake", "test")
    assert obtener_partner(s) is obtener_partner(s)


def test_factory_fake_en_produccion_bloqueado_con_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.infrastructure.recetas.factory import obtener_partner

    with caplog.at_level(logging.WARNING):
        r = obtener_partner(_settings("fake", "produccion"))
    assert isinstance(r, NoConfigurado) and "deshabilitado en producción" in r.mensaje
    assert any(rec.levelno == logging.WARNING for rec in caplog.records)


def test_factory_desconocido_no_configurado_con_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.infrastructure.recetas.factory import obtener_partner

    with caplog.at_level(logging.WARNING):
        r = obtener_partner(_settings("farmalink", "desarrollo"))
    assert isinstance(r, NoConfigurado)
    assert any(rec.levelno == logging.WARNING for rec in caplog.records)
