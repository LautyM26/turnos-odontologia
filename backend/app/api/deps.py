"""Dependencias FastAPI: identidad JWT + tenant con cross-check (C-03, D6).

El ``tenant_id`` autoritativo es el claim JWT. ``X-Clinica-Id`` se mantiene
como afirmación opcional del cliente sujeta a cross-check (mismatch → 403).
Sin JWT válido → 401 salvo ruta pública declarada (ver ``is_public_path``).

**BREAKING C-03**: todo endpoint scoped sin token pasa a 401 (antes solo
pedía header). El frontend debe enviar ``Authorization: Bearer <access>``
+ ``X-Clinica-Id`` y no guardar JWT en ``localStorage``.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.auth.tokens import AuthError, verify_token
from app.domain.core.models import Clinica, Rol, Usuario, UsuarioRol
from app.infrastructure.db import get_session
from app.infrastructure.settings import get_settings

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login", auto_error=False
)

BREAKING_AUTH_MSG = (
    "No autenticado. Enviá Authorization: Bearer <access> (BREAKING C-03: "
    "los endpoints scoped exigen JWT; el header X-Clinica-Id solo se "
    "cross-chequea contra el claim tenant_id)."
)

MISMATCH_MSG = "Tenant no autorizado para esta sesión."

#: Prefijos exentos de login (D8). Resto exige JWT.
PUBLIC_PREFIXES = (
    "/api/auth",
    "/api/public",
    "/api/webhooks/mercadopago",
    "/api/webhooks/whatsapp",
    "/api/comprobantes",
    "/cumplimiento",
    "/privacidad",
    "/api/health",
)


def is_public_path(path: str) -> bool:
    """True si el path es ruta pública declarada (sin login)."""
    return any(
        path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in PUBLIC_PREFIXES
    )


@dataclass(frozen=True)
class AuthContext:
    """Identidad verificada del request (roles desde DB, no solo del JWT)."""

    sub: int
    tenant_id: int
    roles: tuple[str, ...]
    email: str
    jti: str


def roles_of_user(session: Session, usuario_id: int, clinica_id: int) -> tuple[str, ...]:
    """Claves de rol activas del usuario en su tenant (ordenadas)."""
    rows = session.scalars(
        select(Rol.clave)
        .join(UsuarioRol, UsuarioRol.rol_id == Rol.id)
        .where(
            UsuarioRol.usuario_id == usuario_id,
            UsuarioRol.clinica_id == clinica_id,
            UsuarioRol.is_active.is_(True),
            Rol.is_active.is_(True),
        )
    ).all()
    return tuple(sorted(rows))


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Session = Depends(get_session),  # type: ignore[arg-type] # noqa: B008
) -> AuthContext:
    """Valida Bearer access: firma + exp + type + blacklist + usuario activo.

    Raises:
        401 sin token / firma inválida / revocado / usuario inactivo.
        404 si el tenant del JWT ya no existe.
    """
    if not token:
        raise HTTPException(status_code=401, detail=BREAKING_AUTH_MSG)
    settings = get_settings()
    try:
        claims = verify_token(
            token, "access", settings.jwt_secret_key, settings.jwt_algorithm, session
        )
    except AuthError as exc:
        if exc.code == "expired":
            raise HTTPException(status_code=401, detail="Sesión expirada") from exc
        if exc.code == "revoked":
            raise HTTPException(status_code=401, detail="Sesión revocada") from exc
        raise HTTPException(
            status_code=401, detail="Credenciales de acceso inválidas"
        ) from exc
    user = session.get(Usuario, claims.sub)
    if user is None or not user.is_active or user.clinica_id != claims.tenant_id:
        raise HTTPException(status_code=401, detail="Credenciales de acceso inválidas")
    exists = session.scalar(
        select(Clinica.id).where(Clinica.id == claims.tenant_id)
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Clínica inexistente")
    return AuthContext(
        sub=claims.sub,
        tenant_id=claims.tenant_id,
        roles=roles_of_user(session, user.id, claims.tenant_id),
        email=claims.email,
        jti=claims.jti,
    )


def require_tenant_checked(
    auth: Annotated[AuthContext, Depends(get_current_user)],
    clinica_id: Annotated[str | None, Header(alias="X-Clinica-Id")] = None,
) -> int:
    """Tenant autoritativo = JWT; header opcional con cross-check.

    Sin header usa el ``tenant_id`` del JWT. Con header distinto → 403.
    """
    if clinica_id is None:
        return auth.tenant_id
    try:
        header_id = int(clinica_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Tenant inválido") from None
    if header_id <= 0:
        raise HTTPException(status_code=422, detail="Tenant inválido")
    if header_id != auth.tenant_id:
        raise HTTPException(status_code=403, detail=MISMATCH_MSG)
    return auth.tenant_id


def require_tenant(
    clinica_id: Annotated[str | None, Header(alias="X-Clinica-Id")] = None,
    session: Session = Depends(get_session),  # type: ignore[arg-type] # noqa: B008
) -> int:
    """Compat C-02 (solo header, sin JWT). Preferir ``require_tenant_checked``.

    Se mantiene para rutas públicas/legacy; los endpoints scoped deben usar
    ``require_tenant_checked`` (cross-check JWT, cierra spoofing C-02).
    """
    if clinica_id is None:
        raise HTTPException(status_code=422, detail="Tenant requerido")
    try:
        tenant_id = int(clinica_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Tenant inválido") from None
    if tenant_id <= 0:
        raise HTTPException(status_code=422, detail="Tenant inválido")
    exists = session.scalars(select(Clinica.id).where(Clinica.id == tenant_id)).first()
    if exists is None:
        raise HTTPException(status_code=404, detail="Clínica inexistente")
    return tenant_id
