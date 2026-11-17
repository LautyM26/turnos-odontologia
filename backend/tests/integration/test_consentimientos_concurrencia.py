"""Dos firmas completas simultáneas del mismo documento: un 201 y un 409 (C-18 3.3).

La garantía la da el UNIQUE ``(clinica_id, consentimiento_id)`` de la constancia (23505 -> 409).
PG16 real.
"""

import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text

from tests.integration.conftest import bearer, make_test_client, nuevo_paciente_c09


def test_dos_firmas_simultaneas_un_201_y_un_409(  # type: ignore[no-untyped-def]
    session_factory, monkeypatch, staff_c09
) -> None:
    pid = nuevo_paciente_c09(session_factory, staff_c09["a"])
    base = make_test_client(session_factory, monkeypatch)
    h = bearer(base, staff_c09["o_email"])
    doc = base.post(
        f"/api/pacientes/{pid}/consentimientos", json={"tipo": "implante"}, headers=h
    ).json()

    clientes = [make_test_client(session_factory, monkeypatch) for _ in range(2)]
    barrera = threading.Barrier(2)

    def _una(cli):  # type: ignore[no-untyped-def]
        barrera.wait(timeout=30)
        return cli.post(
            f"/api/pacientes/{pid}/consentimientos/{doc['id']}/firmar",
            json={
                "acepta": True,
                "firmante_nombre": "Firmante Sintetico",
                "firmante_dni": "90000001",
                "texto_hash": doc["texto_hash"],
            },
            headers=h,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        respuestas = list(pool.map(_una, clientes))
    assert Counter(r.status_code for r in respuestas) == {201: 1, 409: 1}
    with session_factory() as s:
        assert (
            s.scalar(
                text("SELECT count(*) FROM consentimiento_firma WHERE consentimiento_id=:c"),
                {"c": doc["id"]},
            )
            == 1
        )
