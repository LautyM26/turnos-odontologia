"""Seed mínimo idempotente: 1 clínica + 4 roles + 1 admin (C-02, D8).

Solo datos sintéticos (regla dura 14). Password ADMIN vía env
``SEED_ADMIN_PASSWORD``; fallback dev-only documentado, nunca en repo.
"""

import os

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.core.models import ROL_CLAVES, Clinica, Rol, Usuario, UsuarioRol

SEED_CLINICA_CUIT = "30123456781"
SEED_CLINICA_NOMBRE = "Clinica Piloto Sintetica"
SEED_ADMIN_EMAIL = "admin@clinica-piloto.test"
_DEV_ONLY_FALLBACK = "dev-only-cambiar-en-produccion"

_ROL_NOMBRES = {
    "admin": "Administrador",
    "odontologo": "Odontólogo",
    "recepcionista": "Recepcionista",
    "paciente-enlace": "Enlace Paciente",
}


def _admin_password() -> str:
    """Password ADMIN desde env; fallback SOLO desarrollo local/CI."""
    return os.environ.get("SEED_ADMIN_PASSWORD") or _DEV_ONLY_FALLBACK


def hash_password(plain: str) -> str:
    """Hash bcrypt costo estándar (12)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_core(session: Session) -> dict[str, int]:
    """Upserts por clave natural; re-ejecución = no-op en conteos."""
    clinica = session.scalars(
        select(Clinica).where(Clinica.cuit == SEED_CLINICA_CUIT)
    ).one_or_none()
    if clinica is None:
        clinica = Clinica(
            nombre=SEED_CLINICA_NOMBRE,
            cuit=SEED_CLINICA_CUIT,
            email_contacto="contacto@clinica-piloto.test",
            es_seed=True,
        )
        session.add(clinica)
        session.flush()

    for clave in ROL_CLAVES:
        rol = session.scalars(select(Rol).where(Rol.clave == clave)).one_or_none()
        if rol is None:
            session.add(Rol(clave=clave, nombre=_ROL_NOMBRES[clave]))
    session.flush()

    admin = session.scalars(
        select(Usuario).where(
            Usuario.clinica_id == clinica.id,
            func.lower(Usuario.email) == SEED_ADMIN_EMAIL,
        )
    ).one_or_none()
    if admin is None:
        admin = Usuario(
            clinica_id=clinica.id,
            email=SEED_ADMIN_EMAIL,
            password_hash=hash_password(_admin_password()),
            nombre="Admin Sintetico",
        )
        session.add(admin)
        session.flush()

    rol_admin = session.scalars(select(Rol).where(Rol.clave == "admin")).one()
    asignacion = session.scalars(
        select(UsuarioRol).where(
            UsuarioRol.usuario_id == admin.id, UsuarioRol.rol_id == rol_admin.id
        )
    ).one_or_none()
    if asignacion is None:
        session.add(
            UsuarioRol(
                usuario_id=admin.id, rol_id=rol_admin.id, clinica_id=clinica.id
            )
        )
    session.commit()

    counts = {
        "clinicas": session.scalar(select(func.count()).select_from(Clinica)) or 0,
        "roles": session.scalar(select(func.count()).select_from(Rol)) or 0,
        "admins": session.scalar(
            select(func.count())
            .select_from(Usuario)
            .where(func.lower(Usuario.email) == SEED_ADMIN_EMAIL)
        )
        or 0,
    }
    return counts
