"""Constraints, inmutabilidad y aislamiento a nivel DB de receta_externa (C-19 2.2)."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.integration.conftest import nuevo_paciente_c09

HUELLA = "a" * 64


def _evolucion(session, c, p, usuario, prof) -> int:  # type: ignore[no-untyped-def]
    return session.execute(
        text(
            "INSERT INTO evolucion (clinica_id, paciente_id, autor_usuario_id, profesional_id, "
            "texto) VALUES (:c, :p, :u, :pr, 'Control sintetico') RETURNING id"
        ),
        {"c": c, "p": p, "u": usuario, "pr": prof},
    ).scalar()


def _receta(session, c, p, evo, usuario, prof, **extra) -> int:  # type: ignore[no-untyped-def]
    cols = {
        "tipo": "receta", "partner": "fake", "simulada": True,
        "ext": f"FAKE-{uuid4()}", "url": "https://partner-simulado.invalid/r.pdf",
        "diag": "Dx sintetico", "items": "[]", "clave": str(uuid4()),
    }  # fmt: skip
    cols.update(extra)
    return session.execute(
        text(
            "INSERT INTO receta_externa (clinica_id, paciente_id, evolucion_id, tipo, partner, "
            "simulada, id_externo, pdf_url, diagnostico, items, clave_idempotencia, "
            "huella_solicitud, autor_usuario_id, profesional_id) "
            "VALUES (:c, :p, :e, :tipo, :partner, :simulada, :ext, :url, :diag, "
            "CAST(:items AS jsonb), :clave, :h, :u, :pr) RETURNING id"
        ),
        {"c": c, "p": p, "e": evo, "u": usuario, "pr": prof, "h": HUELLA, **cols},
    ).scalar()


@pytest.fixture()
def datos(session_factory, staff_c09):  # type: ignore[no-untyped-def]
    a, b = staff_c09["a"], staff_c09["b"]
    u, prof = staff_c09["o"], staff_c09["prof_o"]
    pa = nuevo_paciente_c09(session_factory, a)
    pa2 = nuevo_paciente_c09(session_factory, a)
    pb = nuevo_paciente_c09(session_factory, b)
    with session_factory() as s:
        evo = _evolucion(s, a, pa, u, prof)
        evo_otro_paciente = _evolucion(s, a, pa2, u, prof)
        rid = _receta(s, a, pa, evo, u, prof)
        s.commit()
    return {"a": a, "b": b, "u": u, "prof": prof, "pa": pa, "pb": pb, "evo": evo,
            "evo_otro": evo_otro_paciente, "rid": rid}  # fmt: skip


def _falla(session_factory, codigo: str, fn) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        with pytest.raises((IntegrityError, DBAPIError)) as exc:
            fn(s)
            s.commit()
        assert getattr(exc.value.orig, "sqlstate", None) == codigo, exc.value
        s.rollback()


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE receta_externa SET diagnostico='otro' WHERE id=:i",
        "DELETE FROM receta_externa WHERE id=:i",
        "TRUNCATE receta_externa",
    ],
)
def test_update_delete_truncate_rechazados_y_fila_persiste(session_factory, datos, sql) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s, pytest.raises((IntegrityError, DBAPIError)):
        s.execute(text(sql), {"i": datos["rid"]})
        s.commit()
    with session_factory() as s:
        assert s.scalar(text("SELECT count(*) FROM receta_externa WHERE id=:i"),
                        {"i": datos["rid"]}) == 1  # fmt: skip


def test_evolucion_de_otro_paciente_23503(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    d = datos
    _falla(session_factory, "23503",
           lambda s: _receta(s, d["a"], d["pa"], d["evo_otro"], d["u"], d["prof"]))  # fmt: skip


def test_evolucion_de_otra_clinica_23503(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    d = datos
    _falla(session_factory, "23503",
           lambda s: _receta(s, d["b"], d["pb"], d["evo"], d["u"], d["prof"]))  # fmt: skip


def test_clave_repetida_en_la_clinica_23505(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    d = datos
    with session_factory() as s:
        clave = s.scalar(text("SELECT clave_idempotencia FROM receta_externa WHERE id=:i"),
                         {"i": d["rid"]})  # fmt: skip
    _falla(
        session_factory,
        "23505",
        lambda s: _receta(s, d["a"], d["pa"], d["evo"], d["u"], d["prof"], clave=str(clave)),
    )


def test_id_externo_repetido_por_partner_23505(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    d = datos
    with session_factory() as s:
        ext = s.scalar(text("SELECT id_externo FROM receta_externa WHERE id=:i"), {"i": d["rid"]})
    _falla(session_factory, "23505",
           lambda s: _receta(s, d["a"], d["pa"], d["evo"], d["u"], d["prof"], ext=ext))  # fmt: skip


@pytest.mark.parametrize(
    "extra",
    [
        {"items": '{"a": 1}'},
        {"url": "http://inseguro.invalid/r.pdf"},
        {"diag": ""},
        {"diag": "x" * 501},
        {"tipo": "otro"},
    ],
)
def test_checks_23514(session_factory, datos, extra) -> None:  # type: ignore[no-untyped-def]
    d = datos
    _falla(session_factory, "23514",
           lambda s: _receta(s, d["a"], d["pa"], d["evo"], d["u"], d["prof"], **extra))  # fmt: skip


def test_orden_de_estudio_valida(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    d = datos
    with session_factory() as s:
        assert _receta(s, d["a"], d["pa"], d["evo"], d["u"], d["prof"], tipo="orden_estudio")
        s.commit()


def test_consulta_con_otra_clinica_devuelve_0_filas(session_factory, datos) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as s:
        n = s.scalar(text("SELECT count(*) FROM receta_externa WHERE clinica_id=:c"),
                     {"c": datos["b"]})  # fmt: skip
        assert n == 0
