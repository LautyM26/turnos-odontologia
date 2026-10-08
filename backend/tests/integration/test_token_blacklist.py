"""Blacklist: purga borra expiradas, conserva vigentes (C-03 2.2, PG16 real)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select


def test_purga_blacklist_borra_solo_expiradas(session_factory) -> None:
    from app.domain.auth.models import TokenBlacklist
    from app.jobs.purga_blacklist import purgar_blacklist

    ahora = datetime.now(UTC)
    session = session_factory()
    try:
        session.add(
            TokenBlacklist(
                jti="jti-expirada-sintetica",
                type="refresh",
                exp=ahora - timedelta(hours=2),
                motivo="test",
            )
        )
        session.add(
            TokenBlacklist(
                jti="jti-vigente-sintetica",
                type="refresh",
                exp=ahora + timedelta(days=1),
                motivo="test",
            )
        )
        session.commit()
    finally:
        session.close()

    session = session_factory()
    try:
        borradas = purgar_blacklist(session)
        assert borradas == 1
        restantes = session.scalars(select(TokenBlacklist.jti)).all()
        assert restantes == ["jti-vigente-sintetica"]
        # Purga es no-op en segunda corrida (idempotente).
        assert purgar_blacklist(session) == 0
    finally:
        session.close()


def test_blacklist_rechaza_jti_duplicado(session_factory) -> None:
    """PK sobre jti: el mismo jti no se inserta dos veces."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.domain.auth.models import TokenBlacklist

    ahora = datetime.now(UTC)
    session = session_factory()
    try:
        session.add(
            TokenBlacklist(jti="jti-dup-sintetica", type="access", exp=ahora)
        )
        session.commit()
        session.add(
            TokenBlacklist(jti="jti-dup-sintetica", type="access", exp=ahora)
        )
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
        cleanup = session_factory()
        try:
            obj = cleanup.get(TokenBlacklist, "jti-dup-sintetica")
            if obj is not None:
                cleanup.delete(obj)
                cleanup.commit()
        finally:
            cleanup.close()
