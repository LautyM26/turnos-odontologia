"""Bandeja de fallos, costos y mensajes por turno (C-15 7.2, D9). PG16 real, sintético."""

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.whatsapp.models import MensajeWhatsApp
from tests.integration.conftest import bearer, make_test_client
from tests.integration.conftest_whatsapp import nuevo_ahora, telefono_unico, turno_wa


def _cliente(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return make_test_client(session_factory, monkeypatch)


def _msg(session_factory, clinica_id: int, **kw) -> int:  # type: ignore[no-untyped-def]
    cols = {"clinica_id": clinica_id, "direccion": "saliente", "telefono": telefono_unico(),
            "texto": "sintetico", "estado": "enviado", "plantilla": "confirmacion"}  # fmt: skip
    cols.update(kw)
    with session_factory() as session:
        m = MensajeWhatsApp(**cols)
        session.add(m)
        session.commit()
        return m.id


def test_bandeja_lista_fallos_y_resolver(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    tid, pid = turno_wa(session_factory, td, nuevo_ahora())
    caido = _msg(session_factory, td["a"], turno_id=tid, paciente_id=pid, estado="error",
                 motivo_error="sesion_no_activa", requiere_atencion=True,
                 plantilla="recordatorio_24h")  # fmt: skip
    pedido = _msg(session_factory, td["a"], direccion="entrante", estado="recibido",
                  plantilla=None, intencion="reprogramar", requiere_atencion=True)  # fmt: skip
    ok = _msg(session_factory, td["a"])  # enviado: no va a la bandeja
    c = _cliente(session_factory, monkeypatch)
    h = bearer(c, "recepcion@test.test")
    r = c.get("/api/whatsapp/fallos", headers=h)
    assert r.status_code == 200, r.text
    ids = [f["id"] for f in r.json()]
    assert caido in ids and pedido in ids and ok not in ids
    fila = next(f for f in r.json() if f["id"] == caido)
    assert fila["motivo_error"] == "sesion_no_activa" and fila["turno_id"] == tid
    assert fila["paciente_nombre"] == "Paciente Sintetico" and fila["turno_inicio"]

    assert c.post(f"/api/whatsapp/fallos/{caido}/resolver", headers=h).status_code == 200
    assert caido not in [f["id"] for f in c.get("/api/whatsapp/fallos", headers=h).json()]
    assert c.post(f"/api/whatsapp/fallos/{caido}/resolver", headers=h).status_code == 404
    assert c.post(f"/api/whatsapp/fallos/{ok}/resolver", headers=h).status_code == 404


def test_bandeja_aislada_por_clinica(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    de_a = _msg(session_factory, td["a"], direccion="entrante", estado="recibido",
                plantilla=None, intencion="desconocida", requiere_atencion=True)  # fmt: skip
    c = _cliente(session_factory, monkeypatch)
    hb = bearer(c, "recepcion-b@test.test")
    assert de_a not in [f["id"] for f in c.get("/api/whatsapp/fallos", headers=hb).json()]
    assert c.post(f"/api/whatsapp/fallos/{de_a}/resolver", headers=hb).status_code == 404


def test_odontologo_403(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    c = _cliente(session_factory, monkeypatch)
    h = bearer(c, "odonto@test.test")
    for url in ("/api/whatsapp/fallos", "/api/whatsapp/costos?desde=2031-05-01&hasta=2031-05-31",
                "/api/whatsapp/mensajes?turno_id=1"):
        assert c.get(url, headers=h).status_code == 403
    assert c.get("/api/whatsapp/fallos").status_code == 401


def test_costos_del_mes_en_ars(session_factory, monkeypatch, turnos_data, auth_data) -> None:  # type: ignore[no-untyped-def]
    a, b = turnos_data["a"], turnos_data["b"]
    mayo = datetime(2031, 5, 10, 15, tzinfo=UTC)
    for _ in range(3):
        _msg(session_factory, a, plantilla="recordatorio_24h", costo_ars=Decimal("12.50"),
             created_at=mayo)  # fmt: skip
    for _ in range(2):
        _msg(session_factory, a, direccion="entrante", estado="recibido", plantilla=None,
             intencion="confirmar", created_at=mayo)  # fmt: skip
    _msg(session_factory, b, costo_ars=Decimal("99.00"), created_at=mayo)  # otra clínica
    _msg(session_factory, a, costo_ars=Decimal("50.00"),
         created_at=datetime(2031, 6, 1, 12, tzinfo=UTC))  # fuera de rango  # fmt: skip
    c = _cliente(session_factory, monkeypatch)
    r = c.get("/api/whatsapp/costos?desde=2031-05-01&hasta=2031-05-31",
              headers=bearer(c, auth_data["admin_email"]))  # fmt: skip
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_ars"] == "37.50"
    detalle = {(d["plantilla"], d["direccion"]): d for d in body["detalle"]}
    assert detalle[("recordatorio_24h", "saliente")]["cantidad"] == 3
    assert detalle[("recordatorio_24h", "saliente")]["total_ars"] == "37.50"
    assert detalle[(None, "entrante")] == {"plantilla": None, "direccion": "entrante",
                                           "cantidad": 2, "total_ars": "0.00"}  # fmt: skip


def test_costos_rango_invalido_422(session_factory, monkeypatch, auth_data) -> None:  # type: ignore[no-untyped-def]
    c = _cliente(session_factory, monkeypatch)
    h = bearer(c, auth_data["admin_email"])
    for rango in ("desde=2031-05-31&hasta=2031-05-01", "desde=2030-01-01&hasta=2031-05-01"):
        assert c.get(f"/api/whatsapp/costos?{rango}", headers=h).status_code == 422


def test_mensajes_de_un_turno(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    tid, pid = turno_wa(session_factory, td, nuevo_ahora())
    mid = _msg(session_factory, td["a"], turno_id=tid, paciente_id=pid,
               plantilla="recordatorio_24h", costo_ars=Decimal("12.50"))  # fmt: skip
    tid_b, _ = turno_wa(session_factory, td, nuevo_ahora(), clinica="b")
    c = _cliente(session_factory, monkeypatch)
    h = bearer(c, "recepcion@test.test")
    r = c.get(f"/api/whatsapp/mensajes?turno_id={tid}", headers=h)
    assert r.status_code == 200
    assert [m["id"] for m in r.json()] == [mid] and r.json()[0]["costo_ars"] == "12.50"
    assert c.get(f"/api/whatsapp/mensajes?turno_id={tid_b}", headers=h).status_code == 404
