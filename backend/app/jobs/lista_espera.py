"""Relleno automático de huecos por lista de espera (C-16 D1, RN-AG-06). Cron cada 5 min.

Uso: ``python -m app.jobs.lista_espera``. Cada corrida: vence ofertas -> busca huecos
liberados -> ofrece cada hueco al primer candidato. Si el canal falla, corta la corrida para no
consumir la cola (la oferta queda anulada y la entrada vuelve a esperar).
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.domain.lista_espera.servicios import (
    elegir_candidato,
    huecos_liberados,
    ofertar,
    vencer_ofertas,
)
from app.infrastructure.settings import Settings
from app.infrastructure.whatsapp.puerto import Mensajeria, NoConfigurado


def procesar_lista_espera(
    session: Session, mensajeria: Mensajeria | NoConfigurado, settings: Settings, ahora: datetime
) -> dict[str, int]:
    """Una corrida; devuelve ``{"vencidas", "ofertas", "fallidas"}``."""
    conteo = {"vencidas": vencer_ofertas(session, ahora), "ofertas": 0, "fallidas": 0}
    for hueco in huecos_liberados(session, ahora, settings.lista_espera_anticipacion_min):
        entrada = elegir_candidato(session, hueco)
        if entrada is None:
            continue
        oferta, enviada = ofertar(session, mensajeria, settings, entrada, hueco, ahora)
        if oferta is None:
            continue
        if not enviada:
            conteo["fallidas"] += 1
            break
        conteo["ofertas"] += 1
    return conteo


def main() -> int:
    from app.infrastructure.db import create_engine_for_url, create_session_factory
    from app.infrastructure.settings import get_settings
    from app.infrastructure.whatsapp.factory import obtener_mensajeria

    settings = get_settings()
    factory = create_session_factory(create_engine_for_url(settings.database_url))
    with factory() as session:
        c = procesar_lista_espera(
            session, obtener_mensajeria(settings), settings, datetime.now(UTC)
        )
    print(f"lista_espera: {c['vencidas']} vencidas, {c['ofertas']} ofertas, "
          f"{c['fallidas']} fallidas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
