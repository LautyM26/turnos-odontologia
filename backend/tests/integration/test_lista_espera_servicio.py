"""Entradas de la lista de espera (C-16 4.1, D2/D8). PG16 real, sintético."""

from datetime import timedelta

import pytest

from app.domain.agenda.servicio import Conflicto, ReferenciaInvalida
from app.domain.lista_espera import servicios
from app.domain.lista_espera.models import ListaEspera, OfertaListaEspera
from tests.integration.conftest_lista import escenario


def _crear(e, **datos):  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return servicios.crear_entrada(s, e.c, {"prestacion_id": e.prest, **datos}, e.ahora)


def test_alta_con_turno_a_adelantar(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    pid, _ = e.paciente()
    tid = e.turno(24 * 10, pid)
    entrada = _crear(e, paciente_id=pid, turno_a_adelantar_id=tid, prioridad=5)
    assert (entrada.estado, entrada.prioridad, entrada.turno_a_adelantar_id) == ("en_cola", 5, tid)


def test_turno_a_adelantar_de_otro_paciente_422(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    pid, _ = e.paciente()
    otro, _ = e.paciente()
    tid = e.turno(24 * 10, otro)
    with pytest.raises(ReferenciaInvalida):
        _crear(e, paciente_id=pid, turno_a_adelantar_id=tid)


def test_turno_a_adelantar_pasado_o_cancelado_422(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    pid, _ = e.paciente()
    for tid in (e.turno(-5, pid), e.turno(30, pid, estado="cancelado")):
        with pytest.raises(ReferenciaInvalida):
            _crear(e, paciente_id=pid, turno_a_adelantar_id=tid)


def test_referencias_ajenas_422(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    pid, _ = e.paciente()
    with pytest.raises(ReferenciaInvalida):
        _crear(e, paciente_id=turnos_data["pac_b"])
    with pytest.raises(ReferenciaInvalida):
        _crear(e, paciente_id=pid, profesional_id=turnos_data["prof_b"])


def test_entrada_duplicada_409(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    pid, _ = e.paciente()
    _crear(e, paciente_id=pid)
    with pytest.raises(Conflicto):
        _crear(e, paciente_id=pid)


def test_orden_de_la_cola(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    ids = [e.entrada(e.paciente()[0], prioridad=p) for p in (0, 5, 5)]
    with session_factory() as s:
        orden = [x.id for x in servicios.listar_activas(s, e.c, e.prest)]
    assert orden == [ids[1], ids[2], ids[0]]


def test_baja_con_oferta_pendiente(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e = escenario(session_factory, turnos_data)
    eid = e.entrada(e.paciente()[0], estado="ofertado")
    hueco = e.hueco()
    with session_factory() as s:
        oferta = OfertaListaEspera(
            clinica_id=e.c, lista_espera_id=eid, turno_liberado_id=hueco,
            inicio=e.ahora + timedelta(hours=20), fin=e.ahora + timedelta(hours=20, minutes=30),
            profesional_id=turnos_data["p"], sillon_id=turnos_data["s1"], prestacion_id=e.prest,
            expira_at=e.ahora + timedelta(minutes=30),
        )  # fmt: skip
        s.add(oferta)
        s.commit()
        oid = oferta.id
    with session_factory() as s:
        servicios.dar_de_baja(s, e.c, eid)
    with session_factory() as s:
        assert s.get(ListaEspera, eid).estado == "salido"
        assert s.get(OfertaListaEspera, oid).estado == "anulada"
        assert servicios.listar_activas(s, e.c, e.prest) == []
