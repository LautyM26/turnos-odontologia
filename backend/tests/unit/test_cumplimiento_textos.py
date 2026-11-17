"""Catálogo de textos de consentimiento versionados (C-18 1.2)."""

import re

import pytest

from app.domain.cumplimiento.hashing import sha256_hex
from app.domain.cumplimiento.textos import AVISO, CATALOGO, TIPOS

TIPOS_ESPERADOS = {"tratamiento_general", "extraccion", "endodoncia", "implante", "anestesia"}

# Snapshot tipo -> (version, hash). Si cambia un texto hay que subir su versión y este valor.
SNAPSHOT: dict[str, tuple[str, str]] = {
    "tratamiento_general": (
        "1.0", "0b57cbc45ad7f2330d09269f487446877153899077f5edd1c3816f2be6a7c4b5"
    ),
    "extraccion": ("1.0", "c30654541479ced10ca47912aa7085f72e2c797513bbe548fcafd90b17b9d118"),
    "endodoncia": ("1.0", "ff5abd7f8560fff6ef774bdc40a6c1c4921a104a198934e73a2c20086c91d6cf"),
    "implante": ("1.0", "53ab499b8cc8bfee2a14bb4386a60281e92fee02ebe9738c745ec61c433e8a6c"),
    "anestesia": ("1.0", "bdc1589cfe6d3393dffb3f0849ac22ed6e6bbcdf5fdae1ba83a648dc2defe2b6"),
}  # fmt: skip


def test_catalogo_tiene_exactamente_los_cinco_tipos() -> None:
    assert set(TIPOS) == TIPOS_ESPERADOS
    assert set(CATALOGO) == TIPOS_ESPERADOS


@pytest.mark.parametrize("tipo", sorted(TIPOS_ESPERADOS))
def test_cada_texto_empieza_con_el_aviso_legal(tipo: str) -> None:
    version, texto = CATALOGO[tipo]
    assert AVISO == "Texto base a validar con asesoría legal"
    assert texto.startswith(AVISO)
    assert re.fullmatch(r"\d+\.\d+", version)


@pytest.mark.parametrize("tipo", sorted(TIPOS_ESPERADOS))
def test_textos_sin_numeros_tipo_dni_ni_telefonos(tipo: str) -> None:
    texto = CATALOGO[tipo][1]
    assert not re.search(r"\d{7,}", texto)
    assert not re.search(r"\+\d", texto)
    assert "[A completar" in texto


def test_textos_distintos_entre_tipos() -> None:
    assert len({texto for _, texto in CATALOGO.values()}) == len(CATALOGO)


def test_snapshot_obliga_a_subir_la_version_si_cambia_el_texto() -> None:
    actual = {t: (v, sha256_hex(x)) for t, (v, x) in CATALOGO.items()}
    assert actual == SNAPSHOT
