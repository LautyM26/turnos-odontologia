"""Reemplazo concurrente del horario (C-05d D3): gana un set completo, nunca la unión.

Determinista: la sesión 1 toma el lock del profesional y deja su reemplazo sin confirmar.
``reemplazar_horario`` en otro hilo tiene que esperar. Sin el ``FOR UPDATE``, el hilo borraría
solo las filas viejas, insertaría las suyas y quedarían los dos sets mezclados.
"""

import threading
import time

from sqlalchemy import delete, select

from app.domain.agenda.horario import reemplazar_horario
from app.domain.agenda.models import FranjaHoraria, Profesional

SET_A = [{"dia_semana": 1, "inicio": 540, "fin": 780}]
SET_B = [{"dia_semana": 1, "inicio": 600, "fin": 660}, {"dia_semana": 3, "inicio": 540, "fin": 600}]


def _franjas(session_factory, clinica_id: int, prof_id: int) -> list[tuple[int, int, int]]:
    with session_factory() as session:
        return [
            (f.dia_semana, f.inicio_min, f.fin_min)
            for f in session.scalars(
                select(FranjaHoraria)
                .where(FranjaHoraria.clinica_id == clinica_id,
                       FranjaHoraria.profesional_id == prof_id)
                .order_by(FranjaHoraria.dia_semana, FranjaHoraria.inicio_min)
            )
        ]  # fmt: skip


def test_reemplazo_concurrente_espera_el_lock_y_deja_un_solo_set(  # type: ignore[no-untyped-def]
    session_factory, catalogo_data
) -> None:
    a, q = catalogo_data["a"], catalogo_data["prof_q"]
    with session_factory() as s0:
        reemplazar_horario(s0, a, q, [{"dia_semana": 5, "inicio": 0, "fin": 60}])  # horario viejo

    s1 = session_factory()
    s1.scalars(select(Profesional).where(Profesional.id == q).with_for_update()).one()
    s1.execute(delete(FranjaHoraria).where(FranjaHoraria.profesional_id == q))
    s1.add_all(
        FranjaHoraria(clinica_id=a, profesional_id=q, dia_semana=f["dia_semana"],
                      inicio_min=f["inicio"], fin_min=f["fin"])
        for f in SET_A
    )  # fmt: skip
    s1.flush()

    errores: list[BaseException] = []

    def _segundo() -> None:
        try:
            with session_factory() as s2:
                reemplazar_horario(s2, a, q, SET_B)
        except BaseException as exc:  # noqa: BLE001 - se reporta en el hilo principal
            errores.append(exc)

    hilo = threading.Thread(target=_segundo)
    hilo.start()
    time.sleep(1.0)
    assert hilo.is_alive(), "el segundo reemplazo no esperó el lock del profesional"
    s1.commit()
    s1.close()
    hilo.join(timeout=10)
    assert not hilo.is_alive() and not errores, errores
    assert _franjas(session_factory, a, q) == [(1, 600, 660), (3, 540, 600)]  # solo SET_B
