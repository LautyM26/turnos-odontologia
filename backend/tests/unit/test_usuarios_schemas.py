"""Schemas de administración de usuarios (C-18 1.7)."""

import pytest
from pydantic import ValidationError

from app.domain.usuarios.schemas import RolesIn, UsuarioAdminIn

BASE = {"email": "Alta@Example.com", "nombre": "Alta Sintetica", "password": "clave-sintetica-1",
        "roles": ["odontologo"]}  # fmt: skip


def test_alta_valida_normaliza_email() -> None:
    u = UsuarioAdminIn(**BASE)
    assert u.email == "alta@example.com"
    assert u.roles == ["odontologo"]


@pytest.mark.parametrize(
    "roles",
    [[], ["odontologo", "odontologo"], ["paciente-enlace"], ["superuser"], ["admin", "x"]],
)
def test_roles_invalidos(roles) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        UsuarioAdminIn(**{**BASE, "roles": roles})
    with pytest.raises(ValidationError):
        RolesIn(roles=roles)


def test_varios_roles_validos() -> None:
    assert UsuarioAdminIn(**{**BASE, "roles": ["admin", "odontologo"]}).roles == [
        "admin", "odontologo",
    ]  # fmt: skip
    assert RolesIn(roles=["recepcionista"]).roles == ["recepcionista"]


@pytest.mark.parametrize("password", ["", "1234567", "x" * 129])
def test_password_fuera_de_rango(password: str) -> None:
    with pytest.raises(ValidationError):
        UsuarioAdminIn(**{**BASE, "password": password})


@pytest.mark.parametrize("extra", ["clinica_id", "password_hash", "is_active"])
def test_rechaza_campos_de_servidor(extra: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        UsuarioAdminIn(**BASE, **{extra: 1})
    with pytest.raises(ValidationError, match="Extra inputs"):
        RolesIn(roles=["admin"], **{extra: 1})


def test_email_invalido_y_nombre_vacio() -> None:
    with pytest.raises(ValidationError):
        UsuarioAdminIn(**{**BASE, "email": "no-es-email"})
    with pytest.raises(ValidationError):
        UsuarioAdminIn(**{**BASE, "nombre": ""})
