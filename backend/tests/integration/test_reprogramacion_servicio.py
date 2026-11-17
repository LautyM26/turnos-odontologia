"""Opciones y reprogramación (C-17 2.1, D2/D3). PG16 real, sintético."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.domain.agenda.servicio import ReferenciaInvalida
from app.domain.agenda.turnos import Turno, TurnoTransicion
from app.domain.reprogramacion.servicios import Ajustes, HorarioOcupado, opciones, reprogramar
from tests.integration.conftest_lista import escenario

AJ = Ajustes(timeout_min=30, anticipacion_min=120, paso_min=15)


def _t(e, tid: int) -> Turno:  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return s.get(Turno, tid)


def _ops(e, tid):  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return opciones(s, s.get(Turno, tid), e.ahora, AJ)


def _reprogramar(e, tid, inicio, **kw):  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return reprogramar(s, s.get(Turno, tid), inicio, e.ahora, AJ, "paciente_whatsapp",
                           "whatsapp", **kw)  # fmt: skip


def test_tres_primeros_huecos_del_mismo_profesional(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    tid = e.turno(20, e.paciente()[0])
    ops = _ops(e, tid)
    base = e.ahora + timedelta(hours=2)  # 12:00 + 2 h, ya alineado al paso de 15
    assert [o["inicio"] for o in ops] == [base, base + timedelta(minutes=15),
                                          base + timedelta(minutes=30)]  # fmt: skip


def test_ocupado_del_profesional_no_se_ofrece(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    tid = e.turno(20, e.paciente()[0])
    e.turno(2, e.paciente()[0], sillon="s2")  # P ocupado de 14:00 a 14:30 en otro sillón
    inicios = [o["inicio"] for o in _ops(e, tid)]
    assert e.ahora + timedelta(hours=2) not in inicios
    assert inicios[0] == e.ahora + timedelta(hours=2, minutes=30)


def test_no_reprogramables_sin_opciones(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    pid = e.paciente()[0]
    assert _ops(e, e.turno(20, pid, estado="cancelado")) == []
    assert _ops(e, e.turno(-1, pid)) == []  # ya empezó


def test_reprogramar_crea_nuevo_y_cancela_viejo(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    pid = e.paciente()[0]
    tid = e.turno(20, pid)
    destino = _ops(e, tid)[1]["inicio"]
    nuevo = _reprogramar(e, tid, destino)
    assert (nuevo.inicio, nuevo.paciente_id, nuevo.estado, nuevo.origen) == (
        destino, pid, "reservado", "whatsapp")  # fmt: skip
    viejo = _t(e, tid)
    assert viejo.estado == "cancelado"
    assert nuevo.profesional_id == viejo.profesional_id
    assert nuevo.prestacion_id == viejo.prestacion_id
    with session_factory() as s:
        [tr] = s.scalars(select(TurnoTransicion).where(TurnoTransicion.turno_id == tid))
    assert (tr.hacia, tr.actor_tipo, tr.actor_usuario_id) == (
        "cancelado", "paciente_whatsapp", None)  # fmt: skip
    assert tr.motivo == f"reprogramado al turno {nuevo.id}"


def test_inicio_invalido_422(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    tid = e.turno(20, e.paciente()[0])
    with pytest.raises(ReferenciaInvalida):  # enlace: antes de la anticipación mínima
        _reprogramar(e, tid, e.ahora + timedelta(hours=1), exigir_opcion=True)
    with pytest.raises(ReferenciaInvalida):  # en el pasado, por cualquier canal
        _reprogramar(e, tid, e.ahora - timedelta(hours=1))
    with pytest.raises(ReferenciaInvalida):  # libre, pero no es una de las 3 opciones
        _reprogramar(e, tid, e.ahora + timedelta(days=3), exigir_opcion=True)
    assert _t(e, tid).estado == "reservado"


def test_horario_ocupado_409_con_alternativas(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    tid = e.turno(20, e.paciente()[0])
    elegido = _ops(e, tid)[0]["inicio"]
    e.turno(2, e.paciente()[0], sillon="s2")  # alguien toma ese horario de P
    with pytest.raises(HorarioOcupado) as exc:
        _reprogramar(e, tid, elegido)
    assert exc.value.alternativas and elegido not in [a["inicio"] for a in exc.value.alternativas]
    assert _t(e, tid).estado == "reservado"


def test_el_token_pasa_al_turno_nuevo(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    tid = e.turno(20, e.paciente()[0])
    with session_factory() as s:
        s.get(Turno, tid).token_publico_hash = "c17" + "0" * 61
        s.commit()
    nuevo = _reprogramar(e, tid, _ops(e, tid)[0]["inicio"])
    assert nuevo.token_publico_hash == "c17" + "0" * 61
    assert _t(e, tid).token_publico_hash is None


def test_opcion_ofrecida_se_confirma_aunque_pasen_minutos(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    """La anticipación se exige al ofrecer: la 1ª opción (justo a +2 h) sigue valiendo después."""
    e = escenario(session_factory, turnos_data)
    tid = e.turno(20, e.paciente()[0])
    primera = _ops(e, tid)[0]["inicio"]
    with e.sf() as s:
        nuevo = reprogramar(s, s.get(Turno, tid), primera, e.ahora + timedelta(minutes=5), AJ,
                            "paciente_whatsapp", "whatsapp")  # fmt: skip
    assert nuevo.inicio == primera
