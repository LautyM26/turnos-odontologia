"""Endpoints /api/auth/*: login, refresh con rotación, logout, me (C-03).

Transporte: access en ``Authorization: Bearer`` (+ cuerpo login/refresh),
refresh SOLO en cookie HttpOnly (Secure/SameSite=Lax/Path=/api/auth).
Fallos de login genéricos (sin enumeración). Rate limit 5/min por IP+email.
Eventos en log estructurado ``turnos.auth`` (email/IP, sin más PII).
"""

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, roles_of_user
from app.domain.auth.passwords import LOGIN_FALLO_MSG, authenticate
from app.domain.auth.ratelimit import LOGIN_LIMIT, limiter
from app.domain.auth.schemas import LoginIn, MeOut, RefreshIn, TokenOut
from app.domain.auth.tokens import (
    ACCESS,
    REFRESH,
    AuthError,
    issue_pair,
    revoke_jti,
    verify_token,
)
from app.infrastructure.db import get_session
from app.infrastructure.settings import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_auth_log = logging.getLogger("turnos.auth")

REFRESH_COOKIE = "refresh_token"
REFRESH_FALLO_MSG = "Sesión inválida o expirada"


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def _evento(tipo: str, **campos: object) -> None:
    _auth_log.info(json.dumps({"evento": tipo, **campos}, ensure_ascii=False))


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    esquema, _, credencial = auth.partition(" ")
    if esquema.lower() != "bearer" or not credencial.strip():
        return None
    return credencial.strip()


def _set_refresh_cookie(
    response: JSONResponse, refresh: str, refresh_days: int, secure: bool
) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api/auth",
        max_age=refresh_days * 86400,
    )


def _clear_refresh_cookie(response: JSONResponse) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/api/auth")


@router.post("/login", response_model=TokenOut)
@limiter.limit(LOGIN_LIMIT)
def login(
    request: Request,
    body: LoginIn,
    session: Session = Depends(get_session),  # type: ignore[arg-type] # noqa: B008
) -> JSONResponse:
    """Valida credenciales y emite el par access + refresh."""
    ip = _client_ip(request)
    user = authenticate(session, body.email, body.password)
    if user is None:
        _evento("login_ko", email=body.email, ip=ip)
        raise HTTPException(status_code=401, detail=LOGIN_FALLO_MSG)
    settings = get_settings()
    roles = list(roles_of_user(session, user.id, user.clinica_id))
    pair = issue_pair(
        sub=user.id,
        tenant_id=user.clinica_id,
        roles=roles,
        email=user.email,
        secret=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_min=settings.jwt_access_min,
        refresh_days=settings.jwt_refresh_days,
    )
    _evento(
        "login_ok", email=user.email, ip=ip, tenant_id=user.clinica_id, roles=roles
    )
    payload = TokenOut(
        access_token=pair.access_token,
        expires_in=settings.jwt_access_min * 60,
    ).model_dump()
    response = JSONResponse(status_code=200, content=payload)
    _set_refresh_cookie(
        response, pair.refresh_token, settings.jwt_refresh_days, settings.cookie_secure
    )
    return response


@router.post("/refresh", response_model=TokenOut)
def refresh(
    request: Request,
    body: RefreshIn | None = Body(default=None),  # noqa: B008
    session: Session = Depends(get_session),  # type: ignore[arg-type] # noqa: B008
) -> JSONResponse:
    """Rota el refresh de la cookie: nuevo par + blacklist del jti anterior."""
    _ = body  # El refresh viaja solo en cookie; el body solo valida forbid.
    ip = _client_ip(request)
    settings = get_settings()
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        _evento("refresh_ko", motivo="sin_cookie", ip=ip)
        raise HTTPException(status_code=401, detail=REFRESH_FALLO_MSG)
    try:
        claims = verify_token(
            raw, REFRESH, settings.jwt_secret_key, settings.jwt_algorithm, session
        )
    except AuthError as exc:
        _evento("refresh_ko", motivo=exc.code, ip=ip)
        raise HTTPException(status_code=401, detail=REFRESH_FALLO_MSG) from exc
    from app.domain.core.models import Usuario

    user = session.get(Usuario, claims.sub)
    if (
        user is None
        or not user.is_active
        or user.clinica_id != claims.tenant_id
        or user.email != claims.email
    ):
        _evento("refresh_ko", motivo="usuario_invalido", ip=ip)
        raise HTTPException(status_code=401, detail=REFRESH_FALLO_MSG)
    revoke_jti(
        session,
        jti=claims.jti,
        type=REFRESH,
        exp=_exp_dt(claims.exp),
        motivo="rotated",
    )
    roles = list(roles_of_user(session, user.id, user.clinica_id))
    pair = issue_pair(
        sub=user.id,
        tenant_id=user.clinica_id,
        roles=roles,
        email=user.email,
        secret=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_min=settings.jwt_access_min,
        refresh_days=settings.jwt_refresh_days,
    )
    _evento("refresh_ok", email=user.email, ip=ip, tenant_id=user.clinica_id)
    payload = TokenOut(
        access_token=pair.access_token,
        expires_in=settings.jwt_access_min * 60,
    ).model_dump()
    response = JSONResponse(status_code=200, content=payload)
    _set_refresh_cookie(
        response, pair.refresh_token, settings.jwt_refresh_days, settings.cookie_secure
    )
    return response


@router.post("/logout")
def logout(
    request: Request,
    session: Session = Depends(get_session),  # type: ignore[arg-type] # noqa: B008
) -> JSONResponse:
    """Revoca access + refresh vigentes (best effort) y limpia la cookie."""
    ip = _client_ip(request)
    settings = get_settings()
    email: str | None = None
    access = _bearer_token(request)
    if access:
        try:
            claims = verify_token(
                access, ACCESS, settings.jwt_secret_key, settings.jwt_algorithm, session
            )
            email = claims.email
            revoke_jti(
                session,
                jti=claims.jti,
                type=ACCESS,
                exp=_exp_dt(claims.exp),
                motivo="logout",
            )
        except AuthError:
            pass
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        try:
            claims = verify_token(
                raw, REFRESH, settings.jwt_secret_key, settings.jwt_algorithm, session
            )
            email = email or claims.email
            revoke_jti(
                session,
                jti=claims.jti,
                type=REFRESH,
                exp=_exp_dt(claims.exp),
                motivo="logout",
            )
        except AuthError:
            pass
    _evento("logout", email=email, ip=ip)
    response = JSONResponse(status_code=200, content={"detail": "Sesión cerrada"})
    _clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=MeOut)
def me(auth=Depends(get_current_user)) -> MeOut:  # type: ignore[no-untyped-def] # noqa: B008
    """Identidad del access vigente."""
    return MeOut(
        sub=auth.sub, email=auth.email, tenant_id=auth.tenant_id, roles=list(auth.roles)
    )


def _exp_dt(exp_ts: int) -> datetime:
    return datetime.fromtimestamp(exp_ts, tz=UTC)
