"""Seed sintetico de catalogo (C-04): idempotente y borrable sin tocar datos no-seed."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.domain.agenda.models import (
    Bloqueo,
    Prestacion,
    Profesional,
    ProfesionalSillon,
    SillonRecurso,
)
from app.domain.core.models import Clinica
from app.infrastructure.persistence.seed_catalogo import borrar_seed_catalogo, seed_catalogo
from app.infrastructure.persistence.seed_core import SEED_CLINICA_CUIT


def _contar(session, modelo, clinica_id, **filtros) -> int:  # type: ignore[no-untyped-def]
    stmt = select(func.count()).select_from(modelo).where(modelo.clinica_id == clinica_id)
    for campo, valor in filtros.items():
        stmt = stmt.where(getattr(modelo, campo) == valor)
    return session.scalar(stmt)


def test_seed_doble_deja_1_sillon_1_profesional_y_3_prestaciones(  # type: ignore[no-untyped-def]
    session_factory, auth_data
) -> None:
    with session_factory() as session:
        clinica = session.scalars(select(Clinica).where(Clinica.cuit == SEED_CLINICA_CUIT)).one()
        primero = seed_catalogo(session)
        segundo = seed_catalogo(session)
        assert primero == segundo
        cid = clinica.id
        assert _contar(session, SillonRecurso, cid, es_seed=True) == 1
        assert _contar(session, Profesional, cid, es_seed=True) == 1
        assert _contar(session, Prestacion, cid, es_seed=True) == 3
        prof = session.scalars(select(Profesional).where(Profesional.clinica_id == cid)).one()
        sillon = session.scalars(select(SillonRecurso).where(SillonRecurso.clinica_id == cid)).one()
        habilitados = session.scalars(
            select(ProfesionalSillon.sillon_id).where(
                ProfesionalSillon.profesional_id == prof.id, ProfesionalSillon.is_active.is_(True)
            )
        ).all()
        assert list(habilitados) == [sillon.id]
        assert prof.usuario_id is None and prof.es_seed is True
        duraciones = sorted(
            session.scalars(select(Prestacion.duracion_min).where(Prestacion.clinica_id == cid))
        )
        assert duraciones == [30, 45, 60]
        precios = session.scalars(select(Prestacion.precio_referencia)).all()
        assert all(isinstance(p, Decimal) for p in precios)


def test_seed_no_toca_otras_clinicas(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        seed_catalogo(session)
        assert _contar(session, Prestacion, auth_data["clinica_b"]) == 0
        assert _contar(session, Profesional, auth_data["clinica_b"]) == 0


def test_borrar_seed_conserva_registros_no_seed(session_factory, auth_data) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        seed_catalogo(session)
        cid = auth_data["clinica_a"]
        manual = Prestacion(
            clinica_id=cid, nombre="Cargada por admin", duracion_min=20,
            precio_referencia=Decimal("5.00"),
        )  # fmt: skip
        session.add(manual)
        prof_seed = session.scalars(
            select(Profesional).where(Profesional.clinica_id == cid, Profesional.es_seed.is_(True))
        ).one()
        bloqueo = Bloqueo(
            clinica_id=cid, profesional_id=prof_seed.id, motivo="dependiente del seed",
            inicio=datetime(2035, 1, 1, 10, tzinfo=UTC), fin=datetime(2035, 1, 1, 11, tzinfo=UTC),
        )  # fmt: skip
        session.add(bloqueo)
        session.commit()

        borrar_seed_catalogo(session, cid)
        session.commit()

        assert _contar(session, Prestacion, cid, es_seed=True) == 0
        assert _contar(session, SillonRecurso, cid, es_seed=True) == 0
        assert _contar(session, Profesional, cid, es_seed=True) == 0
        assert _contar(session, ProfesionalSillon, cid) == 0
        assert _contar(session, Bloqueo, cid) == 0
        assert session.get(Prestacion, manual.id).nombre == "Cargada por admin"

        # Tras borrar, el seed puede volver a crearse sin duplicar.
        seed_catalogo(session)
        assert _contar(session, Prestacion, cid, es_seed=True) == 3
