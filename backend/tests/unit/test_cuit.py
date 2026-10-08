"""CUIT módulo 11 + schemas extra=forbid (Task 2.1, spec core-models)."""

import pytest
from pydantic import ValidationError

from app.domain.core.cuit import normalizar_cuit, validar_cuit
from app.domain.core.schemas import ClinicaCreate, UsuarioCreate


def test_cuit_valido_con_guiones_se_normaliza() -> None:
    assert normalizar_cuit("30-12345678-1") == "30123456781"
    assert validar_cuit("30-12345678-1") is True
    assert validar_cuit("30123456781") is True


def test_cuit_invalido_rechazado() -> None:
    assert validar_cuit("20-12345678-9") is False
    assert validar_cuit("no-es-cuit") is False
    assert validar_cuit("30-12345678") is False
    with pytest.raises(ValueError):
        normalizar_cuit("abc")


def test_clinica_create_normaliza_cuit_y_rechaza_invalido() -> None:
    ok = ClinicaCreate(nombre="Clínica Sintética", cuit="30-12345678-1")
    assert ok.cuit == "30123456781"
    with pytest.raises(ValidationError):
        ClinicaCreate(nombre="Clínica Sintética", cuit="20-12345678-9")


def test_schemas_rechazan_campos_extra() -> None:
    with pytest.raises(ValidationError):
        ClinicaCreate(nombre="X", cuit="30-12345678-1", is_superuser=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        UsuarioCreate(clinica_id=1, email="a@demo.com", password="secreto01", rol="x")  # type: ignore[call-arg]


def test_usuario_create_normaliza_email() -> None:
    user = UsuarioCreate(clinica_id=1, email="Admin@Demo.COM", password="secreto01")
    assert user.email == "admin@demo.com"
