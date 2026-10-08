"""Normalización pura de identificadores de paciente (C-08 2.1/2.2). Datos sintéticos."""

import pytest

from app.domain.pacientes.normalizacion import (
    NormalizacionError,
    nombre_busqueda,
    normalizar_dni,
    normalizar_email,
    normalizar_telefono,
)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("90.123.456", "90123456"), (" 9 000 001 ", "9000001"), ("90-000-002", "90000002")],
)
def test_dni_normaliza_a_digitos(entrada: str, esperado: str) -> None:
    assert normalizar_dni(entrada) == esperado


@pytest.mark.parametrize("entrada", ["12AB", "123456", "123456789", "", "   "])
def test_dni_invalido(entrada: str) -> None:
    with pytest.raises(NormalizacionError):
        normalizar_dni(entrada)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [(" Ana@Example.COM ", "ana@example.com"), ("B@EXAMPLE.com", "b@example.com")],
)
def test_email_minusculas_sin_espacios(entrada: str, esperado: str) -> None:
    assert normalizar_email(entrada) == esperado


def test_email_invalido() -> None:
    with pytest.raises(NormalizacionError):
        normalizar_email("sin-arroba")


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("011 15 5555-0001", "+5491155550001"),
        ("+54 9 11 5555-0002", "+5491155550002"),
        ("+5491155550002", "+5491155550002"),
    ],
)
def test_telefono_e164_argentino(entrada: str, esperado: str) -> None:
    assert normalizar_telefono(entrada) == esperado


def test_telefono_idempotente() -> None:
    una = normalizar_telefono("011 15 5555-0001")
    assert normalizar_telefono(una) == una


@pytest.mark.parametrize("entrada", ["abc", "123", ""])
def test_telefono_invalido(entrada: str) -> None:
    with pytest.raises(NormalizacionError):
        normalizar_telefono(entrada)


@pytest.mark.parametrize(
    ("apellido", "nombre", "esperado"),
    [
        ("Pérez", "José María", "perez jose maria"),
        ("  ÑANDÚ ", "Úrsula", "nandu ursula"),
    ],
)
def test_nombre_busqueda_sin_acentos(apellido: str, nombre: str, esperado: str) -> None:
    assert nombre_busqueda(apellido, nombre) == esperado
