"""Webhook del gateway WhatsApp (C-15 6.3, D6): HMAC, parseo y despacho. PG16 real, sintético."""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from itertools import count

import pytest
from sqlalchemy import func, select

from app.domain.agenda.turnos import Turno
from app.domain.whatsapp.models import MensajeWhatsApp, WhatsappSesion
from app.infrastructure.whatsapp.fake import FakeMensajeria
from tests.integration.conftest import make_test_client
from tests.integration.conftest_whatsapp import recordatorio_enviado, telefono_unico, turno_wa

CLAVE = "hmac-sintetica-webhook"
URL = "/api/webhooks/whatsapp"


@pytest.fixture()
def fake() -> FakeMensajeria:
    return FakeMensajeria()


@pytest.fixture()
def wa(session_factory, monkeypatch, fake):  # type: ignore[no-untyped-def]
    from app.api.whatsapp import mensajeria_wa

    monkeypatch.setenv("WHATSAPP_WEBHOOK_HMAC_KEY", CLAVE)
    client = make_test_client(session_factory, monkeypatch)
    client.app.dependency_overrides[mensajeria_wa] = lambda: fake
    return client


def _post(client, evento: dict, clave: str | None = CLAVE, firma: str | None = None):  # type: ignore[no-untyped-def]
    cuerpo = json.dumps(evento).encode()
    headers = {"Content-Type": "application/json"}
    if clave is not None:
        calculada = hmac.new(clave.encode(), cuerpo, hashlib.sha512).hexdigest()
        headers["X-Webhook-Hmac"] = firma or calculada
        headers["X-Webhook-Hmac-Algorithm"] = "sha512"
    return client.post(URL, content=cuerpo, headers=headers)


def _mensaje(sesion: str, tel: str, texto: str, **payload) -> dict:  # type: ignore[no-untyped-def]
    base = {"id": f"true_{tel}_{texto}_{datetime.now(UTC).timestamp()}",
            "from": tel.lstrip("+") + "@c.us", "fromMe": False, "body": texto}  # fmt: skip
    base.update(payload)
    return {"event": "message", "session": sesion, "engine": "WEBJS", "payload": base,
            "environment": {"version": "x"}, "me": {"id": "5491100009999@c.us"}}  # fmt: skip


_horas = count(0)


def _preparar(session_factory, td):  # type: ignore[no-untyped-def]
    tel = telefono_unico()
    inicio = datetime.now(UTC) + timedelta(days=3, hours=next(_horas))
    tid, pid = turno_wa(session_factory, td, inicio, telefono=tel,
                        sillon="s2", prof="q")  # fmt: skip
    recordatorio_enviado(session_factory, td, tid, pid, tel)
    return tel, tid


def _estado(session_factory, tid):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return session.get(Turno, tid).estado


def _n_entrantes(session_factory, tel: str) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return session.scalar(select(func.count()).select_from(MensajeWhatsApp).where(
            MensajeWhatsApp.telefono == tel, MensajeWhatsApp.direccion == "entrante"))  # fmt: skip


def test_firma_valida_confirma_sin_jwt(wa, session_factory, turnos_data, fake) -> None:  # type: ignore[no-untyped-def]
    tel, tid = _preparar(session_factory, turnos_data)
    r = _post(wa, _mensaje(f"clinica-{turnos_data['a']}", tel, "SI"))
    assert r.status_code == 200, r.text
    assert r.json() == {"resultado": "confirmado"}
    assert _estado(session_factory, tid) == "confirmado"
    assert len(fake.enviados) == 1


def test_firma_invalida_401_sin_efectos(wa, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    tel, tid = _preparar(session_factory, turnos_data)
    evento = _mensaje(f"clinica-{turnos_data['a']}", tel, "SI")
    assert _post(wa, evento, firma="0" * 128).status_code == 401
    assert _post(wa, evento, clave="otra-clave").status_code == 401
    assert _post(wa, evento, clave=None).status_code == 401
    assert _estado(session_factory, tid) == "reservado"
    assert _n_entrantes(session_factory, tel) == 0


def test_sin_secreto_configurado_503(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("WHATSAPP_WEBHOOK_HMAC_KEY", raising=False)
    client = make_test_client(session_factory, monkeypatch)
    tel, tid = _preparar(session_factory, turnos_data)
    assert _post(client, _mensaje(f"clinica-{turnos_data['a']}", tel, "SI")).status_code == 503
    assert _estado(session_factory, tid) == "reservado"


@pytest.mark.parametrize("sesion", ["default", "clinica-999999", "clinica-abc"])
def test_sesion_que_no_es_de_ninguna_clinica(wa, session_factory, sesion) -> None:  # type: ignore[no-untyped-def]
    tel = telefono_unico()
    r = _post(wa, _mensaje(sesion, tel, "SI"))
    assert r.status_code == 200 and r.json() == {"resultado": "ignorado"}
    assert _n_entrantes(session_factory, tel) == 0


def test_evento_desconocido_y_propio_ignorados(wa, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    a, tel = turnos_data["a"], telefono_unico()
    otro = {"event": "presence.update", "session": f"clinica-{a}", "payload": {}}
    assert _post(wa, otro).json() == {"resultado": "ignorado"}
    assert _post(wa, _mensaje(f"clinica-{a}", tel, "SI", fromMe=True)).json() == {
        "resultado": "ignorado"
    }
    grupo = _mensaje(f"clinica-{a}", tel, "SI", **{"from": "120363000000000001@g.us"})
    assert _post(wa, grupo).json() == {"resultado": "ignorado"}
    assert _n_entrantes(session_factory, tel) == 0


@pytest.mark.parametrize("falta", ["id", "from"])
def test_payload_incompleto_422(wa, turnos_data, falta) -> None:  # type: ignore[no-untyped-def]
    evento = _mensaje(f"clinica-{turnos_data['a']}", telefono_unico(), "SI")
    del evento["payload"][falta]
    assert _post(wa, evento).status_code == 422


def test_json_invalido_422(wa) -> None:  # type: ignore[no-untyped-def]
    cuerpo = b"no-es-json"
    firma = hmac.new(CLAVE.encode(), cuerpo, hashlib.sha512).hexdigest()
    r = wa.post(URL, content=cuerpo, headers={"X-Webhook-Hmac": firma})
    assert r.status_code == 422


def test_ack_y_estado_de_sesion_por_webhook(wa, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    a = turnos_data["a"]
    tel, tid = _preparar(session_factory, turnos_data)
    with session_factory() as session:
        ext = session.scalars(select(MensajeWhatsApp.id_externo).where(
            MensajeWhatsApp.turno_id == tid)).one()  # fmt: skip
    ack = {"event": "message.ack", "session": f"clinica-{a}",
           "payload": {"id": ext, "from": "x@c.us", "fromMe": True, "ack": 3, "ackName": "READ"}}
    assert _post(wa, ack).status_code == 200
    estado = {"event": "session.status", "session": f"clinica-{a}",
              "me": {"id": "5491100009999@c.us", "pushName": "~"},
              "payload": {"status": "SCAN_QR_CODE", "statuses": [], "data": None}}  # fmt: skip
    assert _post(wa, estado).status_code == 200
    with session_factory() as session:
        assert session.scalars(select(MensajeWhatsApp.estado).where(
            MensajeWhatsApp.id_externo == ext)).one() == "leido"  # fmt: skip
        assert session.get(WhatsappSesion, a).estado == "escanear_qr"
