"""Catálogos FDI y de estados del odontograma (C-09, RN-CL-03). Dominio puro, sin DB."""

import pytest

from app.domain.clinica import fdi


def test_conteos_de_piezas() -> None:
    assert len(fdi.PERMANENTES) == 32
    assert len(fdi.TEMPORALES) == 20
    assert len(fdi.piezas_validas("mixta")) == 52
    assert fdi.piezas_validas("permanente") == fdi.PERMANENTES
    assert fdi.piezas_validas("temporal") == fdi.TEMPORALES
    assert not (fdi.PERMANENTES & fdi.TEMPORALES)


@pytest.mark.parametrize("pieza", [11, 18, 48, 51, 85])
def test_bordes_validos(pieza: int) -> None:
    assert fdi.es_pieza_fdi(pieza)
    assert pieza in fdi.piezas_validas("mixta")


@pytest.mark.parametrize("pieza", [10, 19, 49, 56, 86, 90, 0, -11, 111])
def test_bordes_invalidos(pieza: int) -> None:
    assert not fdi.es_pieza_fdi(pieza)
    assert pieza not in fdi.piezas_validas("mixta")


def test_temporal_no_es_permanente_y_viceversa() -> None:
    assert 55 not in fdi.piezas_validas("permanente")
    assert 16 not in fdi.piezas_validas("temporal")


def test_denticion_desconocida_falla() -> None:
    with pytest.raises(ValueError):
        fdi.piezas_validas("lactante")


def test_catalogos_de_estados_dc3() -> None:
    assert fdi.ESTADOS_PIEZA == (
        "ausente", "extraida", "extraccion_indicada", "corona", "endodoncia", "implante",
    )  # fmt: skip
    assert fdi.ESTADOS_CARA == ("caries", "obturacion", "sellador", "fractura")
    assert fdi.CARAS == ("V", "L", "M", "D", "O")
    assert fdi.PIEZA_SIN_CARAS == ("ausente", "extraida")
