"""Evento duplicado no repite efectos (C-15 6.2, D7): secuencial y simultáneo."""

import threading
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.domain.agenda.turnos import TurnoTransicion
from app.domain.whatsapp.models import MensajeWhatsApp
from app.domain.whatsapp.servicios import procesar_mensaje_entrante
from app.infrastructure.whatsapp.fake import FakeMensajeria
from tests.integration.conftest_whatsapp import (
    nuevo_ahora,
    recordatorio_enviado,
    telefono_unico,
    turno_wa,
)


def _preparar(session_factory, td):  # type: ignore[no-untyped-def]
    ahora, tel = nuevo_ahora(), telefono_unico()
    tid, pid = turno_wa(session_factory, td, ahora + timedelta(hours=20), telefono=tel)
    recordatorio_enviado(session_factory, td, tid, pid, tel)
    return ahora, tel, tid


def _procesar(session_factory, td, tel, ahora, fake) -> str:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return procesar_mensaje_entrante(
            session, td["a"], f"IN-dup-{tel}", tel, "SI", ahora, fake, Decimal("12.50")
        )


def _conteos(session_factory, tel: str, tid: int) -> tuple[int, int, int]:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        def n(*w):  # type: ignore[no-untyped-def]
            return session.scalar(select(func.count()).select_from(MensajeWhatsApp).where(*w))

        entrantes = n(MensajeWhatsApp.telefono == tel, MensajeWhatsApp.direccion == "entrante")
        respuestas = n(MensajeWhatsApp.telefono == tel, MensajeWhatsApp.plantilla == "confirmacion")
        transiciones = session.scalar(
            select(func.count()).select_from(TurnoTransicion).where(TurnoTransicion.turno_id == tid)
        )
        return entrantes, transiciones, respuestas


def test_mismo_evento_dos_veces_seguidas(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, tel, tid = _preparar(session_factory, turnos_data)
    fake = FakeMensajeria()
    assert _procesar(session_factory, turnos_data, tel, ahora, fake) == "confirmado"
    assert _procesar(session_factory, turnos_data, tel, ahora, fake) == "duplicado"
    assert _conteos(session_factory, tel, tid) == (1, 1, 1)
    assert len(fake.enviados) == 1


def test_mismo_evento_dos_veces_en_paralelo(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, tel, tid = _preparar(session_factory, turnos_data)
    fake = FakeMensajeria()
    barrera = threading.Barrier(2)
    resultados: list[str] = []
    errores: list[BaseException] = []

    def correr() -> None:
        try:
            barrera.wait()
            resultados.append(_procesar(session_factory, turnos_data, tel, ahora, fake))
        except BaseException as exc:  # noqa: BLE001 - se reporta en el assert
            errores.append(exc)

    hilos = [threading.Thread(target=correr) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=60)
    assert errores == []
    assert sorted(resultados) == ["confirmado", "duplicado"]
    assert _conteos(session_factory, tel, tid) == (1, 1, 1)
    assert len(fake.enviados) == 1
