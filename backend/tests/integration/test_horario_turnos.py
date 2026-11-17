"""Horario de atención en el alta de turnos y en huecos (C-05d D4). PG16 real, sintético.

El profesional H (propio de este módulo, habilitado en S1 y S2) tiene el horario que pide cada
test; la clínica A está en America/Argentina/Buenos_Aires (UTC−3, sin horario de verano), así
que 09:00 local = 12:00Z. 2031-03-10 es lunes y 2031-03-11 martes.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.api.turnos import get_ahora
from app.domain.agenda.horario import reemplazar_horario
from app.domain.agenda.huecos import buscar_huecos
from app.domain.agenda.models import Profesional, ProfesionalSillon
from app.domain.agenda.turnos import Turno, crear_turno
from tests.integration.conftest import bearer, make_test_client

RECEPCION = "recepcion@test.test"
PASADO = datetime(2031, 1, 1, tzinfo=UTC)
LUNES = datetime(2031, 3, 10, tzinfo=UTC)


def _local(dia: datetime, h: int, m: int = 0) -> datetime:
    """Hora local de la clínica (UTC−3) expresada en UTC."""
    return dia + timedelta(hours=h + 3, minutes=m)


@pytest.fixture(scope="module")
def prof_h(session_factory, turnos_data):  # type: ignore[no-untyped-def]
    td = turnos_data
    with session_factory() as session:
        prof = Profesional(clinica_id=td["a"], nombre="Profesional H Sintetico", matricula="FIX-H")
        session.add(prof)
        session.flush()
        session.add_all(
            ProfesionalSillon(clinica_id=td["a"], profesional_id=prof.id, sillon_id=s)
            for s in (td["s1"], td["s2"])
        )
        session.commit()
        return prof.id


def _horario(session_factory, td, prof_id, *franjas):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        reemplazar_horario(
            session, td["a"], prof_id,
            [{"dia_semana": d, "inicio": i * 60, "fin": f * 60} for d, i, f in franjas],
        )  # fmt: skip


@pytest.fixture()
def client(session_factory, monkeypatch):  # type: ignore[no-untyped-def]
    cli = make_test_client(session_factory, monkeypatch)
    cli.app.dependency_overrides[get_ahora] = lambda: PASADO
    return cli


def _post(client, td, prof_id, inicio, **extra):  # type: ignore[no-untyped-def]
    body = {
        "profesional_id": prof_id, "sillon_id": td["s1"], "paciente_id": td["pac_a"],
        "prestacion_id": td["prest_a"], "inicio": inicio.isoformat(), **extra,
    }  # fmt: skip
    return client.post("/api/turnos", json=body, headers=bearer(client, RECEPCION))


def _filas(session_factory, prof_id, inicio) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return session.query(Turno).filter_by(profesional_id=prof_id, inicio=inicio).count()


def _huecos(session_factory, td, prof_id, desde, hasta):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return buscar_huecos(session, td["a"], prof_id, td["prest_a"], desde, hasta, PASADO, 15)


# --- Alta de turno ---------------------------------------------------------------------------


def test_turno_dentro_del_horario_201(client, session_factory, turnos_data, prof_h) -> None:  # type: ignore[no-untyped-def]
    _horario(session_factory, turnos_data, prof_h, (1, 9, 13))
    resp = _post(client, turnos_data, prof_h, _local(LUNES, 12, 30))
    assert resp.status_code == 201, resp.text


def test_turno_que_termina_fuera_del_horario_409_sin_fila(  # type: ignore[no-untyped-def]
    client, session_factory, turnos_data, prof_h
) -> None:
    _horario(session_factory, turnos_data, prof_h, (1, 9, 13))
    inicio = _local(LUNES + timedelta(days=42), 12, 45)  # lunes propio: sin turnos que choquen
    resp = _post(client, turnos_data, prof_h, inicio)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Horario no disponible"
    assert _filas(session_factory, prof_h, inicio) == 0


def test_profesional_sin_horario_409(client, session_factory, turnos_data, prof_h) -> None:  # type: ignore[no-untyped-def]
    _horario(session_factory, turnos_data, prof_h)
    inicio = _local(LUNES, 10)
    assert _post(client, turnos_data, prof_h, inicio).status_code == 409
    assert _filas(session_factory, prof_h, inicio) == 0


def test_sobreturno_fuera_del_horario_201(client, session_factory, turnos_data, prof_h) -> None:  # type: ignore[no-untyped-def]
    _horario(session_factory, turnos_data, prof_h, (1, 9, 13))
    resp = _post(
        client, turnos_data, prof_h, _local(LUNES, 13, 15),
        sobreturno=True, motivo_sobreturno="se agrega al final del día",
    )  # fmt: skip
    assert resp.status_code == 201, resp.text
    assert resp.json()["es_sobreturno"] is True


def test_turno_que_cruza_franjas_contiguas_201(  # type: ignore[no-untyped-def]
    client, session_factory, turnos_data, prof_h
) -> None:
    _horario(session_factory, turnos_data, prof_h, (2, 9, 10), (2, 10, 11))
    resp = _post(client, turnos_data, prof_h, _local(LUNES + timedelta(days=1), 9, 45))
    assert resp.status_code == 201, resp.text


def test_turno_que_cruza_la_medianoche_local_entre_franjas_201(  # type: ignore[no-untyped-def]
    session_factory, turnos_data, prof_h
) -> None:
    """Lunes 22–24 y martes 00–02 forman un tramo: un turno a las 23:45 del lunes entra."""
    td = turnos_data
    _horario(session_factory, td, prof_h, (1, 22, 24), (2, 0, 2))
    datos = {"profesional_id": prof_h, "sillon_id": td["s2"], "paciente_id": td["pac_a"],
             "prestacion_id": td["prest_a"], "inicio": _local(LUNES, 23, 45)}  # fmt: skip
    with session_factory() as session:
        turno = crear_turno(session, td["a"], datos, PASADO)
        assert turno.fin == _local(LUNES + timedelta(days=1), 0, 15)


# --- Huecos ----------------------------------------------------------------------------------


def _hhmm_local(huecos) -> list[str]:  # type: ignore[no-untyped-def]
    return [(h["inicio"] - timedelta(hours=3)).strftime("%H:%M") for h in huecos]


def test_horario_partido_recorta_los_huecos(session_factory, turnos_data, prof_h) -> None:  # type: ignore[no-untyped-def]
    dia = LUNES + timedelta(days=7)  # otro lunes, sin turnos de los tests de alta
    _horario(session_factory, turnos_data, prof_h, (1, 9, 11), (1, 15, 16))
    huecos = _huecos(session_factory, turnos_data, prof_h, _local(dia, 8), _local(dia, 17))
    assert _hhmm_local(huecos) == [
        "09:00", "09:15", "09:30", "09:45", "10:00", "10:15", "10:30", "15:00", "15:15", "15:30",
    ]  # fmt: skip


def test_hueco_que_cruza_franjas_contiguas(session_factory, turnos_data, prof_h) -> None:  # type: ignore[no-untyped-def]
    dia = LUNES + timedelta(days=14)
    _horario(session_factory, turnos_data, prof_h, (1, 9, 10), (1, 10, 11))
    huecos = _huecos(session_factory, turnos_data, prof_h, _local(dia, 9), _local(dia, 11))
    assert "09:45" in _hhmm_local(huecos)


def test_profesional_sin_horario_no_tiene_huecos(session_factory, turnos_data, prof_h) -> None:  # type: ignore[no-untyped-def]
    _horario(session_factory, turnos_data, prof_h)
    dia = LUNES + timedelta(days=21)
    assert _huecos(session_factory, turnos_data, prof_h, dia, dia + timedelta(days=7)) == []


def test_franja_local_convertida_a_utc(session_factory, turnos_data, prof_h) -> None:  # type: ignore[no-untyped-def]
    dia = LUNES + timedelta(days=28)
    _horario(session_factory, turnos_data, prof_h, (1, 9, 13))
    huecos = _huecos(session_factory, turnos_data, prof_h, dia, dia + timedelta(days=1))
    assert huecos[0]["inicio"] == dia.replace(hour=12)  # 09:00 local = 12:00Z
    assert huecos[-1]["fin"] == dia.replace(hour=16)  # termina justo a las 13:00 local


def test_cada_hueco_con_horario_partido_acepta_un_turno_normal(  # type: ignore[no-untyped-def]
    session_factory, turnos_data, prof_h
) -> None:
    """Propiedad (D4): mismo fragmento SQL en huecos y alta, entonces hueco => 201."""
    td, dia = turnos_data, LUNES + timedelta(days=35)
    _horario(session_factory, td, prof_h, (1, 9, 11), (1, 11, 12), (1, 15, 16))
    huecos = _huecos(session_factory, td, prof_h, _local(dia, 6), _local(dia, 20))
    assert len(huecos) == 14  # 09:00–11:30 (9–12 continuo) + 15:00–15:30
    for h in huecos:
        datos = {"profesional_id": prof_h, "sillon_id": h["sillon_ids"][0],
                 "paciente_id": td["pac_a"], "prestacion_id": td["prest_a"],
                 "inicio": h["inicio"]}  # fmt: skip
        with session_factory() as session:
            turno = crear_turno(session, td["a"], datos, PASADO)
            turno.is_active = False  # libera el hueco para la próxima prueba
            session.commit()
