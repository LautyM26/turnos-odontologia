"""Confirmaciones simultáneas del chatbot (C-17 3.2, D4): una sola reprogramación."""

import threading
from datetime import timedelta

from sqlalchemy import func, select

from app.domain.agenda.turnos import Turno, TurnoTransicion
from app.infrastructure.whatsapp.fake import FakeMensajeria
from tests.integration.conftest_lista import escenario, responder
from tests.integration.conftest_whatsapp import recordatorio_enviado


def test_dos_si_simultaneos_una_sola_reprogramacion(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    pid, tel = e.paciente()
    tid = e.turno(20, pid)
    recordatorio_enviado(session_factory, turnos_data, tid, pid, tel)
    responder(e, tel, "3", e.ahora, fake)
    responder(e, tel, "1", e.ahora, fake)
    barrera = threading.Barrier(2)
    resultados: list[str] = []
    errores: list[BaseException] = []

    def correr(texto: str) -> None:
        try:
            barrera.wait()
            resultados.append(responder(e, tel, texto, e.ahora + timedelta(minutes=1), fake))
        except BaseException as exc:  # noqa: BLE001 - se reporta en el assert
            errores.append(exc)

    hilos = [threading.Thread(target=correr, args=(t,)) for t in ("si", "SI")]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=60)
    assert errores == []
    assert resultados.count("chatbot_reprogramado") == 1
    with session_factory() as s:
        nuevos = s.scalar(select(func.count()).select_from(Turno).where(
            Turno.paciente_id == pid, Turno.origen == "whatsapp"))  # fmt: skip
        cancelaciones = s.scalar(select(func.count()).select_from(TurnoTransicion).where(
            TurnoTransicion.turno_id == tid, TurnoTransicion.hacia == "cancelado"))  # fmt: skip
    assert (nuevos, cancelaciones) == (1, 1)


def test_confirmacion_con_conversacion_vieja_no_repite(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    """El claim ``confirmando -> ejecutando`` es la última barrera: aunque un proceso tenga la
    conversación leída antes de que otro la cierre, no reprograma dos veces."""
    from decimal import Decimal

    from app.domain.reprogramacion import chatbot
    from app.domain.reprogramacion.models import ConversacionWA
    from app.domain.reprogramacion.servicios import Ajustes

    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    pid, tel = e.paciente()
    tid = e.turno(20, pid)
    recordatorio_enviado(session_factory, turnos_data, tid, pid, tel)
    responder(e, tel, "3", e.ahora, fake)
    responder(e, tel, "1", e.ahora, fake)
    with session_factory() as vieja:
        conv = chatbot.conversacion_abierta(vieja, e.c, tel)  # leída en "confirmando"
        assert responder(e, tel, "si", e.ahora, fake) == "chatbot_reprogramado"
        r = chatbot.responder(vieja, conv, "si", e.ahora, fake, Decimal("12.50"), Ajustes())
    assert r == "sin_efecto"
    with session_factory() as s:
        final = s.get(ConversacionWA, conv.id)
        assert (final.estado, final.resultado) == ("cerrada", "reprogramado")
