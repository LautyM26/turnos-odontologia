"""Passwords: normalización, bcrypt, fallo genérico (C-03 3.2, sin PG)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import bcrypt

from app.domain.auth.passwords import (
    LOGIN_FALLO_MSG,
    authenticate,
    normalize_email,
    verify_password,
)


def test_normalize_email() -> None:
    assert normalize_email("  Admin@Clinica-Piloto.TEST ") == "admin@clinica-piloto.test"


def test_verify_password_ok_y_ko() -> None:
    digest = bcrypt.hashpw(b"Secreta123", bcrypt.gensalt()).decode("utf-8")
    assert verify_password("Secreta123", digest) is True
    assert verify_password("otra", digest) is False
    assert verify_password("x", "hash-invalido") is False


def _session_with(users: list) -> MagicMock:
    session = MagicMock()
    session.scalars.return_value.all.return_value = users
    return session


def test_authenticate_usuario_inexistente_retorna_none() -> None:
    assert authenticate(_session_with([]), "nadie@test.test", "x") is None


def test_authenticate_password_mala_retorna_none() -> None:
    digest = bcrypt.hashpw(b"Secreta123", bcrypt.gensalt()).decode("utf-8")
    user = SimpleNamespace(password_hash=digest)
    assert authenticate(_session_with([user]), "a@test.test", "mala") is None


def test_authenticate_ok_retorna_usuario() -> None:
    digest = bcrypt.hashpw(b"Secreta123", bcrypt.gensalt()).decode("utf-8")
    user = SimpleNamespace(password_hash=digest)
    assert authenticate(_session_with([user]), "  A@TEST.test ", "Secreta123") is user


def test_authenticate_ambiguo_multi_tenant_retorna_none() -> None:
    digest = bcrypt.hashpw(b"Secreta123", bcrypt.gensalt()).decode("utf-8")
    users = [SimpleNamespace(password_hash=digest), SimpleNamespace(password_hash=digest)]
    assert authenticate(_session_with(users), "a@test.test", "Secreta123") is None


def test_mensaje_fallo_es_generico_y_unico() -> None:
    assert LOGIN_FALLO_MSG == "Credenciales inválidas"
    assert "existe" not in LOGIN_FALLO_MSG and "password" not in LOGIN_FALLO_MSG.lower()
