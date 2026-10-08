"""Detección de tipo por firma de bytes y saneo de nombres (C-08 8.1). Bytes sintéticos."""

import pytest

from app.domain.pacientes.archivos import (
    TipoNoPermitido,
    detectar_tipo,
    sanear_nombre,
)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
PDF = b"%PDF-1.4\n" + b"\x00" * 16


@pytest.mark.parametrize(
    ("datos", "esperado"),
    [
        (JPEG, ("foto", "image/jpeg")),
        (PNG, ("foto", "image/png")),
        (PDF, ("pdf", "application/pdf")),
    ],
)
def test_firmas_permitidas(datos: bytes, esperado: tuple[str, str]) -> None:
    assert detectar_tipo(datos) == esperado


@pytest.mark.parametrize(
    "datos",
    [
        b"GIF89a" + b"\x00" * 16,
        b"PK\x03\x04" + b"\x00" * 16,  # ZIP / DOCX
        b"MZ\x90\x00" + b"\x00" * 16,  # ejecutable
        b"\x00" * 128 + b"DICM",  # DICOM
        b"",
        b"\x89PNG",  # firma PNG truncada
    ],
)
def test_firmas_rechazadas(datos: bytes) -> None:
    with pytest.raises(TipoNoPermitido):
        detectar_tipo(datos)


def test_content_type_declarado_debe_coincidir() -> None:
    assert detectar_tipo(PDF, "application/pdf") == ("pdf", "application/pdf")
    assert detectar_tipo(PDF, "Application/PDF; charset=binary")[0] == "pdf"
    with pytest.raises(TipoNoPermitido):
        detectar_tipo(PDF, "image/png")
    with pytest.raises(TipoNoPermitido):
        detectar_tipo(b"MZ\x90\x00" + b"\x00" * 16, "application/pdf")


@pytest.mark.parametrize(
    ("crudo", "esperado"),
    [
        ("../../etc/passwd.png", "passwd.png"),
        ("C:\\Windows\\sys.pdf", "sys.pdf"),
        ("rad\x00io\ngrafia.pdf", "radiografia.pdf"),
        ("a" * 400 + ".png", None),
        ("", None),
    ],
)
def test_sanear_nombre(crudo: str, esperado: str | None) -> None:
    resultado = sanear_nombre(crudo)
    if esperado is None:
        assert resultado is None or len(resultado) <= 255
        if crudo == "":
            assert resultado is None
    else:
        assert resultado == esperado
