"""Dos guardados simultáneos del odontograma: uno crea la v3, el otro recibe 409 (C-09 3.2).

Cada request usa su propio TestClient (sesión nueva) y un ``Barrier``; la garantía final la da
``UNIQUE (clinica_id, paciente_id, version)`` con el mapeo 23505 -> 409. PG16 real.
"""

import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.domain.clinica.models import Odontograma
from tests.integration.conftest import bearer, make_test_client, nuevo_paciente_c09


def test_dos_guardados_simultaneos_un_201_y_un_409(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, staff_c09
) -> None:
    pid = nuevo_paciente_c09(session_factory, staff_c09["a"])
    base = make_test_client(session_factory, monkeypatch)
    h = bearer(base, staff_c09["o_email"])
    for v in (0, 1):
        r = base.post(
            f"/api/pacientes/{pid}/odontograma",
            json={"version_esperada": v, "denticion": "permanente", "piezas": {}},
            headers=h,
        )
        assert r.status_code == 201

    clientes = [make_test_client(session_factory, monkeypatch) for _ in range(2)]
    barrera = threading.Barrier(2)

    def _una(cli):  # type: ignore[no-untyped-def]
        barrera.wait(timeout=30)
        return cli.post(
            f"/api/pacientes/{pid}/odontograma",
            json={"version_esperada": 2, "denticion": "permanente", "piezas": {"16": {}}},
            headers=h,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        respuestas = list(pool.map(_una, clientes))
    assert Counter(r.status_code for r in respuestas) == {201: 1, 409: 1}
    with session_factory() as s:
        versiones = s.scalars(
            select(Odontograma.version).where(Odontograma.paciente_id == pid)
        ).all()
        assert sorted(versiones) == [1, 2, 3]
        assert (
            s.scalar(
                select(func.count())
                .select_from(Odontograma)
                .where(Odontograma.paciente_id == pid, Odontograma.version == 3)
            )
            == 1
        )
