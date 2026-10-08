"""Emisión y verificación JWT HS256 con `type` discriminante (C-03, D1).

Claims: sub/tenant_id/roles/email/jti/type/iat/exp. Tolerancia de reloj 60s.
La blacklist se consulta por sesión PG (lookup por PK jti); sin sesión se
omite el chequeo (útil en tests unitarios puros de firma/expiración).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.auth.models import TokenBlacklist

LEEWAY_S = 60
ACCESS = "access"
REFRESH = "refresh"
_TOKEN_TYPES = (ACCESS, REFRESH)


@dataclass(frozen=True)
class TokenClaims:
    sub: int
    tenant_id: int
    roles: tuple[str, ...]
    email: str
    jti: str
    type: str
    iat: int
    exp: int


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    access_jti: str
    access_exp: datetime
    refresh_token: str
    refresh_jti: str
    refresh_exp: datetime


class AuthError(Exception):
    """Fallo de verificación. ``code``: expired | revoked | invalid."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _now() -> datetime:
    return datetime.now(UTC)


def issue_token(
    *,
    sub: int,
    tenant_id: int,
    roles: list[str],
    email: str,
    type: str,
    secret: str,
    algorithm: str = "HS256",
    ttl: timedelta,
) -> tuple[str, str, datetime]:
    """Emite un JWT. Retorna (token, jti, exp)."""
    if type not in _TOKEN_TYPES:
        raise ValueError(f"type inválido: {type}")
    now = _now()
    exp = now + ttl
    jti = uuid.uuid4().hex
    payload = {
        "sub": str(sub),
        "tenant_id": tenant_id,
        "roles": list(roles),
        "email": email,
        "jti": jti,
        "type": type,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return (jwt.encode(payload, secret, algorithm=algorithm), jti, exp)


def issue_pair(
    *,
    sub: int,
    tenant_id: int,
    roles: list[str],
    email: str,
    secret: str,
    algorithm: str = "HS256",
    access_min: int = 15,
    refresh_days: int = 7,
) -> TokenPair:
    """Emite el par access (minutos) + refresh (días) del login/refresh."""
    access_token, access_jti, access_exp = issue_token(
        sub=sub,
        tenant_id=tenant_id,
        roles=roles,
        email=email,
        type=ACCESS,
        secret=secret,
        algorithm=algorithm,
        ttl=timedelta(minutes=access_min),
    )
    refresh_token, refresh_jti, refresh_exp = issue_token(
        sub=sub,
        tenant_id=tenant_id,
        roles=roles,
        email=email,
        type=REFRESH,
        secret=secret,
        algorithm=algorithm,
        ttl=timedelta(days=refresh_days),
    )
    return TokenPair(
        access_token=access_token,
        access_jti=access_jti,
        access_exp=access_exp,
        refresh_token=refresh_token,
        refresh_jti=refresh_jti,
        refresh_exp=refresh_exp,
    )


def verify_token(
    token: str,
    expected_type: str,
    secret: str,
    algorithm: str = "HS256",
    session: Session | None = None,
) -> TokenClaims:
    """Verifica firma + exp (tolerancia 60s) + type + blacklist.

    Raises:
        AuthError("expired" | "revoked" | "invalid").
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            leeway=LEEWAY_S,
            options={"require": ["exp", "iat", "sub", "jti", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("invalid") from exc
    if payload.get("type") != expected_type:
        raise AuthError("invalid")
    try:
        sub = int(payload["sub"])
        tenant_id = int(payload["tenant_id"])
        roles = tuple(str(r) for r in payload.get("roles", []))
        email = str(payload["email"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthError("invalid") from exc
    if session is not None:
        hit = session.scalar(
            select(TokenBlacklist.jti).where(
                TokenBlacklist.jti == payload["jti"]
            )
        )
        if hit is not None:
            raise AuthError("revoked")
    return TokenClaims(
        sub=sub,
        tenant_id=tenant_id,
        roles=roles,
        email=email,
        jti=str(payload["jti"]),
        type=str(payload["type"]),
        iat=int(payload["iat"]),
        exp=int(payload["exp"]),
    )


def revoke_jti(
    session: Session,
    *,
    jti: str,
    type: str,
    exp: datetime,
    motivo: str,
) -> None:
    """Inserta un jti en la blacklist (idempotente por PK)."""
    if session.get(TokenBlacklist, jti) is None:
        session.add(
            TokenBlacklist(jti=jti, type=type, exp=exp, motivo=motivo)
        )
        session.commit()
