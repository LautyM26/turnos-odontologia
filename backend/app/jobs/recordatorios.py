"""Recordatorios de turno por WhatsApp (C-15 D5, RN-TU-02). Cron del SO, cada ~15 min.

Uso: ``python -m app.jobs.recordatorios`` (lee DATABASE_URL y WHATSAPP_* de settings).

Un recordatorio por turno ``reservado`` que empieza dentro de ``WHATSAPP_RECORDATORIO_HORAS``.
El "claim" es el UNIQUE parcial ``(clinica_id, turno_id)`` de la 014: dos corridas solapadas no
envían dos veces. Los fallos transitorios se reintentan en corridas siguientes (backoff = período
del cron) hasta ``WHATSAPP_MAX_INTENTOS``; el turno nunca cambia de estado por un fallo.
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.agenda.turnos import Turno
from app.domain.pacientes.models import Paciente
from app.domain.whatsapp.models import MOTIVOS_TRANSITORIOS, MensajeWhatsApp
from app.domain.whatsapp.servicios import despachar, renderizar
from app.infrastructure.settings import Settings
from app.infrastructure.whatsapp.puerto import Mensajeria, NoConfigurado

PLANTILLA = "recordatorio_24h"
_ES_RECORDATORIO = (MensajeWhatsApp.direccion == "saliente") & (
    MensajeWhatsApp.plantilla == PLANTILLA
)
#: Predicado del índice parcial ``uq_mensaje_whatsapp_recordatorio_turno`` como SQL literal: con
#: parámetros, en cuanto psycopg prepara el INSERT, PostgreSQL deja de inferir el índice del
#: ``ON CONFLICT`` (InvalidColumnReference). Tiene que coincidir con la migración 014.
_PREDICADO_INDICE = text("direccion = 'saliente' AND plantilla = 'recordatorio_24h'")


Candidato = tuple[int, int, int, str | None]


def _nuevos(session: Session, ahora: datetime, horas: int) -> list[Candidato]:
    """Turnos en ventana sin fila de recordatorio: (clinica_id, turno_id, paciente_id, tel)."""
    ya = select(MensajeWhatsApp.id).where(
        _ES_RECORDATORIO,
        MensajeWhatsApp.clinica_id == Turno.clinica_id,
        MensajeWhatsApp.turno_id == Turno.id,
    )
    filas = session.execute(
        select(Turno.clinica_id, Turno.id, Turno.paciente_id, Paciente.telefono)
        .join(Paciente, (Paciente.clinica_id == Turno.clinica_id)
              & (Paciente.id == Turno.paciente_id))
        .where(
            Turno.is_active.is_(True), Turno.estado == "reservado",
            Turno.inicio > ahora, Turno.inicio <= ahora + timedelta(hours=horas),
            ~ya.exists(),
        )
        .order_by(Turno.inicio)
    ).all()  # fmt: skip
    return [tuple(f) for f in filas]  # type: ignore[misc]


def _reintentos(session: Session, ahora: datetime, max_intentos: int) -> list[int]:
    return list(
        session.scalars(
            select(MensajeWhatsApp.id)
            .join(Turno, (Turno.clinica_id == MensajeWhatsApp.clinica_id)
                  & (Turno.id == MensajeWhatsApp.turno_id))
            .where(
                _ES_RECORDATORIO, MensajeWhatsApp.estado == "error",
                MensajeWhatsApp.motivo_error.in_(MOTIVOS_TRANSITORIOS),
                MensajeWhatsApp.intentos < max_intentos,
                Turno.is_active.is_(True), Turno.estado == "reservado", Turno.inicio > ahora,
            )
            .order_by(MensajeWhatsApp.id)
        )
    )  # fmt: skip


def _reclamar_nuevo(
    session: Session, clinica_id: int, turno_id: int, paciente_id: int, telefono: str | None
) -> int | None:
    """INSERT ... ON CONFLICT DO NOTHING + commit: id si esta corrida ganó el turno."""
    valores = {
        "clinica_id": clinica_id, "turno_id": turno_id, "paciente_id": paciente_id,
        "plantilla": PLANTILLA, "direccion": "saliente", "telefono": telefono,
        "texto": renderizar(session, clinica_id, PLANTILLA, turno_id),
        "estado": "pendiente" if telefono else "error",
        "motivo_error": None if telefono else "sin_telefono",
        "requiere_atencion": telefono is None,
    }  # fmt: skip
    stmt = (
        insert(MensajeWhatsApp)
        .values(**valores)
        .on_conflict_do_nothing(
            index_elements=["clinica_id", "turno_id"],
            index_where=_PREDICADO_INDICE,
        )
        .returning(MensajeWhatsApp.id)
    )
    nuevo = session.scalar(stmt)
    session.commit()
    return nuevo if telefono else None


def _reclamar_reintento(session: Session, mensaje_id: int) -> bool:
    """``error -> pendiente`` atómico + commit: solo una corrida reintenta cada fila."""
    hecho = session.execute(
        update(MensajeWhatsApp)
        .where(MensajeWhatsApp.id == mensaje_id, MensajeWhatsApp.estado == "error")
        .values(estado="pendiente", motivo_error=None)
    )
    session.commit()
    return bool(hecho.rowcount)


def enviar_recordatorios(
    session: Session,
    mensajeria: Mensajeria | NoConfigurado,
    settings: Settings,
    ahora: datetime,
    dormir: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    """Una corrida del job; devuelve conteos ``{"enviados", "fallidos"}``.

    ponytail: un ``pendiente`` que quede colgado por una caída del proceso a mitad del envío no
    se reintenta solo (la bandeja no lo muestra); agregar barrido por antigüedad si pasa.
    """
    a_enviar = [
        mid for c, t, p, tel in _nuevos(session, ahora, settings.whatsapp_recordatorio_horas)
        if (mid := _reclamar_nuevo(session, c, t, p, tel)) is not None
    ]  # fmt: skip
    a_enviar += [
        mid for mid in _reintentos(session, ahora, settings.whatsapp_max_intentos)
        if _reclamar_reintento(session, mid)
    ]  # fmt: skip
    intervalo = 60 / settings.whatsapp_envios_por_minuto
    conteo = {"enviados": 0, "fallidos": 0}
    for i, mid in enumerate(a_enviar):
        if i and not isinstance(mensajeria, NoConfigurado):
            dormir(intervalo)
        msg = session.get(MensajeWhatsApp, mid)
        assert msg is not None
        ok = despachar(session, mensajeria, msg, settings.ars_precio_mensaje)
        conteo["enviados" if ok else "fallidos"] += 1
    return conteo


def main() -> int:
    """Entry-point CLI para el cron."""
    from app.infrastructure.db import create_engine_for_url, create_session_factory
    from app.infrastructure.settings import get_settings
    from app.infrastructure.whatsapp.factory import obtener_mensajeria

    settings = get_settings()
    factory = create_session_factory(create_engine_for_url(settings.database_url))
    with factory() as session:
        conteo = enviar_recordatorios(
            session, obtener_mensajeria(settings), settings, datetime.now(UTC)
        )
    print(f"recordatorios: {conteo['enviados']} enviados, {conteo['fallidos']} fallidos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
