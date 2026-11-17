"""Elección del candidato y envío de la oferta (C-16 4.2 + 3.1, D3/D4). PG16 real, sintético."""

from sqlalchemy import select

from app.domain.lista_espera.models import ListaEspera, OfertaListaEspera
from app.domain.pacientes.models import Paciente
from app.infrastructure.whatsapp.fake import FakeMensajeria
from app.jobs.lista_espera import procesar_lista_espera
from tests.integration.conftest_lista import escenario, settings_le


def _correr(e, fake, ahora=None, **kw):  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return procesar_lista_espera(s, fake, settings_le(**kw), ahora or e.ahora)


def _ofertas(e, entrada_id: int) -> list[OfertaListaEspera]:  # type: ignore[no-untyped-def]
    with e.sf() as s:
        return list(s.scalars(select(OfertaListaEspera).where(
            OfertaListaEspera.lista_espera_id == entrada_id)))  # fmt: skip


def _a(fake, tel):  # type: ignore[no-untyped-def]
    return [t for _, telefono, t in fake.enviados if telefono == tel]


def test_cancelacion_dispara_oferta_al_primero(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    (p2, tel2), (p3, tel3) = e.paciente(), e.paciente()
    e2, e3 = e.entrada(p2, prioridad=5), e.entrada(p3, prioridad=0)
    hueco = e.hueco(20)
    _correr(e, fake)
    [o] = _ofertas(e, e2)
    assert (o.estado, o.turno_liberado_id) == ("pendiente", hueco)
    assert _ofertas(e, e3) == []
    with session_factory() as s:
        assert s.get(ListaEspera, e2).estado == "ofertado"
        nombre = s.get(Paciente, p2).nombre
    [texto] = _a(fake, tel2)
    assert nombre in texto and "1 para aceptar" in texto and "Profesional P Sintetico" in texto
    assert _a(fake, tel3) == []


def test_texto_no_nombra_al_que_cancelo(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    with session_factory() as s:
        s.add(Paciente(clinica_id=e.c, nombre="Cancelador", apellido="Sintetico", dni="91234567",
                       telefono="+5491199990000", nombre_busqueda="sintetico cancelador",
                       es_seed=True))  # fmt: skip
        s.commit()
        cancelador = s.scalars(select(Paciente.id).where(Paciente.dni == "91234567")).one()
    e.turno(20, cancelador, estado="cancelado")
    pid, tel = e.paciente()
    e.entrada(pid)
    _correr(e, fake)
    [texto] = _a(fake, tel)
    assert "Cancelador" not in texto


def test_otra_prestacion_no_coincide(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, otra = escenario(session_factory, turnos_data), escenario(session_factory, turnos_data)
    otra.ahora = e.ahora
    pid, tel = e.paciente()
    eid = otra.entrada(pid)  # espera OTRA prestación
    e.hueco(20)
    fake = FakeMensajeria()
    _correr(e, fake)
    assert _ofertas(e, eid) == [] and _a(fake, tel) == []


def test_preferencias_de_profesional_y_sillon(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    td = turnos_data
    con_q = e.entrada(e.paciente()[0], profesional_id=td["q"])  # prefiere Q
    con_s2 = e.entrada(e.paciente()[0], sillon_id=td["s2"])  # prefiere S2
    sin_pref = e.entrada(e.paciente()[0])
    e.hueco(20, prof="p", sillon="s1")
    _correr(e, fake)
    assert _ofertas(e, con_q) == [] and _ofertas(e, con_s2) == []
    assert len(_ofertas(e, sin_pref)) == 1


def test_candidato_sin_telefono_se_saltea(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    sin_tel = e.entrada(e.paciente(telefono=None)[0], prioridad=10)
    con_tel = e.entrada(e.paciente()[0], prioridad=0)
    e.hueco(20)
    _correr(e, fake)
    assert _ofertas(e, sin_tel) == [] and len(_ofertas(e, con_tel)) == 1


def test_turno_a_adelantar_anterior_al_hueco(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    pid, _ = e.paciente()
    temprano = e.turno(10, pid, prof="q", sillon="s2")  # su turno es ANTES del hueco
    eid = e.entrada(pid, turno_a_adelantar_id=temprano)
    e.hueco(20)
    _correr(e, fake)
    assert _ofertas(e, eid) == []


def test_hueco_demasiado_cercano(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    eid = e.entrada(e.paciente()[0])
    e.hueco(1.5)  # 90 minutos: menos que la anticipación de 2 h
    _correr(e, fake)
    assert _ofertas(e, eid) == []


def test_hueco_ocupado_de_nuevo(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    e, fake = escenario(session_factory, turnos_data), FakeMensajeria()
    eid = e.entrada(e.paciente()[0])
    e.hueco(20)
    e.turno(20, e.paciente()[0])  # recepción ya dio ese horario
    _correr(e, fake)
    assert _ofertas(e, eid) == []


def test_hueco_de_a_no_va_a_la_cola_de_b(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    a = escenario(session_factory, turnos_data)
    b = escenario(session_factory, turnos_data, clinica="b")
    b.ahora = a.ahora
    eid_b = b.entrada(b.paciente()[0])
    a.hueco(20)
    _correr(a, FakeMensajeria())
    assert _ofertas(b, eid_b) == []
