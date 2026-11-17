"""``horario_libre`` (C-16 2.2, D9): mismas reglas que el pre-chequeo de ``crear_turno``."""

from datetime import UTC, datetime, timedelta

from app.domain.agenda.models import Bloqueo, FranjaHoraria, Profesional, ProfesionalSillon
from app.domain.agenda.turnos import Turno, horario_libre

INICIO = datetime(2036, 4, 7, 13, tzinfo=UTC)  # lunes
FIN = INICIO + timedelta(minutes=30)


def _libre(session_factory, td, prof=None, inicio=INICIO) -> bool:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return horario_libre(s, td["a"], inicio, inicio + timedelta(minutes=30),
                             prof or td["p"], td["s1"])  # fmt: skip


def test_libre_y_ocupado_por_turno(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    assert _libre(session_factory, turnos_data)
    with session_factory() as s:
        s.add(Turno(clinica_id=turnos_data["a"], profesional_id=turnos_data["p"],
                    sillon_id=turnos_data["s1"], paciente_id=turnos_data["pac_a"],
                    prestacion_id=turnos_data["prest_a"], duracion_min=30, inicio=INICIO,
                    fin=FIN))  # fmt: skip
        s.commit()
    assert not _libre(session_factory, turnos_data)


def test_cancelado_no_ocupa(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    inicio = INICIO + timedelta(days=1)
    with session_factory() as s:
        s.add(Turno(clinica_id=turnos_data["a"], profesional_id=turnos_data["p"],
                    sillon_id=turnos_data["s1"], paciente_id=turnos_data["pac_a"],
                    prestacion_id=turnos_data["prest_a"], duracion_min=30, inicio=inicio,
                    fin=inicio + timedelta(minutes=30), estado="cancelado"))  # fmt: skip
        s.commit()
    assert _libre(session_factory, turnos_data, inicio=inicio)


def test_bloqueo(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    inicio = INICIO + timedelta(days=2)
    with session_factory() as s:
        s.add(Bloqueo(clinica_id=turnos_data["a"], profesional_id=turnos_data["p"], inicio=inicio,
                      fin=inicio + timedelta(hours=1), motivo="bloqueo sintetico"))  # fmt: skip
        s.commit()
    assert not _libre(session_factory, turnos_data, inicio=inicio)


def test_fuera_de_horario(session_factory, turnos_data) -> None:  # type: ignore[no-untyped-def]
    a = turnos_data["a"]
    with session_factory() as s:
        prof = Profesional(clinica_id=a, nombre="Profesional Horario", matricula="HL-1")
        s.add(prof)
        s.flush()
        s.add(ProfesionalSillon(clinica_id=a, profesional_id=prof.id, sillon_id=turnos_data["s1"]))
        s.add(FranjaHoraria(clinica_id=a, profesional_id=prof.id, dia_semana=1,
                            inicio_min=0, fin_min=60))  # fmt: skip
        s.commit()
        prof_id = prof.id
    assert not _libre(session_factory, turnos_data, prof=prof_id)
