"""Seed sintetico del catalogo de agenda (C-04, regla dura 14).

Debe correr DESPUES de ``seed_core`` (necesita la clinica piloto). Idempotente por
clave natural (nombre / matricula dentro de la clinica piloto).

Supuesto PA-09 / SU-06: las duraciones y precios son SINTETICOS de ejemplo; el
catalogo real del consultorio piloto los reemplaza (por la API admin o retirando
el seed con ``borrar_seed_catalogo`` antes del go-live). Sin datos reales.
"""

from decimal import Decimal

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.domain.agenda.models import (
    Bloqueo,
    Prestacion,
    Profesional,
    ProfesionalSillon,
    SillonRecurso,
)
from app.domain.core.models import Clinica
from app.infrastructure.persistence.seed_core import SEED_CLINICA_CUIT

SEED_SILLON_NOMBRE = "Sillón 1 (seed)"
SEED_PROFESIONAL_NOMBRE = "Profesional Ejemplo (seed)"
SEED_PROFESIONAL_MATRICULA = "SEED-0001"
SEED_PRESTACIONES = (
    ("Consulta y diagnóstico (seed)", 30, Decimal("20000.00")),
    ("Limpieza y profilaxis (seed)", 45, Decimal("30000.00")),
    ("Obturación simple (seed)", 60, Decimal("45000.00")),
)


def _clinica_piloto(session: Session) -> Clinica:
    clinica = session.scalars(
        select(Clinica).where(Clinica.cuit == SEED_CLINICA_CUIT)
    ).one_or_none()
    if clinica is None:
        raise RuntimeError("Clinica piloto inexistente: ejecutar seed_core antes de seed_catalogo")
    return clinica


def seed_catalogo(session: Session) -> dict[str, int]:
    """Crea (si faltan) 1 sillon, 1 profesional habilitado y 3 prestaciones seed."""
    cid = _clinica_piloto(session).id

    sillon = session.scalars(
        select(SillonRecurso).where(
            SillonRecurso.clinica_id == cid,
            SillonRecurso.nombre == SEED_SILLON_NOMBRE,
            SillonRecurso.es_seed.is_(True),
        )
    ).one_or_none()
    if sillon is None:
        sillon = SillonRecurso(
            clinica_id=cid, nombre=SEED_SILLON_NOMBRE, tipo="sillon", es_seed=True
        )
        session.add(sillon)

    profesional = session.scalars(
        select(Profesional).where(
            Profesional.clinica_id == cid,
            Profesional.matricula == SEED_PROFESIONAL_MATRICULA,
            Profesional.es_seed.is_(True),
        )
    ).one_or_none()
    if profesional is None:
        profesional = Profesional(
            clinica_id=cid,
            nombre=SEED_PROFESIONAL_NOMBRE,
            matricula=SEED_PROFESIONAL_MATRICULA,
            es_seed=True,
        )
        session.add(profesional)
    session.flush()

    habilitacion = session.get(ProfesionalSillon, (profesional.id, sillon.id))
    if habilitacion is None:
        session.add(
            ProfesionalSillon(profesional_id=profesional.id, sillon_id=sillon.id, clinica_id=cid)
        )

    for nombre, duracion, precio in SEED_PRESTACIONES:
        existe = session.scalars(
            select(Prestacion.id).where(
                Prestacion.clinica_id == cid,
                Prestacion.nombre == nombre,
                Prestacion.es_seed.is_(True),
            )
        ).first()
        if existe is None:
            session.add(
                Prestacion(
                    clinica_id=cid,
                    nombre=nombre,
                    duracion_min=duracion,
                    precio_referencia=precio,
                    es_seed=True,
                )
            )
    session.commit()
    return {"sillones": 1, "profesionales": 1, "prestaciones": len(SEED_PRESTACIONES)}


def borrar_seed_catalogo(session: Session, clinica_id: int) -> None:
    """Retira fisicamente SOLO filas ``es_seed`` y sus dependientes (utilitario de infra).

    No es un camino de dominio (el dominio solo da de baja logica). No hace commit.
    """
    ids_prof = select(Profesional.id).where(
        Profesional.clinica_id == clinica_id, Profesional.es_seed.is_(True)
    )
    ids_sillon = select(SillonRecurso.id).where(
        SillonRecurso.clinica_id == clinica_id, SillonRecurso.es_seed.is_(True)
    )
    session.execute(
        delete(Bloqueo).where(
            Bloqueo.clinica_id == clinica_id,
            or_(Bloqueo.profesional_id.in_(ids_prof), Bloqueo.sillon_id.in_(ids_sillon)),
        )
    )
    session.execute(
        delete(ProfesionalSillon).where(
            ProfesionalSillon.clinica_id == clinica_id,
            or_(
                ProfesionalSillon.profesional_id.in_(ids_prof),
                ProfesionalSillon.sillon_id.in_(ids_sillon),
            ),
        )
    )
    for modelo in (Profesional, SillonRecurso, Prestacion):
        session.execute(
            delete(modelo).where(modelo.clinica_id == clinica_id, modelo.es_seed.is_(True))
        )
