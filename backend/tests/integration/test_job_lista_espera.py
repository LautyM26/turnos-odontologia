"""Job de la lista de espera (C-16 5.1, D1): vencimiento, rotación y canal caído."""

from datetime import timedelta

from sqlalchemy import select

from app.domain.lista_espera.models import ListaEspera, OfertaListaEspera
from app.domain.whatsapp.models import MensajeWhatsApp
from app.infrastructure.whatsapp.fake import FakeMensajeria
from app.jobs.lista_espera import procesar_lista_espera
from tests.integration.conftest_lista import escenario, settings_le


def _correr(e, fake, ahora):  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return procesar_lista_espera(s, fake, settings_le(), ahora)


def _estado(e, modelo, id_: int) -> str:  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return s.get(modelo, id_).estado


def _ofertas(e, eid):  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return list(s.scalars(select(OfertaListaEspera).where(
            OfertaListaEspera.lista_espera_id == eid)))  # fmt: skip


def test_expirar_pasa_al_siguiente_en_la_misma_corrida(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    e2, e3 = e.entrada(e.paciente()[0], prioridad=5), e.entrada(e.paciente()[0])
    hueco = e.hueco(20)
    _correr(e, fake, e.ahora)
    [o2] = _ofertas(e, e2)
    c = _correr(e, fake, e.ahora + timedelta(minutes=31))
    assert c["vencidas"] >= 1
    assert _estado(e, OfertaListaEspera, o2.id) == "expirada"
    assert _estado(e, ListaEspera, e2) == "en_cola"
    [o3] = _ofertas(e, e3)
    assert (o3.estado, o3.turno_liberado_id) == ("pendiente", hueco)


def test_nadie_mas_disponible(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    eid = e.entrada(e.paciente()[0])
    e.hueco(20)
    _correr(e, fake, e.ahora)
    _correr(e, fake, e.ahora + timedelta(minutes=31))  # vence; nadie más elegible
    _correr(e, fake, e.ahora + timedelta(minutes=62))
    [o] = _ofertas(e, eid)  # el mismo hueco nunca dos veces a la misma entrada
    assert o.estado == "expirada" and _estado(e, ListaEspera, eid) == "en_cola"


def test_sesion_caida_anula_y_corta_la_corrida(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    fake.estado_sesion = "caida"
    e1, e2 = e.entrada(e.paciente()[0]), e.entrada(e.paciente()[0])
    e.hueco(20)
    e.hueco(26)
    c = _correr(e, fake, e.ahora)
    assert (c["ofertas"], c["fallidas"]) == (0, 1)
    [o1] = _ofertas(e, e1)
    assert o1.estado == "anulada" and _estado(e, ListaEspera, e1) == "en_cola"
    assert _ofertas(e, e2) == []  # la corrida se cortó: no quemó al resto de la cola
    with session_factory() as s:
        msg = s.get(MensajeWhatsApp, o1.mensaje_id)
        assert (msg.estado, msg.motivo_error, msg.requiere_atencion) == (
            "error", "sesion_no_activa", True)  # fmt: skip


def test_corrida_repetida_no_duplica(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    e1, e2 = e.entrada(e.paciente()[0]), e.entrada(e.paciente()[0])
    e.hueco(20)
    _correr(e, fake, e.ahora)
    _correr(e, fake, e.ahora + timedelta(minutes=5))
    assert len(_ofertas(e, e1)) + len(_ofertas(e, e2)) == 1
