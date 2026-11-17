"""Respuestas del paciente, acuses y estado de sesión (C-15 6.1, D2/D7). PG16 real, sintético."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.domain.agenda.turnos import Turno, TurnoTransicion, crear_turno
from app.domain.whatsapp.models import MensajeWhatsApp, WhatsappSesion
from app.domain.whatsapp.servicios import (
    procesar_ack,
    procesar_estado_sesion,
    procesar_mensaje_entrante,
)
from app.infrastructure.whatsapp.fake import FakeMensajeria
from tests.integration.conftest_whatsapp import (
    nuevo_ahora,
    recordatorio_enviado,
    telefono_unico,
    turno_wa,
)


def _escenario(session_factory, td, clinica: str = "a", estado: str = "reservado"):  # type: ignore[no-untyped-def]
    ahora = nuevo_ahora()
    tel = telefono_unico()
    tid, pid = turno_wa(session_factory, td, ahora + timedelta(hours=20), clinica=clinica,
                        estado=estado, telefono=tel)  # fmt: skip
    recordatorio_enviado(session_factory, td, tid, pid, tel, clinica=clinica)
    return ahora, tel, tid


def _entrante(session_factory, clinica_id, tel, texto, ahora, fake, id_externo=None):  # type: ignore[no-untyped-def]
    from decimal import Decimal

    with session_factory() as session:
        return procesar_mensaje_entrante(
            session, clinica_id, id_externo or f"IN-{uuid4()}", tel, texto, ahora, fake,
            Decimal("12.50"),
        )  # fmt: skip


def _estado(session_factory, tid: int) -> str:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return session.get(Turno, tid).estado


def _entrantes(session_factory, tel: str) -> list[MensajeWhatsApp]:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return list(session.scalars(select(MensajeWhatsApp).where(
            MensajeWhatsApp.telefono == tel, MensajeWhatsApp.direccion == "entrante")))  # fmt: skip


def _respuestas(session_factory, tel: str) -> list[str]:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return list(session.scalars(select(MensajeWhatsApp.plantilla).where(
            MensajeWhatsApp.telefono == tel, MensajeWhatsApp.direccion == "saliente",
            MensajeWhatsApp.plantilla != "recordatorio_24h",
        ).order_by(MensajeWhatsApp.id)))  # fmt: skip


def test_si_confirma_el_turno(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, tel, tid = _escenario(session_factory, turnos_data)
    fake = FakeMensajeria()
    assert _entrante(session_factory, turnos_data["a"], tel, "Sí!", ahora, fake) == "confirmado"
    assert _estado(session_factory, tid) == "confirmado"
    with session_factory() as session:
        [tr] = session.scalars(select(TurnoTransicion).where(TurnoTransicion.turno_id == tid))
    assert (tr.desde, tr.hacia, tr.actor_tipo, tr.actor_usuario_id) == (
        "reservado", "confirmado", "paciente_whatsapp", None,
    )  # fmt: skip
    [m] = _entrantes(session_factory, tel)
    assert (m.intencion, m.turno_id, m.estado, m.requiere_atencion) == (
        "confirmar", tid, "recibido", False,
    )  # fmt: skip
    assert m.costo_ars == 0
    assert _respuestas(session_factory, tel) == ["confirmacion"]
    assert len(fake.enviados) == 1 and "confirmado" in fake.enviados[0][2]


def test_dos_cancela_y_libera_el_hueco(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    ahora, tel, tid = _escenario(session_factory, td)
    fake = FakeMensajeria()
    assert _entrante(session_factory, td["a"], tel, "2", ahora, fake) == "cancelado"
    assert _estado(session_factory, tid) == "cancelado"
    assert _respuestas(session_factory, tel) == ["cancelacion"]
    with session_factory() as session:
        t = session.get(Turno, tid)
        nuevo = crear_turno(session, td["a"], {
            "profesional_id": t.profesional_id, "sillon_id": t.sillon_id,
            "paciente_id": td["pac_a"], "prestacion_id": t.prestacion_id, "inicio": t.inicio,
        }, ahora=ahora)  # fmt: skip
        assert nuevo.estado == "reservado"


def test_reprogramar_va_a_la_bandeja_con_respuesta(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, tel, tid = _escenario(session_factory, turnos_data)
    fake = FakeMensajeria()
    resultado = _entrante(session_factory, turnos_data["a"], tel, "reprogramar", ahora, fake)
    assert resultado == "bandeja"
    assert _estado(session_factory, tid) == "reservado"
    [m] = _entrantes(session_factory, tel)
    assert m.intencion == "reprogramar" and m.requiere_atencion is True
    assert _respuestas(session_factory, tel) == ["reprogramacion"]


def test_texto_libre_va_a_la_bandeja_sin_respuesta(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, tel, tid = _escenario(session_factory, turnos_data)
    fake = FakeMensajeria()
    _entrante(session_factory, turnos_data["a"], tel, "hola, ¿a qué hora era?", ahora, fake)
    assert _estado(session_factory, tid) == "reservado"
    [m] = _entrantes(session_factory, tel)
    assert m.intencion == "desconocida" and m.requiere_atencion is True
    assert _respuestas(session_factory, tel) == [] and fake.enviados == []


def test_confirmar_un_cancelado_va_a_la_bandeja(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, tel, tid = _escenario(session_factory, turnos_data, estado="cancelado")
    fake = FakeMensajeria()
    assert _entrante(session_factory, turnos_data["a"], tel, "1", ahora, fake) == "bandeja"
    assert _estado(session_factory, tid) == "cancelado"
    with session_factory() as session:
        assert session.scalars(
            select(TurnoTransicion).where(TurnoTransicion.turno_id == tid)
        ).all() == []
    [m] = _entrantes(session_factory, tel)
    assert m.requiere_atencion is True and m.turno_id == tid
    assert fake.enviados == []


def test_numero_sin_recordatorio(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    tel, fake = telefono_unico(), FakeMensajeria()
    assert _entrante(session_factory, turnos_data["a"], tel, "SI", nuevo_ahora(), fake) == "bandeja"
    [m] = _entrantes(session_factory, tel)
    assert m.turno_id is None and m.requiere_atencion is True and fake.enviados == []


def test_mismo_telefono_en_otra_clinica_no_se_toca(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    ahora, tel, tid_b = _escenario(session_factory, td, clinica="b")  # solo B le recordó
    fake = FakeMensajeria()
    assert _entrante(session_factory, td["a"], tel, "SI", ahora, fake) == "bandeja"
    assert _estado(session_factory, tid_b) == "reservado"
    [m] = _entrantes(session_factory, tel)
    assert m.clinica_id == td["a"] and m.turno_id is None


def test_turno_ya_empezado_no_se_asocia(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, tel, tid = _escenario(session_factory, turnos_data)
    tarde = ahora + timedelta(hours=21)  # el turno empezó a las +20 h
    _entrante(session_factory, turnos_data["a"], tel, "SI", tarde, FakeMensajeria())
    assert _estado(session_factory, tid) == "reservado"
    [m] = _entrantes(session_factory, tel)
    assert m.turno_id is None


def test_acuses_monotonos(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    ahora, tel, tid = _escenario(session_factory, td)
    with session_factory() as session:
        m = session.scalars(select(MensajeWhatsApp).where(
            MensajeWhatsApp.turno_id == tid, MensajeWhatsApp.direccion == "saliente",
        )).one()  # fmt: skip
        ext = m.id_externo
    with session_factory() as session:
        procesar_ack(session, td["a"], ext, 3)  # leído
        procesar_ack(session, td["a"], ext, 2)  # entregado llega tarde: no retrocede
        procesar_ack(session, td["b"], ext, -1)  # otra clínica: no toca nada
        procesar_ack(session, td["a"], "DESCONOCIDO", 3)  # mensaje desconocido: ignorado
    with session_factory() as session:
        assert session.get(MensajeWhatsApp, m.id).estado == "leido"


def test_ack_de_error_va_a_la_bandeja(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    ahora, tel, tid = _escenario(session_factory, td)
    with session_factory() as session:
        m = session.scalars(select(MensajeWhatsApp).where(
            MensajeWhatsApp.turno_id == tid, MensajeWhatsApp.direccion == "saliente",
        )).one()  # fmt: skip
        procesar_ack(session, td["a"], m.id_externo, -1)
    with session_factory() as session:
        m = session.get(MensajeWhatsApp, m.id)
        assert (m.estado, m.motivo_error, m.requiere_atencion) == ("error", "otro", True)


def test_sesion_caida_actualiza_estado_y_alerta(session_factory, turnos_data, caplog) -> None:  # type: ignore[no-untyped-def]
    a, b = turnos_data["a"], turnos_data["b"]
    ahora = datetime(2031, 3, 10, 12, tzinfo=UTC)
    with session_factory() as session:
        procesar_estado_sesion(session, a, "activa", "+5491100009999", ahora)
        procesar_estado_sesion(session, b, "activa", None, ahora)
        with caplog.at_level(logging.WARNING, logger="turnos.whatsapp"):
            procesar_estado_sesion(session, a, "caida", None, ahora + timedelta(minutes=1))
    assert "whatsapp_sesion_caida" in caplog.text
    with session_factory() as session:
        sa_, sb = session.get(WhatsappSesion, a), session.get(WhatsappSesion, b)
        assert (sa_.estado, sa_.nombre) == ("caida", f"clinica-{a}")
        assert sa_.numero == "+5491100009999"  # el último número conocido se conserva
        assert sb.estado == "activa"
