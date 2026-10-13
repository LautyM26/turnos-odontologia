"""POST/GET /api/turnos (C-05 recorte): alta, 409/422, bloqueos, RBAC y aislamiento.

PG16 real vía testcontainers; fechas futuras 2031 y datos sintéticos. Cada test usa un día
propio (``_dia()``) para no interferir con los turnos de los demás tests del módulo.
"""

import itertools
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.api.turnos import get_ahora
from app.domain.agenda.models import Bloqueo
from app.domain.agenda.turnos import Turno
from tests.integration.conftest import bearer, make_test_client

AHORA_BASE = datetime(2031, 1, 1, tzinfo=UTC)
ARGENTINA = timezone(timedelta(hours=-3))
_dias = itertools.count(0)
RECEPCION = "recepcion@test.test"


def _dia() -> datetime:
    """Medianoche UTC de un día futuro único dentro del módulo."""
    return datetime(2031, 6, 1, tzinfo=UTC) + timedelta(days=next(_dias))


def _h(dia: datetime, h: int, m: int = 0) -> datetime:
    return dia.replace(hour=h, minute=m)


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    cli = make_test_client(session_factory, monkeypatch)
    cli.app.dependency_overrides[get_ahora] = lambda: AHORA_BASE
    return cli


def _body(td, inicio, **over):  # type: ignore[no-untyped-def]
    body = {
        "profesional_id": td["p"], "sillon_id": td["s1"], "paciente_id": td["pac_a"],
        "prestacion_id": td["prest_a"], "inicio": inicio.isoformat(),
    }  # fmt: skip
    body.update(over)
    return body


def _post(client, headers, td, inicio, **over):  # type: ignore[no-untyped-def]
    return client.post("/api/turnos", json=_body(td, inicio, **over), headers=headers)


def _n_turnos(session_factory, **filtros) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        stmt = select(func.count()).select_from(Turno)
        for campo, valor in filtros.items():
            stmt = stmt.where(getattr(Turno, campo) == valor)
        return int(session.scalar(stmt))


def _turno_directo(session_factory, td, inicio, minutos=30, **over):  # type: ignore[no-untyped-def]
    cols = {
        "clinica_id": td["a"], "profesional_id": td["p"], "sillon_id": td["s1"],
        "paciente_id": td["pac_a"], "prestacion_id": td["prest_a"], "duracion_min": minutos,
        "inicio": inicio, "fin": inicio + timedelta(minutes=minutos),
    }  # fmt: skip
    cols.update(over)
    with session_factory() as session:
        session.add(Turno(**cols))
        session.commit()


def _bloqueo(session_factory, td, inicio, fin, activo=True, **alcance):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        session.add(
            Bloqueo(
                clinica_id=td["a"], inicio=inicio, fin=fin, motivo="bloqueo sintetico",
                is_active=activo, **alcance,
            )  # fmt: skip
        )
        session.commit()


# --- 3.2 alta ---------------------------------------------------------------------------


def test_recepcionista_crea_turno_201_con_fin_calculado_y_get(  # type: ignore[no-untyped-def]
    client, turnos_data
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    resp = _post(client, h, td, datetime(2031, 3, 10, 10, tzinfo=UTC))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["estado"] == "reservado" and body["origen"] == "mostrador"
    assert body["duracion_min"] == 30
    assert datetime.fromisoformat(body["fin"]) == datetime(2031, 3, 10, 10, 30, tzinfo=UTC)
    got = client.get(f"/api/turnos/{body['id']}", headers=h)
    assert got.status_code == 200 and got.json() == body


def test_inicio_con_offset_se_normaliza_y_admin_tambien_crea(  # type: ignore[no-untyped-def]
    client, turnos_data, auth_data
) -> None:
    td = turnos_data
    dia = _dia()
    h = bearer(client, auth_data["admin_email"])
    local = _h(dia, 10).astimezone(ARGENTINA)  # 07:00-03:00 == 10:00Z
    resp = _post(client, h, td, local)
    assert resp.status_code == 201, resp.text
    assert datetime.fromisoformat(resp.json()["inicio"]) == _h(dia, 10)
    assert datetime.fromisoformat(resp.json()["fin"]) == _h(dia, 10, 30)


def test_fin_o_duracion_en_body_422_sin_fila(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    inicio = _h(_dia(), 10)
    for extra in ({"fin": _h(inicio, 11).isoformat()}, {"duracion_min": 60}):
        assert _post(client, h, td, inicio, **extra).status_code == 422
    assert _n_turnos(session_factory, inicio=inicio) == 0


def test_inicio_naive_422_sin_fila(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    inicio = _h(_dia(), 10)
    naive = inicio.replace(tzinfo=None).isoformat()
    body = _body(td, inicio)
    body["inicio"] = naive
    assert client.post("/api/turnos", json=body, headers=h).status_code == 422
    assert _n_turnos(session_factory, inicio=inicio) == 0


def test_turno_en_el_pasado_422_e_inicio_igual_a_ahora_201(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    ahora = datetime(2031, 3, 10, 12, tzinfo=UTC)
    client.app.dependency_overrides[get_ahora] = lambda: ahora
    pasado = datetime(2031, 3, 10, 11, tzinfo=UTC)
    resp = _post(client, h, td, pasado)
    assert resp.status_code == 422
    assert resp.json()["detail"] == "No se pueden crear turnos en el pasado"
    assert _n_turnos(session_factory, inicio=pasado) == 0
    assert _post(client, h, td, ahora).status_code == 201  # inicio == ahora se acepta
    un_segundo_antes = ahora - timedelta(seconds=1)
    assert _post(client, h, td, un_segundo_antes, sillon_id=td["s2"]).status_code == 422


# --- 3.3 solapamientos ------------------------------------------------------------------


def test_profesional_ocupado_en_otro_sillon_409(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    dia = _dia()
    assert _post(client, h, td, _h(dia, 10)).status_code == 201
    resp = _post(client, h, td, _h(dia, 10, 15), sillon_id=td["s2"])
    assert resp.status_code == 409
    assert resp.json() == {"detail": "Horario no disponible"}  # sin ids ni datos del paciente
    assert _n_turnos(session_factory, profesional_id=td["p"], inicio=_h(dia, 10, 15)) == 0
    assert _n_turnos(session_factory, profesional_id=td["p"], inicio=_h(dia, 10)) == 1


def test_sillon_ocupado_por_otro_profesional_409(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    dia = _dia()
    assert _post(client, h, td, _h(dia, 10)).status_code == 201
    resp = _post(client, h, td, _h(dia, 9, 45), profesional_id=td["q"])  # [09:45, 10:15)
    assert resp.status_code == 409 and resp.json() == {"detail": "Horario no disponible"}
    assert _n_turnos(session_factory, profesional_id=td["q"], inicio=_h(dia, 9, 45)) == 0
    assert _n_turnos(session_factory, sillon_id=td["s1"], inicio=_h(dia, 10)) == 1


def test_turno_contiguo_201(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    h = bearer(client, RECEPCION)
    dia = _dia()
    assert _post(client, h, td, _h(dia, 10)).status_code == 201
    resp = _post(client, h, td, _h(dia, 10, 30))
    assert resp.status_code == 201
    assert datetime.fromisoformat(resp.json()["fin"]) == _h(dia, 11)
    assert _post(client, h, td, _h(dia, 9, 30)).status_code == 201  # termina donde empieza otro


@pytest.mark.parametrize(
    "libera",
    [{"estado": "cancelado"}, {"estado": "ausente"}, {"is_active": False}],
    ids=["cancelado", "ausente", "baja_logica"],
)
def test_turno_no_activo_libera_el_hueco_201(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory, libera
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    dia = _dia()
    _turno_directo(session_factory, td, _h(dia, 10), **libera)
    assert _post(client, h, td, _h(dia, 10)).status_code == 201
    # Triangulación: otro profesional en el mismo sillón y hora tras una baja lógica.
    _turno_directo(session_factory, td, _h(dia, 11), is_active=False)
    assert _post(client, h, td, _h(dia, 11), profesional_id=td["q"]).status_code == 201


# --- 3.4 bloqueos -----------------------------------------------------------------------


def test_bloqueo_del_profesional_409_y_contiguo_201(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    dia = _dia()
    _bloqueo(session_factory, td, _h(dia, 13), _h(dia, 14), profesional_id=td["p"])
    resp = _post(client, h, td, _h(dia, 13, 30))
    assert resp.status_code == 409 and resp.json() == {"detail": "Horario no disponible"}
    assert _n_turnos(session_factory, inicio=_h(dia, 13, 30)) == 0
    ok = _post(client, h, td, _h(dia, 12, 30))  # [12:30, 13:00) toca el bloqueo sin pisarlo
    assert ok.status_code == 201
    assert datetime.fromisoformat(ok.json()["fin"]) == _h(dia, 13)


def test_bloqueo_del_sillon_409(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    dia = _dia()
    _bloqueo(session_factory, td, _h(dia, 9), _h(dia, 10), sillon_id=td["s1"])
    assert _post(client, h, td, _h(dia, 9, 30), profesional_id=td["q"]).status_code == 409
    # Triangulación: otro sillón a la misma hora no está bloqueado.
    libre = _post(client, h, td, _h(dia, 9, 30), profesional_id=td["q"], sillon_id=td["s2"])
    assert libre.status_code == 201


def test_bloqueo_de_clinica_409_para_cualquier_recurso(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    dia = _dia()
    _bloqueo(session_factory, td, dia, dia + timedelta(days=1))
    assert _post(client, h, td, _h(dia, 10)).status_code == 409
    resp = _post(client, h, td, _h(dia, 16), profesional_id=td["q"], sillon_id=td["s2"])
    assert resp.status_code == 409
    # El día siguiente no está bloqueado (rango semiabierto).
    assert _post(client, h, td, dia + timedelta(days=1)).status_code == 201


def test_bloqueo_de_otro_profesional_o_inactivo_no_impide(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    dia = _dia()
    _bloqueo(session_factory, td, _h(dia, 15), _h(dia, 16), profesional_id=td["q"])
    assert _post(client, h, td, _h(dia, 15), sillon_id=td["s2"]).status_code == 201
    _bloqueo(session_factory, td, _h(dia, 17), _h(dia, 18), activo=False, profesional_id=td["p"])
    assert _post(client, h, td, _h(dia, 17)).status_code == 201


# --- 3.5 referencias --------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalida",
    [
        {"paciente_id": "pac_a_inactivo"},
        {"prestacion_id": "prest_inactiva"},
        {"profesional_id": "prof_r"},  # agenda_activa = false (habilitado en S1)
        {"sillon_id": "s3"},  # P no esta habilitado en S3 (D-A1)
        {"profesional_id": "prof_b"},
        {"sillon_id": "sillon_b"},
        {"paciente_id": "pac_b"},
        {"prestacion_id": "prest_b"},
    ],
    ids=[
        "paciente_inactivo", "prestacion_inactiva", "agenda_inactiva", "no_habilitado",
        "profesional_de_B", "sillon_de_B", "paciente_de_B", "prestacion_de_B",
    ],
)  # fmt: skip
def test_referencias_invalidas_422_sin_persistir(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory, invalida
) -> None:
    td = turnos_data
    h = bearer(client, RECEPCION)
    inicio = _h(_dia(), 10)
    over = {campo: td[clave] for campo, clave in invalida.items()}
    assert _post(client, h, td, inicio, **over).status_code == 422
    assert _n_turnos(session_factory, inicio=inicio) == 0


def test_referencia_inexistente_422(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    h = bearer(client, RECEPCION)
    assert _post(client, h, td, _h(_dia(), 10), paciente_id=999_999_999).status_code == 422


# --- 3.6 RBAC y aislamiento -------------------------------------------------------------


def test_odontologo_403_aun_con_body_invalido_y_sin_fila(  # type: ignore[no-untyped-def]
    client, turnos_data, session_factory
) -> None:
    td = turnos_data
    h = bearer(client, "odonto@test.test")
    inicio = _h(_dia(), 10)
    assert _post(client, h, td, inicio).status_code == 403
    assert client.post("/api/turnos", json={"fin": "x"}, headers=h).status_code == 403
    assert _n_turnos(session_factory, inicio=inicio) == 0


def test_sin_token_401(client, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td = turnos_data
    assert client.post("/api/turnos", json=_body(td, _h(_dia(), 10))).status_code == 401
    assert client.get("/api/turnos/1").status_code == 401


def test_misma_hora_en_otra_clinica_201_y_get_ajeno_404(  # type: ignore[no-untyped-def]
    client, turnos_data
) -> None:
    td = turnos_data
    dia = _dia()
    ha = bearer(client, RECEPCION)
    hb = bearer(client, "recepcion-b@test.test")
    creado_a = _post(client, ha, td, _h(dia, 10))
    assert creado_a.status_code == 201
    resp_b = _post(
        client, hb, td, _h(dia, 10), profesional_id=td["prof_b"], sillon_id=td["sillon_b"],
        paciente_id=td["pac_b"], prestacion_id=td["prest_b"],
    )  # fmt: skip
    assert resp_b.status_code == 201, resp_b.text
    assert client.get(f"/api/turnos/{creado_a.json()['id']}", headers=hb).status_code == 404
    assert client.get(f"/api/turnos/{resp_b.json()['id']}", headers=ha).status_code == 404
    assert client.get(f"/api/turnos/{resp_b.json()['id']}", headers=hb).status_code == 200


def test_odontologo_puede_leer_un_turno(  # type: ignore[no-untyped-def]
    client, turnos_data
) -> None:
    td = turnos_data
    creado = _post(client, bearer(client, RECEPCION), td, _h(_dia(), 10))
    headers = bearer(client, "odonto@test.test")
    assert client.get(f"/api/turnos/{creado.json()['id']}", headers=headers).status_code == 200


def test_turnos_no_es_ruta_publica() -> None:
    from app.api.deps import PUBLIC_PREFIXES, is_public_path

    assert not is_public_path("/api/turnos")
    assert not is_public_path("/api/turnos/1")
    assert not any(p.startswith("/api/turnos") for p in PUBLIC_PREFIXES)
