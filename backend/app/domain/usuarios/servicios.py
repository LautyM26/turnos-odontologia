"""Administración de usuarios del personal (C-18, D6; US-014).

``get_current_user`` lee los roles de la DB en cada request, así que un cambio de roles es
efectivo sin reemitir tokens. El servicio hace commit; el alta y el cambio de roles auditan en
la misma transacción (``registrar_evento_admin``) y una falla al auditar los revierte.
Nunca se loguean emails ni contraseñas.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.auditoria.writer import registrar_evento_admin
from app.domain.auth.passwords import normalize_email
from app.domain.core.models import Rol, Usuario, UsuarioRol
from app.domain.usuarios.errores import UltimoAdmin, UsuarioDuplicado, UsuarioNoEncontrado
from app.domain.usuarios.schemas import RolesIn, UsuarioAdminIn, UsuarioAdminOut

if TYPE_CHECKING:
    from app.api.deps import AuthContext

UNIQUE_VIOLATION = "23505"


def _out(usuario: Usuario, roles: Sequence[str]) -> UsuarioAdminOut:
    return UsuarioAdminOut(
        id=usuario.id,
        email=usuario.email,
        nombre=usuario.nombre,
        is_active=usuario.is_active,
        roles=sorted(roles),
    )


def _roles_por_usuario(
    session: Session, clinica_id: int, usuario_ids: Sequence[int]
) -> dict[int, list[str]]:
    filas = session.execute(
        select(UsuarioRol.usuario_id, Rol.clave)
        .join(Rol, Rol.id == UsuarioRol.rol_id)
        .where(
            UsuarioRol.clinica_id == clinica_id,
            UsuarioRol.usuario_id.in_(list(usuario_ids)),
            UsuarioRol.is_active.is_(True),
            Rol.is_active.is_(True),
        )
    ).all()
    por_usuario: dict[int, list[str]] = {i: [] for i in usuario_ids}
    for uid, clave in filas:
        por_usuario[uid].append(clave)
    return por_usuario


def _claves_a_roles(session: Session, claves: Sequence[str]) -> dict[str, Rol]:
    filas = session.scalars(select(Rol).where(Rol.clave.in_(list(claves)))).all()
    return {r.clave: r for r in filas}


def crear_usuario(
    session: Session, auth: "AuthContext", datos: UsuarioAdminIn, ip: str | None
) -> UsuarioAdminOut:
    """Alta en la clínica del admin (nunca otra); email único por clínica (sin mayúsculas)."""
    email = normalize_email(datos.email)
    existe = session.scalar(
        select(Usuario.id).where(
            Usuario.clinica_id == auth.tenant_id, func.lower(Usuario.email) == email
        )
    )
    if existe is not None:
        raise UsuarioDuplicado()
    hash_ = bcrypt.hashpw(datos.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    usuario = Usuario(
        clinica_id=auth.tenant_id, email=email, password_hash=hash_, nombre=datos.nombre
    )
    try:
        session.add(usuario)
        session.flush()
        roles = _claves_a_roles(session, datos.roles)
        for clave in datos.roles:
            session.add(
                UsuarioRol(usuario_id=usuario.id, rol_id=roles[clave].id, clinica_id=auth.tenant_id)
            )
        registrar_evento_admin(
            session, auth, "usuario_crear", usuario.id, {"roles": sorted(datos.roles)}, ip
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == UNIQUE_VIOLATION:
            raise UsuarioDuplicado() from exc
        raise
    except Exception:
        session.rollback()
        raise
    return _out(usuario, datos.roles)


def listar_usuarios(
    session: Session, clinica_id: int, after_id: int | None, limit: int
) -> tuple[list[UsuarioAdminOut], int | None]:
    """Usuarios de la clínica por id ascendente (cursor keyset), con sus roles activos."""
    stmt = select(Usuario).where(Usuario.clinica_id == clinica_id).order_by(Usuario.id)
    if after_id is not None:
        stmt = stmt.where(Usuario.id > after_id)
    filas = list(session.scalars(stmt.limit(limit + 1)).all())
    pagina = filas[:limit]
    roles = _roles_por_usuario(session, clinica_id, [u.id for u in pagina])
    items = [_out(u, roles[u.id]) for u in pagina]
    return items, (pagina[-1].id if len(filas) > limit else None)


def reemplazar_roles(
    session: Session, auth: "AuthContext", usuario_id: int, datos: RolesIn, ip: str | None
) -> UsuarioAdminOut:
    """Reemplaza el conjunto de roles activos; la clínica nunca queda sin admin activo.

    ``SELECT ... FOR UPDATE`` sobre las filas de los admins activos (en orden de id, sin
    deadlock) serializa a dos admins que se quitan el rol a la vez: el segundo ve el estado ya
    confirmado del primero.
    """
    usuario = session.scalars(
        select(Usuario).where(Usuario.id == usuario_id, Usuario.clinica_id == auth.tenant_id)
    ).one_or_none()
    if usuario is None:
        raise UsuarioNoEncontrado()
    nuevos = set(datos.roles)
    try:
        admins = set(
            session.scalars(
                select(UsuarioRol.usuario_id)
                .join(Rol, Rol.id == UsuarioRol.rol_id)
                .join(Usuario, Usuario.id == UsuarioRol.usuario_id)
                .where(
                    UsuarioRol.clinica_id == auth.tenant_id,
                    Rol.clave == "admin",
                    UsuarioRol.is_active.is_(True),
                    Usuario.is_active.is_(True),
                )
                .order_by(UsuarioRol.usuario_id)
                .with_for_update(of=UsuarioRol)
            ).all()
        )
        filas = session.execute(
            select(UsuarioRol, Rol.clave)
            .join(Rol, Rol.id == UsuarioRol.rol_id)
            .where(UsuarioRol.usuario_id == usuario.id, UsuarioRol.clinica_id == auth.tenant_id)
        ).all()
        anteriores = {clave for fila, clave in filas if fila.is_active}
        if anteriores == nuevos:
            session.rollback()
            return _out(usuario, sorted(nuevos))
        if "admin" in anteriores and "admin" not in nuevos and not (admins - {usuario.id}):
            raise UltimoAdmin()
        existentes = {clave for _, clave in filas}
        for fila, clave in filas:
            fila.is_active = clave in nuevos
        roles = _claves_a_roles(session, sorted(nuevos - existentes))
        for clave in nuevos - existentes:
            session.add(
                UsuarioRol(usuario_id=usuario.id, rol_id=roles[clave].id, clinica_id=auth.tenant_id)
            )
        session.flush()
        registrar_evento_admin(
            session, auth, "usuario_roles", usuario.id,
            {"roles_anteriores": sorted(anteriores), "roles": sorted(nuevos)}, ip,
        )  # fmt: skip
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _out(usuario, sorted(nuevos))
