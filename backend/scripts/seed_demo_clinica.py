"""Seed de DEMO para recorrer la UI clínica (C-10). Solo datos sintéticos (regla dura 14).

Idempotente: se puede correr N veces sin duplicar filas. Reutiliza ``seed_core`` y
``seed_catalogo`` (clínica piloto, roles, admin, profesional seed) y agrega:

- ``odontologo@clinica-piloto.test`` (rol odontólogo, vinculado al profesional seed:
  requisito de autor en evoluciones) y ``recepcion@clinica-piloto.test`` (recepcionista);
- 3 pacientes ``es_seed = true`` obviamente ficticios (el tercero SIN consentimiento).

Contraseña de ambos usuarios: variable de entorno ``SEED_DEMO_PASSWORD`` (fallback dev-only).
Conexión: ``DATABASE_URL`` (no requiere el resto de las variables de la API).

Uso (desde la raíz del repo, con las migraciones aplicadas)::

    DATABASE_URL=postgresql+psycopg://... SEED_DEMO_PASSWORD=<elegila> \\
        python backend/scripts/seed_demo_clinica.py
"""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.domain.agenda.models import Profesional  # noqa: E402
from app.domain.core.models import Clinica, Rol, Usuario, UsuarioRol  # noqa: E402
from app.domain.pacientes.models import Paciente  # noqa: E402
from app.domain.pacientes.normalizacion import nombre_busqueda  # noqa: E402
from app.infrastructure.db import create_engine_for_url, create_session_factory  # noqa: E402
from app.infrastructure.persistence.seed_catalogo import (  # noqa: E402
    SEED_PROFESIONAL_MATRICULA,
    seed_catalogo,
)
from app.infrastructure.persistence.seed_core import (  # noqa: E402
    SEED_CLINICA_CUIT,
    hash_password,
    seed_core,
)

DOMINIO = "@clinica-piloto.test"
_DEV_ONLY_FALLBACK = "dev-only-cambiar-en-produccion"
USUARIOS = (
    ("odontologo" + DOMINIO, "Odontólogo Demo", "odontologo"),
    ("recepcion" + DOMINIO, "Recepción Demo", "recepcionista"),
)
# (nombre, apellido, dni, consentimiento)
PACIENTES = (
    ("Demo Uno", "Sintético", "99000001", True),
    ("Demo Dos", "Sintético", "99000002", True),
    ("Demo Tres", "Sintético", "99000003", False),
)


def _password() -> str:
    return os.environ.get("SEED_DEMO_PASSWORD") or _DEV_ONLY_FALLBACK


def _usuario(session: Session, clinica_id: int, email: str, nombre: str, rol: str) -> Usuario:
    usuario = session.scalars(
        select(Usuario).where(Usuario.clinica_id == clinica_id, func.lower(Usuario.email) == email)
    ).one_or_none()
    if usuario is None:
        usuario = Usuario(
            clinica_id=clinica_id,
            email=email,
            password_hash=hash_password(_password()),
            nombre=nombre,
        )
        session.add(usuario)
        session.flush()
    rol_fila = session.scalars(select(Rol).where(Rol.clave == rol)).one()
    asignado = session.scalars(
        select(UsuarioRol).where(
            UsuarioRol.usuario_id == usuario.id, UsuarioRol.rol_id == rol_fila.id
        )
    ).one_or_none()
    if asignado is None:
        session.add(UsuarioRol(usuario_id=usuario.id, rol_id=rol_fila.id, clinica_id=clinica_id))
    return usuario


def seed_demo(session: Session) -> dict[str, int]:
    seed_core(session)
    seed_catalogo(session)
    clinica = session.scalars(select(Clinica).where(Clinica.cuit == SEED_CLINICA_CUIT)).one()
    usuarios = {
        rol: _usuario(session, clinica.id, email, nombre, rol) for email, nombre, rol in USUARIOS
    }
    profesional = session.scalars(
        select(Profesional).where(
            Profesional.clinica_id == clinica.id,
            Profesional.matricula == SEED_PROFESIONAL_MATRICULA,
        )
    ).one()
    if profesional.usuario_id is None:
        profesional.usuario_id = usuarios["odontologo"].id
    ahora = datetime.now(UTC)
    for i, (nombre, apellido, dni, consiente) in enumerate(PACIENTES, start=1):
        existe = session.scalars(
            select(Paciente).where(Paciente.clinica_id == clinica.id, Paciente.dni == dni)
        ).one_or_none()
        if existe is None:
            session.add(
                Paciente(
                    clinica_id=clinica.id,
                    nombre=nombre,
                    apellido=apellido,
                    dni=dni,
                    email=f"demo{i}@ejemplo.test",
                    telefono=f"+549110000000{i}",
                    obra_social_nombre="OS Ficticia",
                    obra_social_plan=f"Plan {i}",
                    nro_afiliado=f"00011{i}",
                    consentimiento_datos=consiente,
                    consentimiento_datos_at=ahora if consiente else None,
                    consentimiento_datos_por=usuarios["odontologo"].id if consiente else None,
                    nombre_busqueda=nombre_busqueda(apellido, nombre),
                    es_seed=True,
                )
            )
    session.commit()
    return {
        "usuarios_demo": session.scalar(
            select(func.count()).select_from(Usuario).where(Usuario.email.like("%" + DOMINIO))
        )
        or 0,
        "pacientes_seed": session.scalar(
            select(func.count()).select_from(Paciente).where(Paciente.es_seed.is_(True))
        )
        or 0,
    }


def main() -> None:
    engine = create_engine_for_url(os.environ["DATABASE_URL"])
    with create_session_factory(engine)() as session:
        print(seed_demo(session))  # noqa: T201


if __name__ == "__main__":
    main()
