"""Dos correcciones simultáneas de la misma evolución: un 201 y un 409 (C-09 4.2).

La garantía la da el índice único parcial ``uq_evolucion_corrige_a`` (23505 -> 409). PG16 real.
"""

import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.domain.clinica.models import Evolucion
from tests.integration.conftest import bearer, make_test_client, nuevo_paciente_c09


def test_dos_correcciones_simultaneas_un_201_y_un_409(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, staff_c09
) -> None:
    pid = nuevo_paciente_c09(session_factory, staff_c09["a"])
    base = make_test_client(session_factory, monkeypatch)
    h = bearer(base, staff_c09["o_email"])
    e1 = base.post(f"/api/pacientes/{pid}/evoluciones", json={"texto": "E1"}, headers=h).json()

    clientes = [make_test_client(session_factory, monkeypatch) for _ in range(2)]
    barrera = threading.Barrier(2)

    def _una(cli):  # type: ignore[no-untyped-def]
        barrera.wait(timeout=30)
        return cli.post(
            f"/api/pacientes/{pid}/evoluciones",
            json={"texto": "Corregida", "corrige_a_id": e1["id"], "motivo_correccion": "Motivo"},
            headers=h,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        respuestas = list(pool.map(_una, clientes))
    assert Counter(r.status_code for r in respuestas) == {201: 1, 409: 1}
    with session_factory() as s:
        assert (
            s.scalar(
                select(func.count())
                .select_from(Evolucion)
                .where(Evolucion.corrige_a_id == e1["id"])
            )
            == 1
        )
