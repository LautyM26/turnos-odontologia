"""Engine/session factory placeholder (modelos reales desde C-02).

Constraints futuras (regla dura 7/10, C-02): montos SIEMPRE NUMERIC en ARS,
tiempo SIEMPRE TIMESTAMPTZ, toda tabla tenant-scoped con clinica_id + índice
(clinica_id, ...). Datos de test solo sintéticos seed=true (regla 14).
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine_for_url(database_url: str):  # type: ignore[no-untyped-def]
    """Create a SQLAlchemy engine for the given database URL."""
    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine):  # type: ignore[no-untyped-def]
    """Create a session factory bound to the engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


_engine = None
_session_factory = None


def _factory():  # type: ignore[no-untyped-def]
    """Lazy singleton session factory from settings (overrideable in tests)."""
    global _engine, _session_factory
    if _session_factory is None:
        from app.infrastructure.settings import get_settings

        _engine = create_engine_for_url(get_settings().database_url)
        _session_factory = create_session_factory(_engine)
    return _session_factory


def get_session() -> Iterator[Session]:
    """Yield one scoped session per request; always closes it."""
    factory = _factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
