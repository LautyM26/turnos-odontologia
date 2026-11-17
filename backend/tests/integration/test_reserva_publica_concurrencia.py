"""Reservas públicas concurrentes (C-06): la base arbitra el hueco y el DNI. PG16 real.

Profesional propio con un único sillón (S1) y horario de día completo, para que el único
desempate posible sea la exclusion constraint (23P01) o el UNIQUE (clinica_id, dni) (23505).
"""

import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.domain.agenda.horario import reemplazar_horario
from app.domain.agenda.models import Profesional, ProfesionalSillon
from app.domain.agenda.reserva_publica import reservar
from app.domain.agenda.schemas_publicas import ReservaIn
from app.domain.agenda.turnos import TurnoNoDisponible
from app.domain.pacientes.models import Paciente

AHORA = datetime(2033, 1, 1, tzinfo=UTC)
N = 5


@pytest.fixture(scope="module")
def prof_unico(session_factory, turnos_data):  # type: ignore[no-untyped-def]
    td = turnos_data
    with session_factory() as session:
        prof = Profesional(clinica_id=td["a"], nombre="Prof Concurrencia", matricula="FIX-RC")
        session.add(prof)
        session.flush()
        session.add(
            ProfesionalSillon(clinica_id=td["a"], profesional_id=prof.id, sillon_id=td["s1"])
        )
        session.commit()
        prof_id = prof.id
    with session_factory() as session:
        franjas = [{"dia_semana": d, "inicio": 0, "fin": 1440} for d in range(1, 8)]
        reemplazar_horario(session, td["a"], prof_id, franjas)
    return prof_id


def _en_paralelo(session_factory, lista_datos):  # type: ignore[no-untyped-def]
    barrera = threading.Barrier(len(lista_datos))
    resultados: list[object] = [None] * len(lista_datos)

    def _uno(i: int) -> None:
        barrera.wait()
        try:
            with session_factory() as session:
                resultados[i] = reservar(session, "clinica-piloto", lista_datos[i], AHORA)
        except Exception as exc:  # noqa: BLE001 - se clasifica en el hilo principal
            resultados[i] = exc

    hilos = [threading.Thread(target=_uno, args=(i,)) for i in range(len(lista_datos))]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)
    return resultados


def _datos(td, prof_id, inicio, dni):  # type: ignore[no-untyped-def]
    return ReservaIn(
        profesional_id=prof_id, prestacion_id=td["prest_a"], inicio=inicio.isoformat(), dni=dni,
        nombre="Ana", apellido="Concurrente", email="ana.c@ejemplo.test", acepta_privacidad=True,
    )  # fmt: skip


def test_mismo_hueco_un_201_y_el_resto_409(session_factory, turnos_data, prof_unico) -> None:  # type: ignore[no-untyped-def]
    inicio = datetime(2033, 7, 1, 10, tzinfo=UTC)
    lista = [_datos(turnos_data, prof_unico, inicio, f"4100000{i}") for i in range(N)]
    resultados = _en_paralelo(session_factory, lista)
    ganadores = [r for r in resultados if isinstance(r, tuple)]
    perdedores = [r for r in resultados if isinstance(r, TurnoNoDisponible)]
    assert len(ganadores) == 1, resultados
    assert len(perdedores) == N - 1, resultados


def test_mismo_dni_nuevo_crea_un_solo_paciente(session_factory, turnos_data, prof_unico) -> None:  # type: ignore[no-untyped-def]
    dni = "42000001"
    base = datetime(2033, 7, 2, 9, tzinfo=UTC)
    lista = [_datos(turnos_data, prof_unico, base + timedelta(hours=i), dni) for i in range(2)]
    resultados = _en_paralelo(session_factory, lista)
    assert all(isinstance(r, tuple) for r in resultados), resultados
    with session_factory() as session:
        n = session.scalar(select(func.count()).select_from(Paciente).where(Paciente.dni == dni))
    assert n == 1
