"""Tokens HS256: firma, expiración, type cruzado, blacklist (C-03 3.1, sin PG)."""

from datetime import timedelta
from unittest.mock import MagicMock

import jwt
import pytest

from app.domain.auth.tokens import (
    ACCESS,
    REFRESH,
    AuthError,
    issue_pair,
    issue_token,
    verify_token,
)

SECRET = "secreto-sintetico-32-chars-minimo-0000"
ALGO = "HS256"


def _pair():  # type: ignore[no-untyped-def]
    return issue_pair(
        sub=7,
        tenant_id=3,
        roles=["admin"],
        email="a@test.test",
        secret=SECRET,
        algorithm=ALGO,
    )


def test_roundtrip_access_ok() -> None:
    pair = _pair()
    claims = verify_token(pair.access_token, ACCESS, SECRET, ALGO)
    assert (claims.sub, claims.tenant_id, claims.roles) == (7, 3, ("admin",))
    assert claims.type == ACCESS
    assert claims.email == "a@test.test"
    assert len(claims.jti) == 32


def test_firma_tamper_rechazada() -> None:
    pair = _pair()
    with pytest.raises(AuthError) as exc:
        verify_token(pair.access_token, ACCESS, "otro-secreto-sintetico-32-chars-00", ALGO)
    assert exc.value.code == "invalid"


def test_type_cruzado_rechazado() -> None:
    pair = _pair()
    with pytest.raises(AuthError) as exc:
        verify_token(pair.refresh_token, ACCESS, SECRET, ALGO)
    assert exc.value.code == "invalid"
    with pytest.raises(AuthError) as exc2:
        verify_token(pair.access_token, REFRESH, SECRET, ALGO)
    assert exc2.value.code == "invalid"


def test_expirado_rechazado_y_tolerancia_60s() -> None:
    # 30s vencido: dentro de la tolerancia → válido.
    token, _, _ = issue_token(
        sub=1, tenant_id=1, roles=[], email="a@t.t",
        type=ACCESS, secret=SECRET, algorithm=ALGO,
        ttl=timedelta(seconds=-30),
    )
    assert verify_token(token, ACCESS, SECRET, ALGO).type == ACCESS
    # 300s vencido: fuera de tolerancia → expired.
    token_old, _, _ = issue_token(
        sub=1, tenant_id=1, roles=[], email="a@t.t",
        type=ACCESS, secret=SECRET, algorithm=ALGO,
        ttl=timedelta(seconds=-300),
    )
    with pytest.raises(AuthError) as exc:
        verify_token(token_old, ACCESS, SECRET, ALGO)
    assert exc.value.code == "expired"


def test_sin_claim_tenant_invalido() -> None:
    import time

    raw = jwt.encode(
        {
            "sub": "1",
            "jti": "x",
            "type": ACCESS,
            "iat": int(time.time()),
            "exp": int(time.time()) + 60,
        },
        SECRET,
        algorithm=ALGO,
    )
    with pytest.raises(AuthError) as exc:
        verify_token(raw, ACCESS, SECRET, ALGO)
    assert exc.value.code == "invalid"


def test_blacklist_revoca_y_sin_sesion_omite() -> None:
    pair = _pair()
    # Sin sesión: el lookup se omite, el token vale.
    assert verify_token(pair.access_token, ACCESS, SECRET, ALGO).jti == pair.access_jti
    # Con sesión que reporta el jti: revoked.
    session_hit = MagicMock()
    session_hit.scalar.return_value = pair.access_jti
    with pytest.raises(AuthError) as exc:
        verify_token(pair.access_token, ACCESS, SECRET, ALGO, session_hit)
    assert exc.value.code == "revoked"
    # Con sesión que no lo reporta: válido.
    session_miss = MagicMock()
    session_miss.scalar.return_value = None
    assert (
        verify_token(pair.access_token, ACCESS, SECRET, ALGO, session_miss).jti
        == pair.access_jti
    )


def test_issue_rechaza_type_desconocido() -> None:
    with pytest.raises(ValueError):
        issue_token(
            sub=1, tenant_id=1, roles=[], email="a@t.t",
            type="sospechoso", secret=SECRET, algorithm=ALGO,
            ttl=timedelta(minutes=1),
        )
