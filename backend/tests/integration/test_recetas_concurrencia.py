"""Dos emisiones simultáneas con la misma clave: una sola fila, mismo id (C-19 3.5). PG16 real."""

import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import text

from app.infrastructure.recetas.fake import FakePartner
from tests.integration.conftest import (
    bearer,
    con_partner,
    evolucion_sintetica,
    make_test_client,
    nuevo_paciente_c09,
)


def test_dos_emisiones_simultaneas_misma_clave_una_fila(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, staff_c09
) -> None:
    pid = nuevo_paciente_c09(session_factory, staff_c09["a"])
    evo = evolucion_sintetica(
        session_factory, staff_c09["a"], pid, staff_c09["o"], staff_c09["prof_o"]
    )
    base = make_test_client(session_factory, monkeypatch)
    h = bearer(base, staff_c09["o_email"])
    partner = FakePartner()
    clientes = [
        con_partner(make_test_client(session_factory, monkeypatch), partner) for _ in range(2)
    ]
    barrera = threading.Barrier(2)
    cuerpo = {
        "tipo": "receta", "evolucion_id": evo, "diagnostico": "Dx sintetico",
        "clave_idempotencia": str(uuid4()),
        "items": [{"nombre_generico": "ibuprofeno", "presentacion": "400 mg", "cantidad": 1,
                   "posologia": "1 cada 8 horas"}],
    }  # fmt: skip

    def _una(cli):  # type: ignore[no-untyped-def]
        barrera.wait(timeout=30)
        return cli.post(f"/api/pacientes/{pid}/recetas", json=cuerpo, headers=h)

    with ThreadPoolExecutor(max_workers=2) as pool:
        respuestas = list(pool.map(_una, clientes))
    assert all(r.status_code in (200, 201) for r in respuestas), [r.text for r in respuestas]
    assert len({r.json()["id"] for r in respuestas}) == 1
    with session_factory() as s:
        n = s.scalar(text("SELECT count(*) FROM receta_externa WHERE paciente_id=:p"), {"p": pid})
        e = s.scalar(
            text("SELECT count(*) FROM auditoria_hc WHERE paciente_id=:p AND entidad='receta'"),
            {"p": pid},
        )
    assert n == 1 and e == 1
