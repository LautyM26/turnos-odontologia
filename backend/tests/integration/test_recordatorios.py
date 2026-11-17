"""Job de recordatorios (C-15 5.1, D5). Un test por escenario de la spec. PG16 real, sintético."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.domain.agenda.turnos import Turno
from app.domain.whatsapp.models import MensajeWhatsApp
from app.infrastructure.whatsapp.fake import FakeMensajeria
from app.infrastructure.whatsapp.puerto import GatewayNoDisponible, NoConfigurado
from app.jobs.recordatorios import enviar_recordatorios
from tests.integration.conftest_whatsapp import nuevo_ahora, settings_wa, turno_wa


def _recordatorios(session_factory, turno_id: int) -> list[MensajeWhatsApp]:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return list(
            session.scalars(
                select(MensajeWhatsApp).where(
                    MensajeWhatsApp.turno_id == turno_id,
                    MensajeWhatsApp.plantilla == "recordatorio_24h",
                )
            )
        )


def _correr(session_factory, fake, ahora, dormidas=None, **kw):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return enviar_recordatorios(
            session, fake, settings_wa(**kw), ahora,
            dormir=(dormidas.append if dormidas is not None else lambda s: None),
        )  # fmt: skip


def test_recordatorio_enviado_una_sola_vez(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, fake = nuevo_ahora(), FakeMensajeria()
    tid, _ = turno_wa(session_factory, turnos_data, ahora + timedelta(hours=22))
    _correr(session_factory, fake, ahora)
    _correr(session_factory, fake, ahora)
    assert len(fake.enviados) == 1
    sesion, telefono, texto = fake.enviados[0]
    assert sesion == f"clinica-{turnos_data['a']}" and telefono == "+5491100000001"
    assert "1 para confirmar" in texto
    [m] = _recordatorios(session_factory, tid)
    assert m.estado == "enviado" and m.direccion == "saliente" and m.intentos == 1
    assert m.costo_ars == Decimal("12.50") and m.id_externo and m.texto == texto
    assert m.requiere_atencion is False


def test_turno_fuera_de_ventana_no_recibe(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, fake = nuevo_ahora(), FakeMensajeria()
    tid, _ = turno_wa(session_factory, turnos_data, ahora + timedelta(hours=30))
    _correr(session_factory, fake, ahora)
    assert fake.enviados == [] and _recordatorios(session_factory, tid) == []


def test_turno_no_reservado_no_recibe(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, fake = nuevo_ahora(), FakeMensajeria()
    ids = [
        turno_wa(session_factory, turnos_data, ahora + timedelta(hours=h), estado=e)[0]
        for h, e in ((10, "cancelado"), (11, "confirmado"))
    ]
    _correr(session_factory, fake, ahora)
    assert fake.enviados == []
    assert all(_recordatorios(session_factory, t) == [] for t in ids)


def test_ritmo_de_envio_limitado(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, fake, dormidas = nuevo_ahora(), FakeMensajeria(), []
    for h in (5, 6, 7):
        turno_wa(session_factory, turnos_data, ahora + timedelta(hours=h))
    _correr(session_factory, fake, ahora, dormidas, whatsapp_envios_por_minuto=20)
    assert len(fake.enviados) == 3
    assert dormidas == [3.0, 3.0]  # sin espera antes del primero


def test_sesion_caida_va_a_la_bandeja_sin_tocar_el_turno(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, fake = nuevo_ahora(), FakeMensajeria()
    fake.estado_sesion = "caida"
    tid, _ = turno_wa(session_factory, turnos_data, ahora + timedelta(hours=20))
    _correr(session_factory, fake, ahora)
    [m] = _recordatorios(session_factory, tid)
    assert (m.estado, m.motivo_error, m.intentos) == ("error", "sesion_no_activa", 1)
    assert m.requiere_atencion is True and m.costo_ars == Decimal("0")
    with session_factory() as session:
        assert session.get(Turno, tid).estado == "reservado"


def test_reintento_exitoso_reutiliza_la_fila(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, fake = nuevo_ahora(), FakeMensajeria()
    fake.fallar_con(GatewayNoDisponible("timeout"))
    tid, _ = turno_wa(session_factory, turnos_data, ahora + timedelta(hours=20))
    _correr(session_factory, fake, ahora)
    fake.fallar_con(None)
    _correr(session_factory, fake, ahora + timedelta(minutes=15))
    [m] = _recordatorios(session_factory, tid)
    assert (m.estado, m.intentos, m.motivo_error) == ("enviado", 2, None)
    assert m.requiere_atencion is False and len(fake.enviados) == 1


def test_tope_de_intentos(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, fake = nuevo_ahora(), FakeMensajeria()
    fake.fallar_con(GatewayNoDisponible("timeout"))
    tid, _ = turno_wa(session_factory, turnos_data, ahora + timedelta(hours=20))
    for i in range(5):
        _correr(session_factory, fake, ahora + timedelta(minutes=15 * i), whatsapp_max_intentos=2)
    [m] = _recordatorios(session_factory, tid)
    assert (m.estado, m.intentos) == ("error", 2)


def test_paciente_sin_telefono_sin_reintento(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    ahora, fake = nuevo_ahora(), FakeMensajeria()
    tid, _ = turno_wa(session_factory, turnos_data, ahora + timedelta(hours=8), telefono=None)
    _correr(session_factory, fake, ahora)
    _correr(session_factory, fake, ahora + timedelta(minutes=15))
    [m] = _recordatorios(session_factory, tid)
    assert (m.estado, m.motivo_error, m.intentos) == ("error", "sin_telefono", 0)
    assert m.telefono is None and m.requiere_atencion is True and fake.enviados == []


def test_sin_gateway_queda_no_configurado_y_se_reintenta_al_configurar(
    session_factory, turnos_data
) -> None:  # type: ignore[no-untyped-def]
    ahora = nuevo_ahora()
    tid, _ = turno_wa(session_factory, turnos_data, ahora + timedelta(hours=8))
    for i in range(4):  # varias corridas sin gateway no agotan los intentos
        _correr(session_factory, NoConfigurado("sin gateway"), ahora + timedelta(minutes=i))
    [m] = _recordatorios(session_factory, tid)
    assert (m.estado, m.motivo_error, m.intentos) == ("error", "no_configurado", 0)
    fake = FakeMensajeria()
    _correr(session_factory, fake, ahora + timedelta(minutes=30))
    [m] = _recordatorios(session_factory, tid)
    assert m.estado == "enviado" and len(fake.enviados) == 1
