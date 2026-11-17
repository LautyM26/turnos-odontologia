"""Doble aceptación simultánea (C-16 4.4, D6): una sola reasignación efectiva."""

import threading
from datetime import timedelta

from sqlalchemy import func, select

from app.domain.agenda.turnos import Turno
from app.domain.whatsapp.models import MensajeWhatsApp
from app.infrastructure.whatsapp.fake import FakeMensajeria
from app.jobs.lista_espera import procesar_lista_espera
from tests.integration.conftest_lista import escenario, responder, settings_le


def test_dos_aceptaciones_distintas_en_paralelo(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    pid, tel = e.paciente()
    e.entrada(pid)
    e.hueco(20)
    with session_factory() as s:
        procesar_lista_espera(s, fake, settings_le(), e.ahora)
    barrera = threading.Barrier(2)
    resultados: list[str] = []
    errores: list[BaseException] = []

    def correr(texto: str) -> None:
        try:
            barrera.wait()
            resultados.append(responder(e, tel, texto, e.ahora + timedelta(minutes=5), fake))
        except BaseException as exc:  # noqa: BLE001 - se reporta en el assert
            errores.append(exc)

    hilos = [threading.Thread(target=correr, args=(t,)) for t in ("1", "si")]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=60)
    assert errores == []
    assert sorted(resultados) == ["oferta_aceptada", "sin_efecto"]
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(Turno).where(
            Turno.paciente_id == pid, Turno.origen == "lista_espera")) == 1  # fmt: skip
        assert s.scalar(select(func.count()).select_from(MensajeWhatsApp).where(
            MensajeWhatsApp.telefono == tel,
            MensajeWhatsApp.plantilla == "oferta_aceptada")) == 1  # fmt: skip
