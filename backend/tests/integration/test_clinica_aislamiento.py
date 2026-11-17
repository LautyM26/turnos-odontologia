"""Aislamiento multi-tenant de odontograma y evoluciones por API (C-09 5.3). PG16 real."""

import pytest
from sqlalchemy import func, select, text

from app.domain.auditoria.models import AuditoriaHC
from app.domain.clinica import servicios
from app.domain.clinica.models import Evolucion, Odontograma
from tests.integration.conftest import bearer


@pytest.fixture()
def datos_b(session_factory, staff_c09):  # type: ignore[no-untyped-def]
    """Odontograma y evolución en la clínica B (SQL directo, sintético)."""
    b, pac_b = staff_c09["b"], staff_c09["pac_b"]
    with session_factory() as s:
        usr_b = s.execute(
            text("SELECT id FROM usuario WHERE clinica_id=:b LIMIT 1"), {"b": b}
        ).scalar()
        prof_b = s.execute(
            text("SELECT id FROM profesional WHERE clinica_id=:b LIMIT 1"), {"b": b}
        ).scalar()
        if prof_b is None:
            prof_b = s.execute(
                text(
                    "INSERT INTO profesional (clinica_id, nombre, matricula) "
                    "VALUES (:b, 'Prof B C09', 'C09-B') RETURNING id"
                ),
                {"b": b},
            ).scalar()
        s.execute(
            text(
                "INSERT INTO odontograma (clinica_id, paciente_id, version, denticion, "
                "autor_usuario_id) VALUES (:b, :p, :v, 'permanente', :u) "
                "ON CONFLICT DO NOTHING"
            ),
            {"b": b, "p": pac_b, "v": 1, "u": usr_b},
        )
        evo = s.execute(
            text(
                "INSERT INTO evolucion (clinica_id, paciente_id, autor_usuario_id, "
                "profesional_id, texto) VALUES (:b, :p, :u, :prof, 'Evolucion B sintetica') "
                "RETURNING id"
            ),
            {"b": b, "p": pac_b, "u": usr_b, "prof": prof_b},
        ).scalar()
        s.commit()
    return {"pac": pac_b, "evo": evo}


def _eventos_b(session_factory, pac: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(
            select(func.count()).select_from(AuditoriaHC).where(AuditoriaHC.paciente_id == pac)
        )


def _n_evoluciones(session_factory, pac: int) -> int:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        return s.scalar(
            select(func.count()).select_from(Evolucion).where(Evolucion.paciente_id == pac)
        )


def test_servicio_con_clinica_a_no_ve_filas_de_b(session_factory, staff_c09, datos_b) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        assert servicios.versiones_odontograma(s, staff_c09["b"], datos_b["pac"])  # B sí ve
        assert servicios.versiones_odontograma(s, staff_c09["a"], datos_b["pac"]) == []
        assert servicios.evoluciones_pagina(s, staff_c09["a"], datos_b["pac"], None, 50)[0] == []
        assert servicios.odontograma_vigente(s, staff_c09["a"], datos_b["pac"]) is None
        assert (
            s.scalar(
                select(func.count())
                .select_from(Evolucion)
                .where(
                    Evolucion.clinica_id == staff_c09["a"], Evolucion.paciente_id == datos_b["pac"]
                )
            )
            == 0
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(Odontograma)
                .where(
                    Odontograma.clinica_id == staff_c09["a"],
                    Odontograma.paciente_id == datos_b["pac"],
                )
            )
            == 0
        )


def test_por_api_a_no_ve_ni_escribe_en_b_y_no_audita(
    client, session_factory, staff_c09, datos_b
) -> None:  # type: ignore[no-untyped-def]
    h = bearer(client, staff_c09["o_email"])
    ha = bearer(client, staff_c09["admin_solo_email"])
    pac, evo = datos_b["pac"], datos_b["evo"]
    antes = _eventos_b(session_factory, pac)
    evoluciones_antes = _n_evoluciones(session_factory, pac)
    base = f"/api/pacientes/{pac}"
    llamadas = [
        ("GET", f"{base}/odontograma", None, h),
        ("GET", f"{base}/odontograma/actual", None, h),
        (
            "POST",
            f"{base}/odontograma",
            {"version_esperada": 0, "denticion": "permanente", "piezas": {}},
            h,
        ),
        ("GET", f"{base}/evoluciones", None, h),
        ("GET", f"{base}/evoluciones/{evo}", None, h),
        ("POST", f"{base}/evoluciones", {"texto": "intruso"}, h),
        (
            "POST",
            f"{base}/evoluciones",
            {"texto": "x", "corrige_a_id": evo, "motivo_correccion": "m"},
            h,
        ),
        ("GET", f"{base}/historia", None, ha),
    ]
    for metodo, url, cuerpo, hdr in llamadas:
        r = client.request(metodo, url, json=cuerpo, headers=hdr)
        assert r.status_code == 404, (metodo, url, r.status_code)
    assert _eventos_b(session_factory, pac) == antes
    assert _n_evoluciones(session_factory, pac) == evoluciones_antes  # nada escrito en B
