"""Aceptar y rechazar la oferta por WhatsApp (C-16 4.3 + 3.2, D5/D6). PG16 real, sintético."""

from datetime import timedelta

from sqlalchemy import select

from app.domain.agenda.turnos import Turno, TurnoTransicion
from app.domain.lista_espera.models import ListaEspera, OfertaListaEspera
from app.domain.whatsapp.models import MensajeWhatsApp
from app.infrastructure.whatsapp.fake import FakeMensajeria
from app.jobs.lista_espera import procesar_lista_espera
from tests.integration.conftest_lista import escenario, responder, settings_le
from tests.integration.conftest_whatsapp import recordatorio_enviado


def _ofertar(e, fake, ahora=None):  # type: ignore[no-untyped-def]
    with e.sf() as s:
        procesar_lista_espera(s, fake, settings_le(), ahora or e.ahora)


def _oferta(e, eid: int) -> OfertaListaEspera:  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return s.scalars(
            select(OfertaListaEspera)
            .where(OfertaListaEspera.lista_espera_id == eid)
            .order_by(OfertaListaEspera.id.desc())
        ).first()


def _salientes(e, tel: str) -> list[str]:  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return list(s.scalars(select(MensajeWhatsApp.plantilla).where(
            MensajeWhatsApp.telefono == tel, MensajeWhatsApp.direccion == "saliente",
        ).order_by(MensajeWhatsApp.id)))  # fmt: skip


def _preparar(session_factory, td):  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, td), FakeMensajeria()
    pid, tel = e.paciente()
    return e, fake, pid, tel, e.entrada(pid)


def test_aceptar_reasigna_el_hueco(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, pid, tel, eid = _preparar(session_factory, turnos_data)
    hueco = e.hueco(20)
    _ofertar(e, fake)
    r = responder(e, tel, "1", e.ahora + timedelta(minutes=5), fake)
    assert r == "oferta_aceptada"
    o = _oferta(e, eid)
    assert o.estado == "aceptada" and o.turno_creado_id
    with session_factory() as s:
        nuevo = s.get(Turno, o.turno_creado_id)
        viejo = s.get(Turno, hueco)
        assert (nuevo.paciente_id, nuevo.origen, nuevo.estado) == (pid, "lista_espera", "reservado")
        assert (nuevo.inicio, nuevo.profesional_id, nuevo.sillon_id) == (
            viejo.inicio, viejo.profesional_id, viejo.sillon_id)  # fmt: skip
        assert s.get(ListaEspera, eid).estado == "aceptado"
    assert _salientes(e, tel) == ["oferta_hueco", "oferta_aceptada"]


def test_aceptar_adelanta_y_libera_el_turno_viejo(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    pid, tel = e.paciente()
    viejo = e.turno(24 * 8, pid, prof="q", sillon="s2")
    e.entrada(pid, turno_a_adelantar_id=viejo)
    otro_pid, otro_tel = e.paciente()
    otro = e.entrada(otro_pid)  # espera y recibirá el hueco del turno viejo
    e.hueco(20)
    _ofertar(e, fake)
    assert responder(e, tel, "si", e.ahora + timedelta(minutes=5), fake) == "oferta_aceptada"
    with session_factory() as s:
        assert s.get(Turno, viejo).estado == "cancelado"
        [tr] = s.scalars(select(TurnoTransicion).where(TurnoTransicion.turno_id == viejo))
        assert (tr.hacia, tr.actor_tipo, tr.actor_usuario_id) == (
            "cancelado", "paciente_whatsapp", None)  # fmt: skip
    _ofertar(e, fake, e.ahora + timedelta(minutes=6))  # cascada: el horario del viejo
    o = _oferta(e, otro)
    assert o is not None and o.turno_liberado_id == viejo and o.estado == "pendiente"


def test_hueco_tomado_en_el_medio(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, pid, tel, eid = _preparar(session_factory, turnos_data)
    e.hueco(20)
    _ofertar(e, fake)
    e.turno(20, e.paciente()[0])  # recepción da ese horario a otro
    assert responder(e, tel, "1", e.ahora + timedelta(minutes=5), fake) == "oferta_no_disponible"
    o = _oferta(e, eid)
    assert o.estado == "anulada" and o.turno_creado_id is None
    with session_factory() as s:
        assert s.get(ListaEspera, eid).estado == "en_cola"
    assert _salientes(e, tel)[-1] == "oferta_no_disponible"


def test_aceptar_oferta_vencida(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, pid, tel, eid = _preparar(session_factory, turnos_data)
    e.hueco(20)
    _ofertar(e, fake)
    tarde = e.ahora + timedelta(minutes=40)  # venció y el job todavía no pasó
    assert responder(e, tel, "sí", tarde, fake) == "oferta_no_disponible"
    assert _oferta(e, eid).estado == "expirada"
    with session_factory() as s:
        assert s.get(ListaEspera, eid).estado == "en_cola"


def test_rechazar(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, pid, tel, eid = _preparar(session_factory, turnos_data)
    sig_pid, _ = e.paciente()
    siguiente = e.entrada(sig_pid)
    e.hueco(20)
    _ofertar(e, fake)
    assert responder(e, tel, "no", e.ahora + timedelta(minutes=5), fake) == "oferta_rechazada"
    assert _oferta(e, eid).estado == "rechazada"
    assert _salientes(e, tel) == ["oferta_hueco"]  # sin respuesta automática
    _ofertar(e, fake, e.ahora + timedelta(minutes=6))
    assert _oferta(e, siguiente).estado == "pendiente"


def test_respuesta_a_oferta_y_no_al_recordatorio(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, pid, tel, eid = _preparar(session_factory, turnos_data)
    propio = e.turno(24 * 6, pid, prof="q", sillon="s2")
    recordatorio_enviado(session_factory, turnos_data, propio, pid, tel)  # primero
    e.hueco(20)
    _ofertar(e, fake)  # después: la oferta es lo más reciente
    assert responder(e, tel, "1", e.ahora + timedelta(minutes=5), fake) == "oferta_aceptada"
    with session_factory() as s:
        assert s.get(Turno, propio).estado == "reservado"  # el recordatorio no se tocó
