"""Schemas de pacientes y ficha (C-08 5.1): extra=forbid, normalización, contacto."""

import pytest
from pydantic import ValidationError

from app.domain.pacientes.schemas import FichaPut, PacienteCreate, PacienteUpdate

BASE = {
    "nombre": "Paciente",
    "apellido": "Sintetico",
    "dni": "90000001",
    "telefono": "+5491155550001",
}


def test_create_normaliza_dni_email_y_telefono() -> None:
    p = PacienteCreate(
        nombre=" Ana ",
        apellido="Pérez",
        dni="90.123.456",
        email=" Ana@Example.COM ",
        telefono="011 15 5555-0001",
    )
    assert (p.nombre, p.dni, p.email, p.telefono) == (
        "Ana",
        "90123456",
        "ana@example.com",
        "+5491155550001",
    )


def test_create_con_solo_email_es_valido() -> None:
    p = PacienteCreate(nombre="A", apellido="B", dni="90000002", email="a@example.com")
    assert p.telefono is None


@pytest.mark.parametrize("campo", ["riesgo_ausencia", "clinica_id", "consentimiento_datos", "x"])
def test_create_rechaza_campos_extra(campo: str) -> None:
    with pytest.raises(ValidationError):
        PacienteCreate(**BASE, **{campo: 1})  # type: ignore[arg-type]


def test_create_sin_contacto_falla() -> None:
    with pytest.raises(ValidationError):
        PacienteCreate(nombre="A", apellido="B", dni="90000003")


@pytest.mark.parametrize(
    "cambio",
    [{"dni": "12AB"}, {"dni": "123"}, {"telefono": "abc"}, {"email": "sin-arroba"}, {"nombre": ""}],
)
def test_create_valores_invalidos(cambio: dict) -> None:
    with pytest.raises(ValidationError):
        PacienteCreate(**{**BASE, **cambio})


def test_obra_social_se_recorta() -> None:
    p = PacienteCreate(**BASE, obra_social_nombre="  OSDE ", nro_afiliado=" 123 ")
    assert p.obra_social_nombre == "OSDE"
    assert p.nro_afiliado == "123"


def test_update_todo_opcional_y_normaliza() -> None:
    assert PacienteUpdate().model_dump(exclude_unset=True) == {}
    p = PacienteUpdate(telefono="011 15 5555-0001", dni="90.123.456")
    assert p.model_dump(exclude_unset=True) == {"telefono": "+5491155550001", "dni": "90123456"}


@pytest.mark.parametrize("campo", ["riesgo_ausencia", "clinica_id", "id"])
def test_update_sin_riesgo_ni_tenant(campo: str) -> None:
    with pytest.raises(ValidationError):
        PacienteUpdate(**{campo: 5})  # type: ignore[arg-type]


def test_update_acepta_consentimiento() -> None:
    assert PacienteUpdate(consentimiento_datos=True).consentimiento_datos is True


def test_ficha_put_valida_version_y_largo() -> None:
    assert FichaPut(version_esperada=0, alergias="sintetica").version_esperada == 0
    with pytest.raises(ValidationError):
        FichaPut(version_esperada=-1)
    with pytest.raises(ValidationError):
        FichaPut(version_esperada=0, anamnesis="x" * 10001)
    with pytest.raises(ValidationError):
        FichaPut(version_esperada=0, autor_usuario_id=1)  # type: ignore[call-arg]
