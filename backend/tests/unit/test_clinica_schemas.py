"""Schemas del odontograma y de la evolución (C-09, extra=forbid). Dominio puro, sin DB."""

import pytest
from pydantic import ValidationError

from app.domain.clinica.fdi import piezas_validas
from app.domain.clinica.schemas import EvolucionIn, OdontogramaIn


def _odonto(**over):  # type: ignore[no-untyped-def]
    base = {"version_esperada": 0, "denticion": "permanente", "piezas": {}}
    base.update(over)
    return OdontogramaIn(**base)


def test_acepta_piezas_vacias() -> None:
    assert _odonto().piezas == {}


def test_acepta_marcas_existente_y_a_realizar() -> None:
    o = _odonto(
        piezas={
            "36": {
                "estado": {"codigo": "corona"},
                "caras": {
                    "M": {"codigo": "caries", "registro": "a_realizar"},
                    "O": {"codigo": "obturacion", "registro": "existente"},
                },
            }
        }
    )
    pieza = o.piezas["36"]
    assert pieza.caras["M"].registro == "a_realizar"
    assert pieza.caras["O"].registro == "existente"
    assert pieza.estado is not None and pieza.estado.registro == "existente"  # default


@pytest.mark.parametrize("pieza", ["55", "85", "10", "19", "abc", "1"])
def test_pieza_invalida_en_permanente(pieza: str) -> None:
    with pytest.raises(ValidationError):
        _odonto(piezas={pieza: {}})


def test_pieza_permanente_en_temporal_rechazada_y_temporal_aceptada() -> None:
    with pytest.raises(ValidationError):
        _odonto(denticion="temporal", piezas={"16": {}})
    assert "85" in _odonto(denticion="temporal", piezas={"85": {}}).piezas


@pytest.mark.parametrize("pieza", ["10", "19", "49", "56", "86", "90"])
def test_mixta_rechaza_fuera_de_rango(pieza: str) -> None:
    with pytest.raises(ValidationError):
        _odonto(denticion="mixta", piezas={pieza: {}})


def test_mixta_acepta_limites() -> None:
    o = _odonto(denticion="mixta", piezas={p: {} for p in ("11", "48", "51", "85")})
    assert len(o.piezas) == 4


def test_cara_desconocida() -> None:
    with pytest.raises(ValidationError):
        _odonto(piezas={"16": {"caras": {"X": {"codigo": "caries"}}}})


def test_estado_desconocido() -> None:
    with pytest.raises(ValidationError):
        _odonto(piezas={"16": {"caras": {"O": {"codigo": "blanqueamiento"}}}})
    with pytest.raises(ValidationError):
        _odonto(piezas={"16": {"estado": {"codigo": "blanqueamiento"}}})


@pytest.mark.parametrize("estado", ["ausente", "extraida"])
def test_pieza_ausente_o_extraida_sin_caras(estado: str) -> None:
    with pytest.raises(ValidationError):
        _odonto(piezas={"26": {"estado": {"codigo": estado}, "caras": {"O": {"codigo": "caries"}}}})
    assert _odonto(piezas={"26": {"estado": {"codigo": estado}, "caras": {}}})


def test_codigo_de_cara_en_pieza_y_viceversa() -> None:
    with pytest.raises(ValidationError):
        _odonto(piezas={"16": {"estado": {"codigo": "caries"}}})
    with pytest.raises(ValidationError):
        _odonto(piezas={"16": {"caras": {"O": {"codigo": "corona"}}}})


def test_campos_extra_en_cada_nivel() -> None:
    with pytest.raises(ValidationError):
        _odonto(autor_usuario_id=1)
    with pytest.raises(ValidationError):
        _odonto(piezas={"16": {"extra": 1}})
    with pytest.raises(ValidationError):
        _odonto(piezas={"16": {"estado": {"codigo": "corona", "x": 1}}})
    with pytest.raises(ValidationError):
        _odonto(piezas={"16": {"caras": {"O": {"codigo": "caries", "x": 1}}}})


def test_registro_invalido() -> None:
    with pytest.raises(ValidationError):
        _odonto(piezas={"16": {"caras": {"O": {"codigo": "caries", "registro": "futuro"}}}})


def test_version_esperada_negativa_y_denticion_invalida() -> None:
    with pytest.raises(ValidationError):
        _odonto(version_esperada=-1)
    with pytest.raises(ValidationError):
        _odonto(denticion="lactante")


def test_mas_de_52_piezas() -> None:
    # En mixta hay exactamente 52 claves válidas: el máximo se alcanza y no se excede.
    todas = {str(p): {} for p in piezas_validas("mixta")}
    assert len(_odonto(denticion="mixta", piezas=todas).piezas) == 52
    todas["99"] = {}
    with pytest.raises(ValidationError):
        _odonto(denticion="mixta", piezas=todas)


# --- EvolucionIn (1.3) ---------------------------------------------------------------------


def _evo(**over):  # type: ignore[no-untyped-def]
    base = {"texto": "Control sintético"}
    base.update(over)
    return EvolucionIn(**base)


def test_evolucion_minima_y_recorte() -> None:
    e = _evo(texto="  hola  ", pieza_fdi=16)
    assert e.texto == "hola" and e.pieza_fdi == 16
    assert e.corrige_a_id is None and e.motivo_correccion is None


@pytest.mark.parametrize("texto", ["", "   ", "\n\t"])
def test_texto_en_blanco(texto: str) -> None:
    with pytest.raises(ValidationError):
        _evo(texto=texto)


def test_texto_limite_10000() -> None:
    assert _evo(texto="a" * 10_000)
    with pytest.raises(ValidationError):
        _evo(texto="a" * 10_001)


@pytest.mark.parametrize("pieza", [19, 10, 49, 56, 86, 0])
def test_pieza_fdi_invalida(pieza: int) -> None:
    with pytest.raises(ValidationError):
        _evo(pieza_fdi=pieza)


@pytest.mark.parametrize("campo", ["autor_usuario_id", "profesional_id", "fecha_hora"])
def test_autor_o_fecha_en_cuerpo_rechazados(campo: str) -> None:
    with pytest.raises(ValidationError):
        _evo(**{campo: 1})


def test_correccion_exige_ambos_campos() -> None:
    with pytest.raises(ValidationError):
        _evo(corrige_a_id=5)
    with pytest.raises(ValidationError):
        _evo(motivo_correccion="Pieza mal indicada")
    with pytest.raises(ValidationError):
        _evo(corrige_a_id=5, motivo_correccion="   ")
    e = _evo(corrige_a_id=5, motivo_correccion="Pieza mal indicada")
    assert e.corrige_a_id == 5


def test_motivo_limite_500() -> None:
    assert _evo(corrige_a_id=5, motivo_correccion="m" * 500)
    with pytest.raises(ValidationError):
        _evo(corrige_a_id=5, motivo_correccion="m" * 501)
