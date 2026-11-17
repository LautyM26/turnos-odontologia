"""``buscar_huecos`` (C-05c D5): escenarios de la spec schedule-availability contra PG16 real.

Datos sintéticos; cada test usa un día propio de 2032-04 (los bloqueos de clínica tapan el
día entero para todos los recursos). P y Q habilitados en S1 y S2, prestación de 30 min.
"""

import itertools
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.agenda.huecos import buscar_huecos
from app.domain.agenda.models import Bloqueo
from app.domain.agenda.servicio import ReferenciaInvalida
from app.domain.agenda.turnos import Turno, crear_turno

PASADO = datetime(2032, 1, 1, tzinfo=UTC)
_dias = itertools.count(0)


def _dia() -> datetime:
    return datetime(2032, 4, 1, tzinfo=UTC) + timedelta(days=next(_dias))


def _h(dia: datetime, h: int, m: int = 0) -> datetime:
    return dia.replace(hour=h, minute=m)


def _huecos(session_factory, td, desde, hasta, prof=None, ahora=PASADO, paso=15):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        return buscar_huecos(
            session, td["a"], prof or td["p"], td["prest_a"], desde, hasta, ahora, paso
        )


def _inicios(huecos) -> list[tuple[int, int]]:  # type: ignore[no-untyped-def]
    return [(h["inicio"].hour, h["inicio"].minute) for h in huecos]


def _turno(session_factory, td, inicio, prof=None, sillon=None, **over):  # type: ignore[no-untyped-def]
    cols = {
        "clinica_id": td["a"], "profesional_id": prof or td["p"], "sillon_id": sillon or td["s1"],
        "paciente_id": td["pac_a"], "prestacion_id": td["prest_a"], "duracion_min": 30,
        "inicio": inicio, "fin": inicio + timedelta(minutes=30),
    }  # fmt: skip
    cols.update(over)
    with session_factory() as session:
        session.add(Turno(**cols))
        session.commit()


def _bloqueo(session_factory, td, inicio, fin, **alcance):  # type: ignore[no-untyped-def]
    with session_factory() as session:
        session.add(
            Bloqueo(clinica_id=td["a"], inicio=inicio, fin=fin, motivo="sintetico", **alcance)
        )
        session.commit()


def test_dia_libre_devuelve_huecos_cada_paso(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    huecos = _huecos(session_factory, td, _h(dia, 9), _h(dia, 10))
    assert _inicios(huecos) == [(9, 0), (9, 15), (9, 30)]  # 09:45 terminaría a las 10:15
    for h in huecos:
        assert h["fin"] - h["inicio"] == timedelta(minutes=30)
        assert h["sillon_ids"] == sorted([td["s1"], td["s2"]])


def test_turno_del_profesional_ocupa_el_hueco(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    _turno(session_factory, td, _h(dia, 9, 15))  # [09:15, 09:45) en S1
    huecos = _huecos(session_factory, td, _h(dia, 9), _h(dia, 10, 30))
    assert _inicios(huecos) == [(9, 45), (10, 0)]  # 09:45 contiguo al fin del turno


def test_bloqueo_de_clinica(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    _bloqueo(session_factory, td, _h(dia, 12), _h(dia, 13))
    huecos = _huecos(session_factory, td, _h(dia, 11, 30), _h(dia, 13, 30))
    assert _inicios(huecos) == [(11, 30), (13, 0)]


def test_bloqueo_del_profesional_y_del_sillon(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    _bloqueo(session_factory, td, _h(dia, 9), _h(dia, 9, 30), profesional_id=td["p"])
    _bloqueo(session_factory, td, _h(dia, 9, 30), _h(dia, 10), sillon_id=td["s1"])
    huecos = _huecos(session_factory, td, _h(dia, 9), _h(dia, 10))
    assert _inicios(huecos) == [(9, 30)]
    assert huecos[0]["sillon_ids"] == [td["s2"]]


def test_un_sillon_ocupado_deja_el_otro(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    _turno(session_factory, td, _h(dia, 9), prof=td["q"], sillon=td["s1"])
    huecos = _huecos(session_factory, td, _h(dia, 9), _h(dia, 9, 30))
    assert _inicios(huecos) == [(9, 0)]
    assert huecos[0]["sillon_ids"] == [td["s2"]]


def test_turno_cancelado_o_sobreturno_no_restan(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    _turno(session_factory, td, _h(dia, 9), estado="cancelado")
    _turno(session_factory, td, _h(dia, 9, 30), es_sobreturno=True, motivo_sobreturno="urgencia")
    huecos = _huecos(session_factory, td, _h(dia, 9), _h(dia, 10))
    assert _inicios(huecos) == [(9, 0), (9, 15), (9, 30)]


def test_ventana_que_empieza_en_el_pasado(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    huecos = _huecos(session_factory, td, _h(dia, 9), _h(dia, 11), ahora=_h(dia, 10, 5))
    assert _inicios(huecos)[0] == (10, 15)


def test_paso_configurable(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    huecos = _huecos(session_factory, td, _h(dia, 9), _h(dia, 10), paso=30)
    assert _inicios(huecos) == [(9, 0), (9, 30)]


@pytest.mark.parametrize(
    ("desde_h", "hasta_dias", "msg"),
    [(10, 0, "posterior"), (9, 8, "7 días")],
    ids=["hasta_antes_de_desde", "ventana_mayor_a_7_dias"],
)
def test_ventana_invalida_422(session_factory, turnos_data, desde_h, hasta_dias, msg) -> None:  # type: ignore[no-untyped-def]
    td, dia = turnos_data, _dia()
    with pytest.raises(ReferenciaInvalida, match=msg):
        _huecos(session_factory, td, _h(dia, desde_h), _h(dia, 9) + timedelta(days=hasta_dias))


def test_cada_hueco_devuelto_acepta_un_turno_normal(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    """Propiedad (D5): un hueco es exactamente un inicio donde ``crear_turno`` da 201."""
    td, dia = turnos_data, _dia()
    _turno(session_factory, td, _h(dia, 9, 15))
    _turno(session_factory, td, _h(dia, 10), prof=td["q"], sillon=td["s2"])
    _bloqueo(session_factory, td, _h(dia, 11), _h(dia, 11, 20), sillon_id=td["s1"])
    _bloqueo(session_factory, td, _h(dia, 12, 10), _h(dia, 12, 40))
    huecos = _huecos(session_factory, td, _h(dia, 9), _h(dia, 13))
    assert huecos
    for h in huecos:
        for sillon in h["sillon_ids"]:
            datos = {
                "profesional_id": td["p"], "sillon_id": sillon, "paciente_id": td["pac_a"],
                "prestacion_id": td["prest_a"], "inicio": h["inicio"],
            }  # fmt: skip
            with session_factory() as session:
                turno = crear_turno(session, td["a"], datos, PASADO)
                turno.is_active = False  # baja lógica: libera el hueco para la próxima prueba
                session.commit()
