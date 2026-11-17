"""Chatbot de reprogramación por WhatsApp (C-17 3.1, D4). Un test por escenario. PG16 real."""

from datetime import timedelta

from sqlalchemy import select

from app.domain.agenda.turnos import Turno
from app.domain.reprogramacion.models import ConversacionWA
from app.domain.whatsapp.models import MensajeWhatsApp
from app.infrastructure.whatsapp.fake import FakeMensajeria
from tests.integration.conftest_lista import escenario, responder
from tests.integration.conftest_whatsapp import recordatorio_enviado


def _preparar(session_factory, td, prof: str = "p"):  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, td), FakeMensajeria()
    pid, tel = e.paciente()
    tid = e.turno(20, pid, prof=prof)
    recordatorio_enviado(session_factory, td, tid, pid, tel)
    return e, fake, tel, tid


def _salientes(e, tel: str) -> list[str]:  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return list(s.scalars(select(MensajeWhatsApp.plantilla).where(
            MensajeWhatsApp.telefono == tel, MensajeWhatsApp.direccion == "saliente",
            MensajeWhatsApp.plantilla != "recordatorio_24h",
        ).order_by(MensajeWhatsApp.id)))  # fmt: skip


def _conv(e, tel: str) -> ConversacionWA:  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return s.scalars(select(ConversacionWA).where(ConversacionWA.telefono == tel)
                         .order_by(ConversacionWA.id.desc())).first()  # fmt: skip


def _estado(e, tid: int) -> str:  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return s.get(Turno, tid).estado


def _ultimo_entrante(e, tel: str) -> MensajeWhatsApp:  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return s.scalars(select(MensajeWhatsApp).where(
            MensajeWhatsApp.telefono == tel, MensajeWhatsApp.direccion == "entrante")
            .order_by(MensajeWhatsApp.id.desc())).first()  # fmt: skip


def test_tres_abre_el_chatbot(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, tel, tid = _preparar(session_factory, turnos_data)
    assert responder(e, tel, "3", e.ahora, fake) == "chatbot"
    assert _estado(e, tid) == "reservado"
    conv = _conv(e, tel)
    assert conv.estado == "eligiendo" and len(conv.opciones) == 3
    [texto] = [t for _, t_, t in fake.enviados if t_ == tel]
    assert "1) " in texto and "2) " in texto and "3) " in texto and "0 para dejar" in texto
    assert "Profesional P Sintetico" in texto


def test_sin_huecos_va_a_la_bandeja(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, tel, tid = _preparar(session_factory, turnos_data, prof="prof_r")  # sin agenda
    assert responder(e, tel, "reprogramar", e.ahora, fake) == "bandeja"
    assert _salientes(e, tel) == ["reprogramacion"]
    assert _ultimo_entrante(e, tel).requiere_atencion is True
    assert _conv(e, tel) is None


def test_elegir_y_confirmar_reprograma(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, tel, tid = _preparar(session_factory, turnos_data)
    responder(e, tel, "3", e.ahora, fake)
    opcion2 = _conv(e, tel).opciones[1]["inicio"]
    assert responder(e, tel, "2", e.ahora + timedelta(minutes=1), fake) == "chatbot_confirmar"
    assert _estado(e, tid) == "reservado"  # "2" fue la opción 2, no "cancelar mi turno"
    r = responder(e, tel, "si", e.ahora + timedelta(minutes=2), fake)
    assert r == "chatbot_reprogramado"
    conv = _conv(e, tel)
    assert (conv.estado, conv.resultado) == ("cerrada", "reprogramado")
    assert _estado(e, tid) == "cancelado"
    with e.sf() as s:
        nuevo = s.get(Turno, conv.turno_nuevo_id)
        assert nuevo.inicio.isoformat() == opcion2 and nuevo.estado == "reservado"
    assert _salientes(e, tel) == ["reprogramacion_opciones", "reprogramacion_confirmar",
                                  "reprogramacion_hecha"]  # fmt: skip


def test_arrepentirse(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, tel, tid = _preparar(session_factory, turnos_data)
    responder(e, tel, "3", e.ahora, fake)
    responder(e, tel, "1", e.ahora, fake)
    assert responder(e, tel, "no", e.ahora, fake) == "chatbot_sin_cambios"
    assert _estado(e, tid) == "reservado"
    assert (_conv(e, tel).estado, _conv(e, tel).resultado) == ("cerrada", "sin_cambios")
    assert _salientes(e, tel)[-1] == "reprogramacion_sin_cambios"


def test_numero_fuera_de_rango(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, tel, tid = _preparar(session_factory, turnos_data)
    responder(e, tel, "3", e.ahora, fake)
    assert responder(e, tel, "7", e.ahora, fake) == "bandeja"
    assert _conv(e, tel).estado == "eligiendo"
    assert _ultimo_entrante(e, tel).requiere_atencion is True


def test_hueco_tomado_en_el_medio_ofrece_alternativas(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, tel, tid = _preparar(session_factory, turnos_data)
    responder(e, tel, "3", e.ahora, fake)
    responder(e, tel, "1", e.ahora, fake)
    elegido = _conv(e, tel).opciones[0]["inicio"]
    e.turno(2, e.paciente()[0], sillon="s2")  # recepción da ese horario de P a otro paciente
    assert responder(e, tel, "si", e.ahora, fake) == "chatbot_alternativas"
    conv = _conv(e, tel)
    assert conv.estado == "eligiendo" and elegido not in [o["inicio"] for o in conv.opciones]
    assert _estado(e, tid) == "reservado"
    textos = [t for _, t_, t in fake.enviados if t_ == tel]
    assert textos[-1].startswith("Ese horario se ocupó.")


def test_conversacion_vencida_no_cancela(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, tel, tid = _preparar(session_factory, turnos_data)
    responder(e, tel, "3", e.ahora, fake)
    r = responder(e, tel, "2", e.ahora + timedelta(minutes=40), fake)
    assert r == "chatbot_vencida"
    assert _estado(e, tid) == "reservado"
    assert (_conv(e, tel).estado, _conv(e, tel).resultado) == ("cerrada", "vencida")
    assert _salientes(e, tel)[-1] == "reprogramacion_vencida"


def test_evento_duplicado_sin_efecto(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake, tel, tid = _preparar(session_factory, turnos_data)
    responder(e, tel, "3", e.ahora, fake)
    responder(e, tel, "1", e.ahora, fake)
    assert responder(e, tel, "si", e.ahora, fake, id_externo="IN-c17-dup") == "chatbot_reprogramado"
    assert responder(e, tel, "si", e.ahora, fake, id_externo="IN-c17-dup") == "duplicado"
    with e.sf() as s:
        assert len(list(s.scalars(select(Turno).where(Turno.origen == "whatsapp",
                                                      Turno.prestacion_id == e.prest)))) == 1
