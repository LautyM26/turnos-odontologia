"""Schemas de consentimientos y regla pura de firma completa (C-18 1.3, 1.4)."""

import pytest
from pydantic import ValidationError

from app.domain.cumplimiento.schemas import ConsentimientoIn, FirmaIn
from app.domain.cumplimiento.servicios import faltantes_firma

HASH = "a" * 64


def test_consentimiento_in_acepta_tipo_del_catalogo() -> None:
    assert ConsentimientoIn(tipo="extraccion").tipo == "extraccion"


@pytest.mark.parametrize("tipo", ["inexistente", "", "EXTRACCION"])
def test_tipo_fuera_del_catalogo_rechazado(tipo: str) -> None:
    with pytest.raises(ValidationError):
        ConsentimientoIn(tipo=tipo)


@pytest.mark.parametrize("extra", ["texto", "texto_hash", "fecha", "autor_usuario_id"])
def test_consentimiento_in_rechaza_campos_de_servidor(extra: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        ConsentimientoIn(tipo="extraccion", **{extra: "x"})


def test_firma_in_acepta_campos_de_completitud_ausentes() -> None:
    f = FirmaIn(texto_hash=HASH)
    assert (f.acepta, f.firmante_nombre, f.firmante_dni) == (None, None, None)


@pytest.mark.parametrize("extra", ["ip", "fecha", "dispositivo"])
def test_firma_in_rechaza_ip_fecha_dispositivo(extra: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        FirmaIn(texto_hash=HASH, **{extra: "x"})


@pytest.mark.parametrize("h", ["", "abc", "A" * 64, "g" * 64, "a" * 63, "a" * 65])
def test_firma_in_rechaza_hash_que_no_es_hex_de_64(h: str) -> None:
    with pytest.raises(ValidationError):
        FirmaIn(texto_hash=h)


def _firma(**over):  # type: ignore[no-untyped-def]
    base = {"acepta": True, "firmante_nombre": "Firmante Sintetico", "firmante_dni": "90000001",
            "texto_hash": HASH}  # fmt: skip
    base.update(over)
    return FirmaIn(**base)


@pytest.mark.parametrize("acepta", [False, None])
def test_faltantes_sin_aceptacion(acepta) -> None:  # type: ignore[no-untyped-def]
    assert faltantes_firma(_firma(acepta=acepta)) == ["acepta"]


@pytest.mark.parametrize("dni", ["123456", "123456789", "12.345.678", "abcdefgh", None])
def test_faltantes_dni_invalido(dni) -> None:  # type: ignore[no-untyped-def]
    assert faltantes_firma(_firma(firmante_dni=dni)) == ["firmante_dni"]


@pytest.mark.parametrize("nombre", ["", "   ", None])
def test_faltantes_nombre_vacio(nombre) -> None:  # type: ignore[no-untyped-def]
    assert faltantes_firma(_firma(firmante_nombre=nombre)) == ["firmante_nombre"]


def test_faltantes_completa_y_multiples() -> None:
    assert faltantes_firma(_firma()) == []
    assert faltantes_firma(_firma(firmante_dni="1234567")) == []
    assert faltantes_firma(_firma(acepta=False, firmante_nombre="", firmante_dni="1")) == [
        "acepta", "firmante_nombre", "firmante_dni",
    ]  # fmt: skip
