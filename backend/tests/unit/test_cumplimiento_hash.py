"""Hash SHA-256 del texto exacto de un consentimiento (C-18 1.1)."""

import re

import pytest

from app.domain.cumplimiento.hashing import sha256_hex


def test_hash_de_texto_conocido() -> None:
    # Vector de referencia estándar (FIPS 180-2), independiente de la implementación.
    assert sha256_hex("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_texto_vacio_tiene_hash_conocido() -> None:
    assert sha256_hex("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


@pytest.mark.parametrize(
    ("a", "b"),
    [("Consiento.", "Consiento. "), ("extracción", "extraccion"), ("A b", "A  b")],
)
def test_espacios_y_acentos_cuentan(a: str, b: str) -> None:
    assert sha256_hex(a) != sha256_hex(b)


def test_es_hex_de_64_caracteres_en_minuscula() -> None:
    h = sha256_hex("Texto sintético con ñ y tilde")
    assert re.fullmatch(r"[0-9a-f]{64}", h)
