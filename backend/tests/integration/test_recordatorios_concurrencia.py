"""Claim del recordatorio bajo concurrencia (C-15 5.2, D5): dos corridas, un solo envío."""

import threading
from datetime import timedelta

from app.infrastructure.whatsapp.fake import FakeMensajeria
from app.jobs.recordatorios import enviar_recordatorios
from tests.integration.conftest_whatsapp import nuevo_ahora, settings_wa, turno_wa


def test_dos_corridas_simultaneas_un_solo_envio(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, fake = nuevo_ahora(), FakeMensajeria()
    turno_wa(session_factory, turnos_data, ahora + timedelta(hours=6))
    barrera = threading.Barrier(2)
    errores: list[BaseException] = []

    def correr() -> None:
        try:
            with session_factory() as session:
                barrera.wait()
                enviar_recordatorios(session, fake, settings_wa(), ahora, dormir=lambda s: None)
        except BaseException as exc:  # noqa: BLE001 - se reporta en el assert
            errores.append(exc)

    hilos = [threading.Thread(target=correr) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=60)
    assert errores == []
    assert len(fake.enviados) == 1
