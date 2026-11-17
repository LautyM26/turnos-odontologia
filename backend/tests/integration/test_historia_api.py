"""Historia clínica consolidada (C-09 5.1). PG16 real, datos sintéticos."""

import pytest
from sqlalchemy import select

from app.domain.auditoria.models import AuditoriaHC
from tests.integration.conftest import bearer, nuevo_paciente_c09


@pytest.fixture()
def pid(session_factory, staff_c09) -> int:  # type: ignore[no-untyped-def]
    return nuevo_paciente_c09(session_factory, staff_c09["a"])


def _h(client, staff_c09, clave="o"):  # type: ignore[no-untyped-def]
    return bearer(client, staff_c09[f"{clave}_email"])


def _evento_leer_paciente(session_factory, pid):  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return list(
            s.scalars(
                select(AuditoriaHC).where(
                    AuditoriaHC.paciente_id == pid,
                    AuditoriaHC.accion == "leer",
                    AuditoriaHC.entidad == "paciente",
                )
            ).all()
        )


def test_historia_completa(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    for v in (0, 1):
        assert (
            client.put(
                f"/api/pacientes/{pid}/ficha",
                json={"version_esperada": v, "alergias": f"a{v}"},
                headers=h,
            ).status_code
            == 200
        )
    assert (
        client.post(
            f"/api/pacientes/{pid}/odontograma",
            json={"version_esperada": 0, "denticion": "permanente", "piezas": {"16": {}}},
            headers=h,
        ).status_code
        == 201
    )
    ids = [
        client.post(f"/api/pacientes/{pid}/evoluciones", json={"texto": f"E{i}"}, headers=h).json()[
            "id"
        ]
        for i in range(3)
    ]
    r = client.get(f"/api/pacientes/{pid}/historia", headers=_h(client, staff_c09, "admin_solo"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ficha"]["version"] == 2 and body["ficha"]["alergias"] == "a1"
    assert body["odontograma"]["version"] == 1 and "16" in body["odontograma"]["piezas"]
    assert [e["id"] for e in body["evoluciones"]] == ids[::-1]
    assert body["next_cursor"] is None


def test_paciente_sin_datos_clinicos(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    r = client.get(f"/api/pacientes/{pid}/historia", headers=_h(client, staff_c09))
    assert r.status_code == 200
    body = r.json()
    assert body["ficha"]["version"] == 0
    assert body["odontograma"]["version"] == 0 and body["odontograma"]["piezas"] == {}
    assert body["evoluciones"] == [] and body["next_cursor"] is None


def test_51_evoluciones_50_mas_cursor_que_continua(client, staff_c09, pid) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    ids = [
        client.post(f"/api/pacientes/{pid}/evoluciones", json={"texto": f"E{i}"}, headers=h).json()[
            "id"
        ]
        for i in range(51)
    ]
    body = client.get(f"/api/pacientes/{pid}/historia", headers=h).json()
    assert len(body["evoluciones"]) == 50 and body["next_cursor"]
    assert body["evoluciones"][0]["id"] == ids[-1]
    resto = client.get(
        f"/api/pacientes/{pid}/evoluciones?after_id={body['next_cursor']}", headers=h
    ).json()
    assert [e["id"] for e in resto["items"]] == [ids[0]] and resto["next_cursor"] is None


def test_paciente_de_otra_clinica_404(client, staff_c09) -> None:  # type: ignore[no-untyped-def]
    r = client.get(
        f"/api/pacientes/{staff_c09['pac_b']}/historia", headers=_h(client, staff_c09, "admin_solo")
    )
    assert r.status_code == 404


def test_un_solo_evento_leer_paciente_con_los_tres_campos(
    client, session_factory, staff_c09, pid
) -> None:  # type: ignore[no-untyped-def]
    h = _h(client, staff_c09)
    client.post(f"/api/pacientes/{pid}/evoluciones", json={"texto": "E"}, headers=h)
    assert client.get(f"/api/pacientes/{pid}/historia", headers=h).status_code == 200
    eventos = _evento_leer_paciente(session_factory, pid)
    assert len(eventos) == 1
    assert eventos[0].diff == {"campos": ["ficha", "odontograma", "evoluciones"]}
    assert eventos[0].actor_usuario_id == staff_c09["o"] and eventos[0].entidad_id == pid
    with session_factory() as s:  # y ningún evento de lectura de ficha/odontograma/evolución suelto
        sueltos = s.scalars(
            select(AuditoriaHC).where(
                AuditoriaHC.paciente_id == pid,
                AuditoriaHC.accion == "leer",
                AuditoriaHC.entidad != "paciente",
            )
        ).all()
    assert sueltos == []
