"""Errores de dominio de recetas y saneo del motivo del partner (C-19 1.6)."""

import pytest

from app.domain.pacientes.servicios import PacienteError
from app.domain.recetas import errores


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (errores.PartnerNoConfigurado("Configurá RECETAS_PARTNER"), 501),
        (errores.PartnerCaido(), 502),
        (errores.PartnerRechazoError("motivo"), 422),
        (errores.EvolucionNoValidaParaReceta(), 422),
        (errores.ClaveIdempotenciaReutilizada(), 409),
        (errores.RecetaNoEncontrada(), 404),
    ],
)
def test_status_y_herencia(error: PacienteError, status: int) -> None:
    assert isinstance(error, PacienteError) and error.status_code == status and error.detail


def test_partner_caido_es_reintentable() -> None:
    assert errores.PartnerCaido().extra["reintentable"] is True


def test_no_configurado_conserva_mensaje() -> None:
    assert errores.PartnerNoConfigurado("Configurá RECETAS_PARTNER").detail.startswith("Configurá")


def test_evolucion_propia_mensaje() -> None:
    assert "propia" in errores.EvolucionNoValidaParaReceta(ajena=True).detail


def test_sanear_enmascara_credencial() -> None:
    out = errores.sanear_motivo("fallo con clave-sintetica-xyz en header", "clave-sintetica-xyz")
    assert "clave-sintetica-xyz" not in out and "***" in out


def test_sanear_sin_credencial_y_trunca_a_300() -> None:
    assert errores.sanear_motivo("hola", None) == "hola"
    assert len(errores.sanear_motivo("a" * 1000, "k")) == 300


def test_sanear_credencial_vacia_no_rompe() -> None:
    assert errores.sanear_motivo("hola", "") == "hola"
