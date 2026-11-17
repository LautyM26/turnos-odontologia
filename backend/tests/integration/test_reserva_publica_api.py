"""API pública de reserva (C-06): un test por escenario de ``public-booking``. PG16 real.

Sin JWT ni ``X-Clinica-Id``. Reloj fijo (``get_ahora``) en 2033-01-01; cada test usa un día
propio de 2033-08. ``make_test_client`` limpia el limiter, así los límites no se arrastran.
"""

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.api.turnos import get_ahora
from app.domain.agenda.models import Profesional
from app.domain.agenda.turnos import Turno
from app.domain.core.models import Clinica
from app.domain.pacientes.models import Paciente
from tests.integration.conftest import bearer, make_test_client

AHORA = datetime(2033, 1, 1, tzinfo=UTC)
SLUG = "clinica-piloto"
_dias = itertools.count(0)
_dnis = itertools.count(43_000_000)


def _dia() -> datetime:
    return datetime(2033, 8, 1, tzinfo=UTC) + timedelta(days=next(_dias))


def _cliente(session_factory, monkeypatch, ahora=AHORA):  # type: ignore[no-untyped-def]
    cli = make_test_client(session_factory, monkeypatch)
    cli.app.dependency_overrides[get_ahora] = lambda: ahora
    return cli


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    return _cliente(session_factory, monkeypatch)


def _body(td, inicio, **over):  # type: ignore[no-untyped-def]
    body = {
        "profesional_id": td["p"], "prestacion_id": td["prest_a"], "inicio": inicio.isoformat(),
        "dni": str(next(_dnis)), "nombre": "Ana", "apellido": "Publica",
        "email": "ana.publica@ejemplo.test", "acepta_privacidad": True,
    }  # fmt: skip
    body.update(over)
    return body


def _reservar(client, td, inicio, **over):  # type: ignore[no-untyped-def]
    return client.post(f"/api/public/clinicas/{SLUG}/reservas", json=_body(td, inicio, **over))


def _huecos(client, td, desde, hasta, slug=SLUG, **over):  # type: ignore[no-untyped-def]
    params = {"profesional_id": td["p"], "prestacion_id": td["prest_a"],
              "desde": desde.isoformat(), "hasta": hasta.isoformat(), **over}  # fmt: skip
    return client.get(f"/api/public/clinicas/{slug}/huecos", params=params)


# --- catálogo ------------------------------------------------------------------------------


def test_catalogo_publico_sin_sesion_200(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    resp = client.get(f"/api/public/clinicas/{SLUG}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = {p["id"] for p in body["profesionales"]}
    assert {turnos_data["p"], turnos_data["q"]} <= ids
    assert all(set(p) == {"id", "nombre", "especialidad"} for p in body["profesionales"])
    assert "matricula" not in resp.text


def test_profesional_sin_horario_no_se_ofrece(client, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        prof = Profesional(clinica_id=turnos_data["a"], nombre="Sin Horario", matricula="FIX-SH")
        session.add(prof)
        session.commit()
        prof_id = prof.id
    ids = {p["id"] for p in client.get(f"/api/public/clinicas/{SLUG}").json()["profesionales"]}
    assert prof_id not in ids


def test_slug_inexistente_404(client) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/public/clinicas/no-existe").status_code == 404


# --- huecos --------------------------------------------------------------------------------


def test_huecos_publicos_sin_sillones_y_restando_turnos(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    antes = _huecos(client, td, dia.replace(hour=9), dia.replace(hour=10))
    assert antes.status_code == 200
    assert all(set(h) == {"inicio", "fin"} for h in antes.json())
    assert len(antes.json()) == 3  # 09:00, 09:15, 09:30
    assert _reservar(client, td, dia.replace(hour=9)).status_code == 201
    despues = _huecos(client, td, dia.replace(hour=9), dia.replace(hour=10)).json()
    inicios = [datetime.fromisoformat(h["inicio"]) for h in despues]
    assert inicios == [dia.replace(hour=9, minute=30)]  # P ocupado de 09:00 a 09:30


def test_huecos_profesional_de_otra_clinica_422(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    dia = _dia()
    resp = _huecos(client, turnos_data, dia, dia + timedelta(hours=2),
                   profesional_id=turnos_data["prof_b"])  # fmt: skip
    assert resp.status_code == 422


# --- reserva -------------------------------------------------------------------------------


def test_paciente_nuevo_reserva_201_con_token(client, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    inicio = _dia().replace(hour=10)
    resp = _reservar(client, turnos_data, inicio)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["estado"] == "reservado" and body["cancelable"] is True
    assert body["token"] and datetime.fromisoformat(body["inicio"]) == inicio
    assert {"dni", "email", "telefono", "paciente_id", "sillon_id"}.isdisjoint(body)
    with session_factory() as session:
        turno = session.scalars(select(Turno).where(Turno.inicio == inicio)).one()
        assert turno.origen == "enlace"


@pytest.mark.parametrize("privacidad", [False, None])
def test_sin_aceptar_privacidad_422_sin_filas(
    client, session_factory, turnos_data, privacidad
) -> None:  # type: ignore[no-untyped-def]
    inicio, dni = _dia().replace(hour=10), str(next(_dnis))
    resp = _reservar(client, turnos_data, inicio, dni=dni, acepta_privacidad=privacidad)
    assert resp.status_code == 422
    with session_factory() as session:
        assert session.scalars(select(Paciente).where(Paciente.dni == dni)).first() is None
        assert session.scalars(select(Turno).where(Turno.inicio == inicio)).first() is None


def test_sobreturno_por_enlace_422(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    resp = _reservar(client, turnos_data, _dia().replace(hour=10), sobreturno=True)
    assert resp.status_code == 422


def test_dni_existente_201_respuesta_indistinguible(client, session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        dni = session.get(Paciente, turnos_data["pac_a"]).dni
    nuevo = _reservar(client, turnos_data, _dia().replace(hour=10))
    existente = _reservar(client, turnos_data, _dia().replace(hour=10), dni=dni)
    assert existente.status_code == nuevo.status_code == 201
    assert set(existente.json()) == set(nuevo.json())


def test_tercera_reserva_mismo_dni_409(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    dia, dni = _dia(), str(next(_dnis))
    for h in (9, 11):
        assert _reservar(client, turnos_data, dia.replace(hour=h), dni=dni).status_code == 201
    resp = _reservar(client, turnos_data, dia.replace(hour=13), dni=dni)
    assert resp.status_code == 409


def test_horario_tomado_409(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    inicio = _dia().replace(hour=10)
    assert _reservar(client, turnos_data, inicio).status_code == 201  # P queda ocupado
    resp = _reservar(client, turnos_data, inicio)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Horario no disponible"


# --- token ---------------------------------------------------------------------------------


def test_ver_y_cancelar_con_token_libera_el_hueco(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    inicio = dia.replace(hour=10)
    token = _reservar(client, td, inicio).json()["token"]
    assert _huecos(client, td, inicio, inicio + timedelta(minutes=30)).json() == []
    ver = client.get(f"/api/public/reservas/{token}")
    assert ver.status_code == 200
    assert "token" not in ver.json() and "dni" not in ver.json()
    cancelado = client.post(f"/api/public/reservas/{token}/cancelar")
    assert cancelado.status_code == 200
    assert cancelado.json()["estado"] == "cancelado"
    huecos = _huecos(client, td, inicio, inicio + timedelta(minutes=30)).json()
    assert len(huecos) == 1  # volvió a aparecer


def test_cancelar_despues_del_inicio_422(session_factory, monkeypatch, turnos_data) -> None:  # type: ignore[no-untyped-def]
    inicio = _dia().replace(hour=10)
    token = _reservar(_cliente(session_factory, monkeypatch), turnos_data, inicio).json()["token"]
    tarde = _cliente(session_factory, monkeypatch, inicio + timedelta(minutes=5))
    assert tarde.post(f"/api/public/reservas/{token}/cancelar").status_code == 422
    assert tarde.get(f"/api/public/reservas/{token}").json()["estado"] == "reservado"


def test_token_invalido_404(client) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/public/reservas/no-existe").status_code == 404
    assert client.post("/api/public/reservas/no-existe/cancelar").status_code == 404


# --- seguridad -----------------------------------------------------------------------------


def test_funciona_sin_jwt_e_ignora_sesion_de_staff(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, "recepcion@test.test")
    resp = client.post(
        f"/api/public/clinicas/{SLUG}/reservas",
        json=_body(turnos_data, _dia().replace(hour=10)), headers=h,
    )  # fmt: skip
    assert resp.status_code == 201


def test_slug_de_b_no_ve_ni_reserva_profesionales_de_a(
    client, session_factory, turnos_data
) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        slug_b = session.get(Clinica, turnos_data["b"]).slug
    cat_b = client.get(f"/api/public/clinicas/{slug_b}").json()
    assert turnos_data["p"] not in {p["id"] for p in cat_b["profesionales"]}
    resp = client.post(
        f"/api/public/clinicas/{slug_b}/reservas", json=_body(turnos_data, _dia().replace(hour=10))
    )
    assert resp.status_code == 422


def test_rafaga_de_reservas_desde_una_ip_429(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    """Default 5/minute: el sexto pedido recibe 429 con Retry-After (aunque el slug no exista:
    el límite cuenta pedidos que llegan al endpoint, no reservas exitosas)."""
    body = _body(turnos_data, _dia().replace(hour=10))
    url = "/api/public/clinicas/no-existe/reservas"
    codigos = [client.post(url, json=body).status_code for _ in range(6)]
    assert codigos == [404] * 5 + [429]
    ultimo = client.post(url, json=body)
    assert ultimo.status_code == 429 and ultimo.headers.get("Retry-After")
