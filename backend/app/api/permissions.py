"""PermissionContext: dependencias RBAC finas (C-03 5.2, matriz del 03).

Roles: admin (todo), odontologo (clínico + agenda/bloqueos propios),
recepcionista (turnos + sobreturnos, sin HC clínica, sin anular caja),
paciente-enlace (solo reserva pública). Todo falla cerrado: 401 sin token,
403 sin rol. Sobreturnos/anulaciones son contrato que C-05/C-12 invocarán.
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, get_current_user
from app.infrastructure.db import get_session

#: (session, usuario_id) → profesional_id vinculado. Sin binding (pre-C-04)
#: retorna None → falla cerrado. C-04 lo reemplaza por el join real.
AgendaResolver = Callable[[Session, int], int | None]
_agenda_resolver: AgendaResolver | None = None


def set_resolver_agenda_propia(fn: AgendaResolver | None) -> None:
    """Inyecta el vínculo Usuario→Profesional (C-04; solo tests hasta entonces)."""
    global _agenda_resolver
    _agenda_resolver = fn


def require_role(*claves: str):  # type: ignore[no-untyped-def]
    """Dependencia: exige al menos uno de los roles (JWT + DB)."""

    def _check(
        auth: AuthContext = Depends(get_current_user),  # noqa: B008
    ) -> AuthContext:
        if not any(rol in auth.roles for rol in claves):
            raise HTTPException(status_code=403, detail="Rol insuficiente")
        return auth

    return _check


def require_admin():  # type: ignore[no-untyped-def]
    """Atajo: solo admin (configuración, anulaciones de caja, admin/*)."""
    return require_role("admin")


def require_clinico():  # type: ignore[no-untyped-def]
    """HC/odontograma/evolución: admin + odontólogo (recepción → 403)."""
    return require_role("admin", "odontologo")


def require_sobreturno():  # type: ignore[no-untyped-def]
    """Sobreturnos RN-AG-04: admin/recepcionista (odontólogo → 403)."""
    return require_role("admin", "recepcionista")


def require_anulacion_caja():  # type: ignore[no-untyped-def]
    """Anulaciones RN-CA-03: solo admin con traza (resto → 403)."""
    return require_role("admin")


def require_own_agenda(
    request: Request,
    auth: AuthContext = Depends(get_current_user),  # noqa: B008
    session: Session = Depends(get_session),  # type: ignore[arg-type] # noqa: B008
) -> AuthContext:
    """Agenda tercerizada: odontólogo solo ve la propia (tercerizado o no).

    Lee ``profesional_id`` del path o query (convención C-05). Admin y
    recepcionista gestionan todas. Sin vínculo Usuario→Profesional → 403
    (fallo cerrado pre-C-04).
    """
    if "admin" in auth.roles or "recepcionista" in auth.roles:
        return auth
    raw = request.path_params.get("profesional_id", request.query_params.get("profesional_id"))
    if raw is None:
        raise HTTPException(status_code=422, detail="profesional_id requerido")
    try:
        profesional_id = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="profesional_id inválido") from None
    vinculado = _agenda_resolver(session, auth.sub) if _agenda_resolver else None
    if vinculado is None or vinculado != profesional_id:
        raise HTTPException(status_code=403, detail="Agenda no autorizada")
    return auth
