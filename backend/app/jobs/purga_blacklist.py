"""Purga de jti expirados de token_blacklist (C-03 2.2, D5).

Invocado por cron del SO o scheduler. Uso:
``python -m app.jobs.purga_blacklist`` (lee DATABASE_URL de settings).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.domain.auth.models import TokenBlacklist

GRACIA_POST_EXP = timedelta(hours=1)


def purgar_blacklist(session: Session, ahora: datetime | None = None) -> int:
    """Borra filas con ``exp`` anterior a (ahora - 1h). Retorna filas borradas."""
    limite = (ahora or datetime.now(UTC)) - GRACIA_POST_EXP
    resultado = session.execute(
        delete(TokenBlacklist).where(TokenBlacklist.exp < limite)
    )
    session.commit()
    return resultado.rowcount or 0


def main() -> int:
    """Entry-point CLI: abre sesión contra DATABASE_URL y purga."""
    from app.infrastructure.db import create_engine_for_url, create_session_factory
    from app.infrastructure.settings import get_settings

    engine = create_engine_for_url(get_settings().database_url)
    factory = create_session_factory(engine)
    session = factory()
    try:
        borradas = purgar_blacklist(session)
    finally:
        session.close()
    print(f"purga_blacklist: {borradas} filas borradas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
