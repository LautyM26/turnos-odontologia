"""Reprogramación por enlace con el token de C-06 (C-17 4.1, D5). PG16 real, sintético."""

import secrets
from datetime import UTC, datetime, timedelta
from itertools import count

from sqlalchemy import select

from app.domain.agenda.reserva_publica import hash_token
from app.domain.agenda.turnos import Turno, TurnoTransicion
from tests.integration.conftest import make_test_client, paciente_sintetico

_dias = count(3)


def _reserva(session_factory, td, prof: str = "p") -> tuple[int, str]:  # type: ignore[no-untyped-def]
    """Turno reservado online con token en claro (como lo deja C-06)."""
    token = secrets.token_urlsafe(32)
    inicio = (datetime.now(UTC) + timedelta(days=next(_dias))).replace(
        hour=13, minute=0, second=0, microsecond=0)  # fmt: skip
    with session_factory() as s:
        pac = paciente_sintetico(td["a"])
        s.add(pac)
        s.flush()
        t = Turno(clinica_id=td["a"], profesional_id=td[prof], sillon_id=td["s1"],
                  paciente_id=pac.id, prestacion_id=td["prest_a"], duracion_min=30,
                  inicio=inicio, fin=inicio + timedelta(minutes=30), origen="enlace",
                  token_publico_hash=hash_token(token))  # fmt: skip
        s.add(t)
        s.commit()
        return t.id, token


def test_opciones_sin_sillones_y_sin_jwt(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    c = make_test_client(session_factory, monkeypatch)
    _, token = _reserva(session_factory, turnos_data)
    r = c.get(f"/api/public/reservas/{token}/opciones")
    assert r.status_code == 200, r.text
    assert 1 <= len(r.json()) <= 3 and set(r.json()[0]) == {"inicio", "fin"}
    assert c.get("/api/public/reservas/token-que-no-existe/opciones").status_code == 404


def test_reprogramar_y_el_token_sigue_al_nuevo(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    c = make_test_client(session_factory, monkeypatch)
    tid, token = _reserva(session_factory, turnos_data)
    destino = c.get(f"/api/public/reservas/{token}/opciones").json()[0]["inicio"]
    r = c.post(f"/api/public/reservas/{token}/reprogramar", json={"inicio": destino})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "reservado"
    assert datetime.fromisoformat(r.json()["inicio"]) == datetime.fromisoformat(destino)
    with session_factory() as s:
        viejo = s.get(Turno, tid)
        [tr] = s.scalars(select(TurnoTransicion).where(TurnoTransicion.turno_id == tid))
    assert viejo.estado == "cancelado" and viejo.token_publico_hash is None
    assert (tr.actor_tipo, tr.actor_usuario_id) == ("paciente_enlace", None)
    ver = c.get(f"/api/public/reservas/{token}")
    assert datetime.fromisoformat(ver.json()["inicio"]) == datetime.fromisoformat(destino)
    cancelar = c.post(f"/api/public/reservas/{token}/cancelar")
    assert cancelar.status_code == 200 and cancelar.json()["estado"] == "cancelado"


def test_inicio_que_no_es_opcion_422(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    c = make_test_client(session_factory, monkeypatch)
    tid, token = _reserva(session_factory, turnos_data)
    lejos = (datetime.now(UTC) + timedelta(days=10)).isoformat()  # libre, pero no es opción
    r = c.post(f"/api/public/reservas/{token}/reprogramar", json={"inicio": lejos})
    assert r.status_code == 422
    r = c.post(f"/api/public/reservas/{token}/reprogramar",
               json={"inicio": lejos, "sillon_id": 1})  # fmt: skip
    assert r.status_code == 422  # extra='forbid'
    with session_factory() as s:
        assert s.get(Turno, tid).estado == "reservado"


def test_ocupado_409_con_alternativas(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    c = make_test_client(session_factory, monkeypatch)
    tid, token = _reserva(session_factory, turnos_data)
    elegido = c.get(f"/api/public/reservas/{token}/opciones").json()[0]["inicio"]
    inicio = datetime.fromisoformat(elegido)
    with session_factory() as s:  # alguien toma ese horario de P en otro sillón
        s.add(Turno(clinica_id=turnos_data["a"], profesional_id=turnos_data["p"],
                    sillon_id=turnos_data["s2"], paciente_id=turnos_data["pac_a"],
                    prestacion_id=turnos_data["prest_a"], duracion_min=30, inicio=inicio,
                    fin=inicio + timedelta(minutes=30)))  # fmt: skip
        s.commit()
    r = c.post(f"/api/public/reservas/{token}/reprogramar", json={"inicio": elegido})
    assert r.status_code == 409, r.text
    alternativas = [datetime.fromisoformat(a["inicio"]) for a in r.json()["alternativas"]]
    assert alternativas and inicio not in alternativas
    with session_factory() as s:
        assert s.get(Turno, tid).estado == "reservado"
