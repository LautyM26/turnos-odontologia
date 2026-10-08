"""Seed idempotente sobre PG16 real (Tasks 4.1/4.2). NUNCA SQLite."""

import bcrypt
from sqlalchemy import select

from app.domain.core.models import Usuario
from app.infrastructure.persistence.seed_core import seed_core


def test_seed_doble_ejecucion_es_noop(session_factory) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        first = seed_core(session)
    with session_factory() as session:
        second = seed_core(session)
    assert first == {"clinicas": 1, "roles": 4, "admins": 1}
    assert second == first


def test_seed_solo_datos_sinteticos_y_hash(session_factory) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        admin = session.scalars(
            select(Usuario).where(Usuario.email == "admin@clinica-piloto.test")
        ).one()
        assert admin.password_hash != "dev-only-cambiar-en-produccion"
        assert bcrypt.checkpw(
            b"dev-only-cambiar-en-produccion", admin.password_hash.encode("utf-8")
        )
        assert admin.clinica.es_seed is True
