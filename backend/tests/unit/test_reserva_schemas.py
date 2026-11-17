"""Contrato público de reserva (C-06 D5): sin cuenta, privacidad obligatoria, datos normalizados."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.agenda.schemas_publicas import ReservaIn

BASE = {
    "profesional_id": 1,
    "prestacion_id": 2,
    "inicio": "2031-03-10T09:00:00-03:00",
    "dni": "30.111.222",
    "nombre": "  Ana ",
    "apellido": "Sintetica",
    "email": "Ana@Ejemplo.TEST",
    "acepta_privacidad": True,
}


def test_normaliza_dni_email_nombre_e_inicio_utc() -> None:
    body = ReservaIn(**BASE)
    assert body.dni == "30111222"
    assert body.email == "ana@ejemplo.test"
    assert body.nombre == "Ana"
    assert body.inicio == datetime(2031, 3, 10, 12, tzinfo=UTC)


def test_telefono_solo_se_normaliza_a_e164() -> None:
    sin_email = {k: v for k, v in BASE.items() if k != "email"}
    assert ReservaIn(**sin_email, telefono="011 15 2345-6789").telefono == "+5491123456789"


@pytest.mark.parametrize(
    "cambio",
    [
        {"acepta_privacidad": False},
        {"acepta_privacidad": None},
        {"dni": "12"},
        {"email": None},
        {"email": "no-es-email"},
        {"telefono": "abc"},
        {"nombre": ""},
        {"apellido": "x" * 101},
        {"inicio": "2031-03-10T09:00:00"},
        {"sobreturno": True},
        {"clinica_id": 9},
    ],
    ids=[
        "privacidad_false", "privacidad_null", "dni", "sin_contacto", "email", "telefono",
        "nombre_vacio", "apellido_largo", "inicio_sin_zona", "sobreturno", "clinica_id",
    ],
)  # fmt: skip
def test_reserva_invalida(cambio) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        ReservaIn(**{**BASE, **cambio})


def test_privacidad_ausente_falla() -> None:
    with pytest.raises(ValidationError):
        ReservaIn(**{k: v for k, v in BASE.items() if k != "acepta_privacidad"})
