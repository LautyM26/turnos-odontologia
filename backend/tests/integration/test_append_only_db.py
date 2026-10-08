"""Inmutabilidad a nivel DB de auditoria_hc y ficha_version (C-08 3.3). PG16 real."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


@pytest.fixture()
def filas(session_factory, auth_data):  # type: ignore[no-untyped-def]
    """Un paciente sintético con una versión de ficha y un evento de auditoría."""
    a = auth_data["clinica_a"]
    autor = auth_data["user_ids"]["odonto@test.test"]
    with session_factory() as session:
        pac = session.execute(
            text(
                "INSERT INTO paciente (clinica_id, nombre, apellido, dni, telefono, "
                "nombre_busqueda, es_seed) "
                "VALUES (:c, 'P', 'S', :d, '+5491155550001', 's p', true) "
                "RETURNING id"
            ),
            {"c": a, "d": f"9{uuid4().int % 10**7:07d}"},
        ).scalar()
        ficha = session.execute(
            text(
                "INSERT INTO ficha_version (clinica_id, paciente_id, version, alergias, "
                "autor_usuario_id) VALUES (:c, :p, 1, 'sintetica', :u) RETURNING id"
            ),
            {"c": a, "p": pac, "u": autor},
        ).scalar()
        evento = session.execute(
            text(
                "INSERT INTO auditoria_hc (clinica_id, paciente_id, actor_usuario_id, "
                "actor_tipo, accion, entidad, entidad_id) "
                "VALUES (:c, :p, :u, 'usuario', 'crear', 'ficha', :f) RETURNING id"
            ),
            {"c": a, "p": pac, "u": autor, "f": 1},
        ).scalar()
        session.commit()
    return {"paciente": pac, "ficha": ficha, "evento": evento}


MUTACIONES = [
    ("auditoria_hc", "UPDATE auditoria_hc SET accion='leer' WHERE id=:id", "evento"),
    ("auditoria_hc", "DELETE FROM auditoria_hc WHERE id=:id", "evento"),
    ("ficha_version", "UPDATE ficha_version SET alergias='otra' WHERE id=:id", "ficha"),
    ("ficha_version", "DELETE FROM ficha_version WHERE id=:id", "ficha"),
]


@pytest.mark.parametrize(("tabla", "sql", "clave"), MUTACIONES)
def test_update_delete_rechazados_y_fila_persiste(  # type: ignore[no-untyped-def]
    session_factory, filas, tabla, sql, clave
) -> None:
    with session_factory() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(sql), {"id": filas[clave]})
        session.rollback()
    with session_factory() as session:
        n = session.execute(
            text(f"SELECT count(*) FROM {tabla} WHERE id=:id"), {"id": filas[clave]}
        ).scalar()
    assert n == 1


@pytest.mark.parametrize("tabla", ["auditoria_hc", "ficha_version"])
def test_truncate_rechazado(session_factory, filas, tabla) -> None:  # type: ignore[no-untyped-def]
    with session_factory() as session:
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text(f"TRUNCATE {tabla} CASCADE"))
        session.rollback()
    with session_factory() as session:
        assert session.execute(text(f"SELECT count(*) FROM {tabla}")).scalar() >= 1


def test_insert_sigue_funcionando(session_factory, filas, auth_data) -> None:  # type: ignore[no-untyped-def]
    autor = auth_data["user_ids"]["odonto@test.test"]
    with session_factory() as session:
        nuevo = session.execute(
            text(
                "INSERT INTO ficha_version (clinica_id, paciente_id, version, autor_usuario_id) "
                "VALUES (:c, :p, 2, :u) RETURNING id"
            ),
            {"c": auth_data["clinica_a"], "p": filas["paciente"], "u": autor},
        ).scalar()
        session.commit()
    assert nuevo is not None
